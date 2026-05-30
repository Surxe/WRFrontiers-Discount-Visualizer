const CORE_MODULE_CATEGORIES = [
  'DA_ModuleCategory_Chassis.0',
  'DA_ModuleCategory_Torso.0',
  'DA_ModuleCategory_Shoulder.0',
];

const CORE_CATEGORY_PRIORITY = [
  'DA_ModuleCategory_Chassis.0',
  'DA_ModuleCategory_Torso.0',
  'DA_ModuleCategory_Shoulder.0',
];

export function getModuleCategoryId(module, ModuleTypeDB, parseRef) {
  const typeRef = parseRef(module.module_type_ref);
  const moduleType = typeRef ? ModuleTypeDB[typeRef] : null;
  return moduleType ? parseRef(moduleType.module_category_ref) : null;
}

export function isCoreModule(module, ModuleTypeDB, parseRef) {
  const categoryId = getModuleCategoryId(module, ModuleTypeDB, parseRef);
  return categoryId != null && CORE_MODULE_CATEGORIES.includes(categoryId);
}

function rgbaToCss(rgba) {
  if (!rgba) return null;
  const r = Math.round((rgba.R ?? 0) * 255);
  const g = Math.round((rgba.G ?? 0) * 255);
  const b = Math.round((rgba.B ?? 0) * 255);
  const a = rgba.A ?? 1;
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function tagDisplayName(tag) {
  if (!tag?.name) return tag?.id ?? '';
  if (typeof tag.name === 'string') return tag.name;
  return tag.name.en || tag.name.Key || tag.id;
}

/**
 * Pick one core module from a virtual bot's core_module_refs (chassis preferred).
 */
export function findCoreModuleForVbot(vbotId, databases, parseRef) {
  const { VirtualBotDB, ModuleDB, ModuleTypeDB } = databases;
  const bot = VirtualBotDB[vbotId];
  if (!bot?.core_module_refs?.length) {
    throw new Error(`Virtual bot ${vbotId} has no core_module_refs`);
  }

  const coreModules = bot.core_module_refs
    .map((ref) => ModuleDB[parseRef(ref)])
    .filter((module) => module && isCoreModule(module, ModuleTypeDB, parseRef));

  if (coreModules.length === 0) {
    throw new Error(`Virtual bot ${vbotId} has no chassis/torso/shoulder core modules`);
  }

  coreModules.sort((a, b) => {
    const catA = getModuleCategoryId(a, ModuleTypeDB, parseRef);
    const catB = getModuleCategoryId(b, ModuleTypeDB, parseRef);
    return (
      CORE_CATEGORY_PRIORITY.indexOf(catA) - CORE_CATEGORY_PRIORITY.indexOf(catB)
    );
  });

  return coreModules[0];
}

/**
 * Faction badge icon + first module tag for a virtual bot (build fails if >1 tag).
 */
export function resolveVbotMeta(vbotId, databases, parseRef) {
  const { FactionDB, ModuleTagDB } = databases;
  const coreModule = findCoreModuleForVbot(vbotId, databases, parseRef);

  const tags = coreModule.module_tags_refs ?? [];
  if (tags.length > 1) {
    throw new Error(
      `Virtual bot ${vbotId} core module ${coreModule.id} has ${tags.length} module_tags_refs (expected at most 1)`
    );
  }

  let faction_icon_path = null;
  if (coreModule.faction_ref) {
    const factionId = parseRef(coreModule.faction_ref);
    const faction = factionId ? FactionDB[factionId] : null;
    faction_icon_path = faction?.badge?.image_path ?? null;
    if (!faction_icon_path) {
      throw new Error(
        `Virtual bot ${vbotId} core module ${coreModule.id}: faction ${factionId} has no badge.image_path`
      );
    }
  }

  let tag_icon_path = null;
  let tag_label = null;
  let tag_text_color = null;
  let tag_background = null;

  if (tags.length === 1) {
    const tagId = parseRef(tags[0]);
    const tag = tagId ? ModuleTagDB[tagId] : null;
    if (!tag) {
      throw new Error(
        `Virtual bot ${vbotId} core module ${coreModule.id}: unknown module tag ${tagId}`
      );
    }
    tag_label = tagDisplayName(tag);
    tag_text_color = tag.text_color?.Hex ?? null;
    tag_background = rgbaToCss(tag.background_color?.RGBA);
    // ModuleTag objects have no image_path in game data
    tag_icon_path = tag.icon_path ?? null;
  }

  return {
    faction_icon_path,
    tag_icon_path,
    tag_label,
    tag_text_color,
    tag_background,
    core_module_id: coreModule.id,
  };
}

export function buildVbotMetaById(vbotIds, databases, parseRef) {
  const metaById = {};
  for (const vbotId of vbotIds) {
    if (!vbotId) continue;
    metaById[vbotId] = resolveVbotMeta(vbotId, databases, parseRef);
  }
  return metaById;
}
