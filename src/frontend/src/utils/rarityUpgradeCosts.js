/**
 * Rarity upgrade cost data: disk loader + view model.
 *
 * `loadRarityUpgradeCosts()` is the single source of truth for reading
 * RarityUpgradeCost.json (shared by DiscountPage.astro and the costs page).
 * `buildRarityCostRows()` shapes that raw data into the per-rarity / per-level
 * model the Upgrade Costs page renders.
 */

import fs from 'fs';
import path from 'path';

/**
 * Load and parse RarityUpgradeCost.json, trying the known relative locations
 * in order. Returns the parsed object, or `{}` if it can't be found/read.
 */
export function loadRarityUpgradeCosts() {
  try {
    const ruPath = [
      path.resolve('../../WRFrontiersDB-Data/current/Objects/RarityUpgradeCost.json'),
      path.resolve('../../../WRFrontiersDB-Data/current/Objects/RarityUpgradeCost.json'),
      path.resolve('public/WRFrontiersDB-Data/current/Objects/RarityUpgradeCost.json'),
    ].find(p => fs.existsSync(p));
    if (ruPath) return JSON.parse(fs.readFileSync(ruPath, 'utf-8'));
  } catch (e) {
    console.error('Failed to load RarityUpgradeCost.json', e);
  }
  return {};
}

// Rarity display order + identity color (validated categorical palette, dark surface).
// Rarity is always text-labelled, so colour is a reinforcement, never the sole cue.
export const RARITY_META = {
  Common:   { color: '#8b93a7', order: 0 },
  Uncommon: { color: '#2f9e56', order: 1 },
  Rare:     { color: '#2f7de0', order: 2 },
  Epic:     { color: '#d857a8', order: 3 },
};

const DEFAULT_RARITY_META = { color: '#8b93a7', order: 99 };

/** Parse "OBJID_ModuleRarity::DA_ModuleRarity_Epic.0" -> "Epic". */
export function rarityName(ref) {
  const m = /DA_ModuleRarity_([A-Za-z]+)/.exec(ref || '');
  return m ? m[1] : ref;
}

/**
 * @typedef {Object} LevelRow
 * @property {number} level
 * @property {'salvage' | 'intel'} currency
 * @property {number} base
 * @property {number | null} discounted
 * @property {number | null} pctOff
 */

/**
 * Shape the raw RarityUpgradeCost data into a sorted array of rarities, each
 * with its per-level cost rows and headline per-currency savings.
 */
export function buildRarityCostRows(rarityUpgradeCosts = {}) {
  return Object.values(rarityUpgradeCosts)
    .map(entry => {
      const name = rarityName(entry.rarity_ref || entry.id);
      const meta = RARITY_META[name] || DEFAULT_RARITY_META;

      /** @type {LevelRow[]} */
      const levels = [];
      for (let lvl = 1; lvl <= 13; lvl++) {
        const node = entry.costs?.[String(lvl)];
        if (!node) continue;
        const salv = node.salvage || {};
        const intel = node.intel || {};
        const isSalvage = (salv.standard || salv.discounted) ? true
          : (intel.standard || intel.discounted) ? false
          : true;
        const cur = isSalvage ? salv : intel;
        const base = cur.standard ?? 0;
        const discounted = cur.discounted ?? null;
        const pctOff = discounted != null && base > 0
          ? Math.round((1 - discounted / base) * 100)
          : null;
        levels.push({
          level: lvl,
          currency: isSalvage ? 'salvage' : 'intel',
          base,
          discounted,
          pctOff,
        });
      }

      // Per-currency headline savings (levels that actually carry a discount).
      const savingsFor = currency => {
        const d = levels.filter(l => l.currency === currency && l.pctOff != null);
        if (d.length === 0) return null;
        return Math.round(d.reduce((s, l) => s + (l.pctOff || 0), 0) / d.length);
      };

      return {
        name,
        color: meta.color,
        order: meta.order,
        levels,
        salvageSavings: savingsFor('salvage'),
        intelSavings: savingsFor('intel'),
      };
    })
    .sort((a, b) => a.order - b.order);
}

/** Format a cost value for display; null -> em dash. */
export function formatCost(n) {
  return n == null ? '—' : n.toLocaleString();
}
