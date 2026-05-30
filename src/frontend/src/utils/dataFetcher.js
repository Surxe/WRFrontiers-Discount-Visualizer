import fs from 'fs';
import path from 'path';
import { getCurrentOrLatestWeek } from './dateValidator.js';
import { buildVbotMetaById } from './vbotMeta.js';

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

  let targetFilename = filename;
  if (!targetFilename) {
    const manifest = readJson('weeks.json', frontendDataDir);
    if (manifest && manifest.weeks && manifest.weeks.length > 0) {
      const currentOrLatest = getCurrentOrLatestWeek(manifest.weeks);
      targetFilename = currentOrLatest ? currentOrLatest.file : manifest.weeks[0].file;
    } else {
      targetFilename = 'discounts.json'; // Fallback just in case
    }
  }

  const discountsOutput = readJson(targetFilename, frontendDataDir);
  const itemsArray = Array.isArray(discountsOutput.items) ? discountsOutput.items : [];
  const dateRange = discountsOutput.date_range || "";

  if (itemsArray.length === 0) {
    return { dateRange, items: [], shopCards: {}, catIcons: {}, vbotMetaById: {} };
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
  const CharacterPresetDB = readJson('CharacterPreset.json');
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

    // Resolve Virtual Bot directly from module's virtual_bot_ref field
    const vbotRef = parseRef(module.virtual_bot_ref);
    const vbotObj = vbotRef ? VirtualBotDB[vbotRef] : null;
    const vbotIconPath = vbotObj?.icon_path || null;

    return {
      ...item,
      name: item.name,
      icon_path: module.inventory_icon_path,
      rarity: baseRarityRef,
      category: categoryRef,
      group: groupRef,
      vbot: vbotRef,
      vbot_icon_path: vbotIconPath,
      preferred_vbot: null // Will be set after we know which vbots are in the data
    };
  }).filter(item => !item._missing);

  // Build module-to-vbot mapping for ALL virtual bots in the database
  // This ensures weapons can be matched to their vbots even if the bot itself isn't discounted
  const moduleToVbotMap = new Map();
  
  // For each virtual bot in the database, extract modules from its factory presets
  for (const vbotId of Object.keys(VirtualBotDB)) {
    const vbotData = VirtualBotDB[vbotId];
    if (vbotData && vbotData.factory_preset_refs) {
      for (const presetRef of vbotData.factory_preset_refs) {
        const presetId = parseRef(presetRef);
        const preset = CharacterPresetDB[presetId];
        if (preset && preset.modules) {
          for (const moduleData of preset.modules) {
            const moduleId = parseRef(moduleData.module_ref);
            moduleToVbotMap.set(moduleId, vbotId);
          }
        }
      }
    }
  }
  
  // Now set preferred_vbot for items that match the mapping
  for (const item of enrichedDiscounts) {
    if (moduleToVbotMap.has(item.id)) {
      item.preferred_vbot = moduleToVbotMap.get(item.id);
    }
  }

  // Identify which virtual bots are in the current discount data
  const botParts = enrichedDiscounts.filter(item => ['Chassis', 'Torso', 'Shoulder'].some(c => item.category && item.category.includes(c)));

  // Grouping by vbot for chassis/torso/shoulder and validating rarity
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

  const vbotIdsInDiscount = [...new Set(botParts.map((p) => p.vbot).filter(Boolean))];
  const vbotMetaById = buildVbotMetaById(vbotIdsInDiscount, databases, parseRef);

  return {
    dateRange,
    items: enrichedDiscounts,
    shopCards: ShopCardDB,
    catIcons,
    vbotMetaById,
  };
}
