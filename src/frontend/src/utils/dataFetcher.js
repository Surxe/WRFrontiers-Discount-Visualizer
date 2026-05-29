import fs from 'fs';
import path from 'path';

// Helper to strip "OBJID_Type::" prefixes
const parseRef = (ref) => {
  if (!ref) return null;
  const parts = ref.split('::');
  return parts.length > 1 ? parts[1] : parts[0];
};

export function fetchEnrichedDiscounts() {
  // Use absolute path or fallback to process.cwd() assuming we're running from src/frontend
  const dataDir = process.env.DATA_DIR || path.resolve('../../WRFrontiersDB-Data/current/Objects');
  const frontendDataDir = path.resolve('public/data');
  
  const readJson = (filename, dir = dataDir) => {
    try {
      const filePath = path.join(dir, filename);
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (e) {
      console.error(`Error reading ${filename}:`, e);
      return {};
    }
  };

  const discountsOutput = readJson('discounts.json', frontendDataDir);
  const itemsArray = Array.isArray(discountsOutput.items) ? discountsOutput.items : [];
  const dateRange = discountsOutput.date_range || "";

  if (itemsArray.length === 0) {
    return { dateRange, items: [], shopCards: {} };
  }

  const ModuleDB = readJson('Module.json');
  const ModuleRarityDB = readJson('ModuleRarity.json');
  const RarityDB = readJson('Rarity.json');
  const ModuleTypeDB = readJson('ModuleType.json');
  const ModuleCategoryDB = readJson('ModuleCategory.json');
  const ModuleGroupDB = readJson('ModuleGroup.json');
  const ShopCardDB = readJson('ShopCard.json');
  const VirtualBotDB = readJson('VirtualBot.json');

  const enrichedDiscounts = itemsArray.map(item => {
    const moduleId = item.id;
    const module = ModuleDB[moduleId];
    
    if (!module) {
      return { ...item, _missing: true };
    }

    // Resolve Rarity
    const rarityRef = parseRef(module.module_rarity_ref);
    const moduleRarity = ModuleRarityDB[rarityRef];
    const baseRarityRef = moduleRarity ? parseRef(moduleRarity.rarity_ref) : null;
    const rarityObj = baseRarityRef ? RarityDB[baseRarityRef] : null;

    // Resolve Category
    const typeRef = parseRef(module.module_type_ref);
    const moduleType = ModuleTypeDB[typeRef];
    const categoryRef = moduleType ? parseRef(moduleType.module_category_ref) : null;
    const categoryObj = categoryRef ? ModuleCategoryDB[categoryRef] : null;

    // Resolve Group
    const groupRef = parseRef(module.module_group_ref);
    const groupObj = groupRef ? ModuleGroupDB[groupRef] : null;

    // Resolve Virtual Bot
    const vbotRef = parseRef(module.virtual_bot_ref);
    const vbotObj = vbotRef ? VirtualBotDB[vbotRef] : null;

    return {
      ...item,
      name: item.name,
      icon_path: module.inventory_icon_path,
      rarity: baseRarityRef,
      category: categoryRef,
      group: groupRef,
      vbot: vbotRef
    };
  }).filter(item => !item._missing);

  // Grouping by vbot for chassis/torso/shoulder and validating rarity
  const botParts = enrichedDiscounts.filter(item => ['Chassis', 'Torso', 'Shoulder'].some(c => item.category && item.category.includes(c)));
  
  const botsMap = {};
  for (const part of botParts) {
    if (part.vbot) {
      if (!botsMap[part.vbot]) {
        botsMap[part.vbot] = { rarities: new Set(), parts: [] };
      }
      botsMap[part.vbot].rarities.add(part.rarity);
      botsMap[part.vbot].parts.push(part);
    }
  }

  // Validate rarities
  for (const [vbot, data] of Object.entries(botsMap)) {
    if (data.rarities.size > 1) {
      throw new Error(`Rarity mismatch for Virtual Bot ${vbot}. Found rarities: ${Array.from(data.rarities).join(', ')}`);
    }
  }

  return {
    dateRange,
    items: enrichedDiscounts,
    shopCards: ShopCardDB
  };
}
