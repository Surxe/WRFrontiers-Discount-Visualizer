import fs from 'fs';
import path from 'path';

// Helper to strip "OBJID_Type::" prefixes
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

export function fetchEnrichedDiscounts() {
  const dataDir = resolveObjectsDir();
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
  const ModuleSocketTypeDB = readJson('ModuleSocketType.json');
  const ShopCardDB = readJson('ShopCard.json');
  const VirtualBotDB = readJson('VirtualBot.json');

  // Build reverse map: moduleId → { vbotId, icon_path }
  const moduleToVbot = {};
  for (const [vbotId, vbot] of Object.entries(VirtualBotDB)) {
    for (const ref of (vbot.core_module_refs || [])) {
      const moduleId = parseRef(ref);
      if (moduleId) {
        moduleToVbot[moduleId] = { vbotId, icon_path: vbot.icon_path };
      }
    }
  }

  const getSocketIcon = (moduleTypeId) => {
    const fullRef = `OBJID_ModuleType::${moduleTypeId}`;
    for (const socket of Object.values(ModuleSocketTypeDB)) {
      if (socket.compatible_module_types_refs?.includes(fullRef)) {
        return socket.icon_path;
      }
    }
    // Fallback to Category icon if not found
    const typeObj = ModuleTypeDB[moduleTypeId];
    if (typeObj && typeObj.module_category_ref) {
      const catRef = parseRef(typeObj.module_category_ref);
      return ModuleCategoryDB[catRef]?.icon_path;
    }
    return null;
  };

  const catIcons = {
    torso: getSocketIcon('DA_ModuleType_Torso.0'),
    shoulder: getSocketIcon('DA_ModuleType_Shoulder.0'),
    chassis: getSocketIcon('DA_ModuleType_Chassis.0'),
    lightWep: getSocketIcon('DA_ModuleType_Weapon.0'),
    heavyWep: getSocketIcon('DA_ModuleType_WeaponHeavy.0'),
    supplyGear: getSocketIcon('DA_ModuleType_Ability3.0'),
    cycleGear: getSocketIcon('DA_ModuleType_Ability4.0')
  };

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

    // Resolve Virtual Bot via reverse lookup
    const vbotEntry = moduleToVbot[moduleId];
    const vbotRef = vbotEntry?.vbotId || null;
    const vbotIconPath = vbotEntry?.icon_path || null;

    return {
      ...item,
      name: item.name,
      icon_path: module.inventory_icon_path,
      rarity: baseRarityRef,
      category: categoryRef,
      group: groupRef,
      vbot: vbotRef,
      vbot_icon_path: vbotIconPath
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
    shopCards: ShopCardDB,
    catIcons
  };
}
