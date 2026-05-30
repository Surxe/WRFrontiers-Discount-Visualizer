const CORE_MODULE_CATEGORIES = [
  'DA_ModuleCategory_Chassis.0',
  'DA_ModuleCategory_Torso.0',
  'DA_ModuleCategory_Shoulder.0',
];

/** Torso carries module_classes_refs; chassis/shoulder are fallbacks for faction only. */
const META_CORE_CATEGORY_PRIORITY = [
  'DA_ModuleCategory_Torso.0',
  'DA_ModuleCategory_Chassis.0',
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

/**
 * Pick one core module from a virtual bot's core_module_refs (torso preferred).
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
      META_CORE_CATEGORY_PRIORITY.indexOf(catA) -
      META_CORE_CATEGORY_PRIORITY.indexOf(catB)
    );
  });

  return coreModules[0];
}

function assertAtMostOneClassPerCorePart(vbotId, coreModules) {
  for (const module of coreModules) {
    const classes = module.module_classes_refs ?? [];
    if (classes.length > 1) {
      throw new Error(
        `Virtual bot ${vbotId} core module ${module.id} has ${classes.length} module_classes_refs (expected at most 1)`
      );
    }
  }
}

function resolveCharacterClassIcon(module, databases, parseRef) {
  const { ModuleClassDB, CharacterClassDB } = databases;
  const classRefs = module.module_classes_refs ?? [];
  if (classRefs.length === 0) return null;

  const moduleClassId = parseRef(classRefs[0]);
  const moduleClass = moduleClassId ? ModuleClassDB[moduleClassId] : null;
  if (!moduleClass?.character_class_ref) {
    throw new Error(
      `Module ${module.id}: ModuleClass ${moduleClassId} missing character_class_ref`
    );
  }

  const characterClassId = parseRef(moduleClass.character_class_ref);
  const characterClass = characterClassId
    ? CharacterClassDB[characterClassId]
    : null;
  const iconPath = characterClass?.badge?.image_path ?? null;
  if (!iconPath) {
    throw new Error(
      `Module ${module.id}: CharacterClass ${characterClassId} has no badge.image_path`
    );
  }

  return iconPath;
}

/**
 * Faction badge + CharacterClass icon from torso core module (build fails if >1 class ref).
 */
export function resolveVbotMeta(vbotId, databases, parseRef) {
  const { VirtualBotDB, ModuleDB, ModuleTypeDB, FactionDB } = databases;
  const bot = VirtualBotDB[vbotId];
  const coreModules = bot.core_module_refs
    .map((ref) => ModuleDB[parseRef(ref)])
    .filter((module) => module && isCoreModule(module, ModuleTypeDB, parseRef));

  assertAtMostOneClassPerCorePart(vbotId, coreModules);

  const coreModule = findCoreModuleForVbot(vbotId, databases, parseRef);

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

  const class_icon_path = resolveCharacterClassIcon(
    coreModule,
    databases,
    parseRef
  );

  return {
    faction_icon_path,
    class_icon_path,
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
