import fs from 'fs';
import path from 'path';
import { getCurrentOrLatestWeek } from './dateValidator.js';
import { buildVbotMetaById } from './vbotMeta.js';

const parseRef = (ref) => {
  if (!ref) return null;
  const parts = ref.split('::');
  return parts.length > 1 ? parts[1] : parts[0];
};

function resolveObjectsDir() {
  if (process.env.DATA_DIR) {
    return process.env.DATA_DIR;
  }
  const candidates = [
    path.resolve('public/WRFrontiersDB-Data/current/Objects'),
    path.resolve('../../WRFrontiersDB-Data/current/Objects'),
    path.resolve('../../../WRFrontiersDB-Data/current/Objects'),
  ];
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'Module.json'))) {
      return dir;
    }
  }
  console.warn(
    'WRFrontiersDB-Data Objects not found. Tried:',
    candidates.join(', ')
  );
  return candidates[0];
}

export function fetchEnrichedDiscounts(filename = null) {
  const dataDir = resolveObjectsDir();
  const frontendDataDir = path.resolve('public/data');
  
  const readJson = (file, dir = dataDir) => {
    try {
      const filePath = path.join(dir, file);
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (e) {
      console.error(`Error reading ${file}:`, e);
      return {};
    }
  };

  const manifest = readJson('weeks.json', frontendDataDir);
  let targetWeek = null;
  
  if (filename) {
    targetWeek = manifest.weeks?.find(w => w.file === filename || w.slug === filename);
  } else if (manifest && manifest.weeks && manifest.weeks.length > 0) {
    targetWeek = getCurrentOrLatestWeek(manifest.weeks) || manifest.weeks[0];
  }
  
  if (!targetWeek) {
    return { dateRange: "", gridData: { standardRows: [], titanRows: [] }, shopCards: {}, catIcons: [], vbotMetaById: {} };
  }

  const slug = targetWeek.slug;
  const dateRange = targetWeek.date_range || "";
  
  const gridData = readJson(`grid_${slug}.json`, frontendDataDir);
  const columnsList = readJson('columns.json', frontendDataDir) || [];
  
  if (!gridData || (!gridData.standardRows && !gridData.titanRows)) {
    return { dateRange, gridData: { standardRows: [], titanRows: [] }, shopCards: {}, catIcons: [], vbotMetaById: {} };
  }

  const ModuleDB = readJson('Module.json');
  const ModuleRarityDB = readJson('ModuleRarity.json');
  const ModuleTypeDB = readJson('ModuleType.json');
  const ModuleCategoryDB = readJson('ModuleCategory.json');
  const ModuleSocketTypeDB = readJson('ModuleSocketType.json');
  const ShopCardDB = readJson('ShopCard.json');
  const VirtualBotDB = readJson('VirtualBot.json');
  const FactionDB = readJson('Faction.json');
  const ModuleClassDB = readJson('ModuleClass.json');
  const CharacterClassDB = readJson('CharacterClass.json');

  const databases = {
    ModuleDB,
    ModuleTypeDB,
    VirtualBotDB,
    FactionDB,
    ModuleClassDB,
    CharacterClassDB,
  };

  // Build catIcons array from columns.json
  const catIcons = columnsList.map(colRef => {
    if (colRef === "VirtualBots") {
      return "Bot";
    }
    const colId = parseRef(colRef);
    let iconPath = null;
    if (ModuleSocketTypeDB[colId]) {
      iconPath = ModuleSocketTypeDB[colId].icon_path;
    } else if (ModuleCategoryDB[colId]) {
      iconPath = ModuleCategoryDB[colId].icon_path;
    }
    return iconPath;
  });

  const enrichModuleId = (moduleId) => {
    if (!moduleId) return null;
    const module = ModuleDB[moduleId];
    if (!module) return null;
    
    const rarityRef = parseRef(module.module_rarity_ref);
    const moduleRarity = ModuleRarityDB[rarityRef];
    const baseRarityRef = moduleRarity ? parseRef(moduleRarity.rarity_ref) : null;
    
    return {
      id: moduleId,
      name: module.name?.en || moduleId,
      icon_path: module.inventory_icon_path,
      rarity: baseRarityRef
    };
  };

  const vbotIds = new Set();
  
  const enrichRow = (row) => {
    if (row.botId) vbotIds.add(row.botId);
    const enrichedCells = {};
    for (const [col, moduleId] of Object.entries(row.cells || {})) {
      enrichedCells[col] = enrichModuleId(moduleId);
    }
    return { botId: row.botId, cells: enrichedCells };
  };

  const enrichedStandardRows = (gridData.standardRows || []).map(enrichRow);
  const enrichedTitanRows = (gridData.titanRows || []).map(enrichRow);

  const vbotMetaById = buildVbotMetaById(Array.from(vbotIds), databases, parseRef);

  return {
    dateRange,
    gridData: {
      standardRows: enrichedStandardRows,
      titanRows: enrichedTitanRows
    },
    shopCards: ShopCardDB,
    catIcons,
    vbotMetaById,
  };
}
