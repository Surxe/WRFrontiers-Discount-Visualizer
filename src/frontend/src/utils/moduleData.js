import fs from 'fs';
import path from 'path';

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
	console.warn('WRFrontiersDB-Data Objects not found. Tried:', candidates.join(', '));
	return candidates[0];
}

let moduleCache = null;
let moduleGroupCache = null;
let moduleTypeCache = null;
let moduleCategoryCache = null;
let catIconsCache = null;

export function fetchCatIcons() {
	if (catIconsCache) {
		return catIconsCache;
	}

	const frontendDataDir = path.resolve('public/data');
	try {
		const columnsList = JSON.parse(fs.readFileSync(path.join(frontendDataDir, 'columns.json'), 'utf-8'));
		const dataDir = resolveObjectsDir();

		const ModuleSocketTypeDB = JSON.parse(fs.readFileSync(path.join(dataDir, 'ModuleSocketType.json'), 'utf-8'));
		const ModuleCategoryDB = JSON.parse(fs.readFileSync(path.join(dataDir, 'ModuleCategory.json'), 'utf-8'));

		const parseRef = (ref) => {
			if (!ref) return null;
			const parts = ref.split('::');
			return parts.length > 1 ? parts[1] : parts[0];
		};

		catIconsCache = columnsList.map(colRef => {
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

		return catIconsCache;
	} catch (e) {
		console.error('Error reading columns.json:', e);
		return [];
	}
}

export function fetchModules() {
	if (moduleCache) {
		return moduleCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'Module.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		moduleCache = JSON.parse(content);
		return moduleCache;
	} catch (e) {
		console.error('Error reading Module.json:', e);
		return {};
	}
}

export function fetchModuleGroups() {
	if (moduleGroupCache) {
		return moduleGroupCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'ModuleGroup.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		moduleGroupCache = JSON.parse(content);
		return moduleGroupCache;
	} catch (e) {
		console.error('Error reading ModuleGroup.json:', e);
		return {};
	}
}

export function fetchModuleTypes() {
	if (moduleTypeCache) {
		return moduleTypeCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'ModuleType.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		moduleTypeCache = JSON.parse(content);
		return moduleTypeCache;
	} catch (e) {
		console.error('Error reading ModuleType.json:', e);
		return {};
	}
}

export function fetchModuleCategories() {
	if (moduleCategoryCache) {
		return moduleCategoryCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'ModuleCategory.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		moduleCategoryCache = JSON.parse(content);
		return moduleCategoryCache;
	} catch (e) {
		console.error('Error reading ModuleCategory.json:', e);
		return {};
	}
}

let moduleRarityCache = null;

export function fetchModuleRarities() {
	if (moduleRarityCache) {
		return moduleRarityCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'ModuleRarity.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		moduleRarityCache = JSON.parse(content);
		return moduleRarityCache;
	} catch (e) {
		console.error('Error reading ModuleRarity.json:', e);
		return {};
	}
}

export function getModuleGroupName(groupId) {
	const groups = fetchModuleGroups();
	const group = groups[groupId];
	return group?.name?.en || 'Unknown';
}

export function getModuleGroupSlug(groupId) {
	// ModuleGroup IDs are already URL-friendly (e.g., "supply-gear", "heavy-weapon")
	return groupId || 'unknown';
}

export function getGroupIdFromSlug(slug) {
	// ModuleGroup IDs are already URL-friendly
	return slug || null;
}

export function getModuleData(moduleId) {
	const modules = fetchModules();
	return modules[moduleId] || null;
}

export function getModuleName(module) {
	if (module?.name?.en) {
		return module.name.en;
	}
	// Parse name from ID (e.g., "DA_Module_Weapon_Shredder.0" -> "Shredder")
	const id = module?.id || '';
	if (id) {
		const parts = id.split('_');
		if (parts.length >= 3) {
			// Remove version suffix (e.g., ".0", ".1")
			const lastPart = parts[parts.length - 1].split('.')[0];
			// If last part is a number, use the second-to-last part
			if (!isNaN(parseInt(lastPart))) {
				return parts[parts.length - 2];
			}
			return lastPart;
		}
	}
	return id || 'Unknown';
}

export function getModuleIconPath(module) {
	return module?.inventory_icon_path || null;
}

export function getModuleGroupForModule(module) {
	const groupRef = module?.module_group_ref;
	
	if (!groupRef) {
		return null;
	}

	// Extract the group ID from the ref (e.g., "OBJID_ModuleGroup::supply-gear" -> "supply-gear")
	const groupId = groupRef.includes('::')
		? groupRef.split('::')[1]
		: groupRef;

	return groupId;
}

/** Groups that need their name appended to the module's base name. */
const SUFFIX_GROUPS = new Set([
	'non-titan-torsos',
	'non-titan-shoulder',
	'non-titan-chassis',
	'titan-torsos',
	'titan-shoulder',
	'titan-chassis',
]);

/**
 * Returns the display name for a module, appending the group label
 * (e.g. "Torso", "Shoulder", "Chassis") for groups where the base
 * name alone is ambiguous (e.g. "Wyrm" -> "Wyrm Torso").
 *
 * @param {object} module - raw Module.json entry
 * @returns {string}
 */
export function getModuleDisplayName(module) {
	if (!module) return '';
	const baseName = module.name?.en || module.name || '';
	const groupId = getModuleGroupForModule(module);
	if (!groupId || !SUFFIX_GROUPS.has(groupId)) return baseName;

	// Use ModuleCategory name if available (e.g. "Chassis" instead of "Titan Chassis")
	const typeRef = module.module_type_ref;
	if (typeRef) {
		const typeId = typeRef.includes('::') ? typeRef.split('::')[1] : typeRef;
		const types = fetchModuleTypes();
		const categoryRef = types[typeId]?.module_category_ref;
		if (categoryRef) {
			const catId = categoryRef.includes('::') ? categoryRef.split('::')[1] : categoryRef;
			const categories = fetchModuleCategories();
			const categoryLabel = categories[catId]?.name?.en || '';
			if (categoryLabel && !baseName.toLowerCase().includes(categoryLabel.toLowerCase())) {
				return `${baseName} ${categoryLabel}`;
			}
		}
	}

	// Fallback to group name
	const groups = fetchModuleGroups();
	const groupLabel = groups[groupId]?.name?.en || '';
	if (!groupLabel || baseName.toLowerCase().includes(groupLabel.toLowerCase())) return baseName;
	return `${baseName} ${groupLabel}`;
}

export function fetchAllModulesWithGroup() {
	const modules = fetchModules();
	const groups = fetchModuleGroups();

	const result = [];

	for (const [moduleId, module] of Object.entries(modules)) {
		// Filter to only production-ready modules
		if (module.production_status !== 'Ready') {
			continue;
		}

		const groupId = getModuleGroupForModule(module);
		const group = groupId ? groups[groupId] : null;
		
		result.push({
			id: moduleId,
			name: getModuleName(module),
			iconPath: getModuleIconPath(module),
			groupId: groupId,
			groupName: group?.name?.en || 'Unknown',
			isTitan: group?.titan || false,
			isVirtualBotModule: group?.virtual_bot_module || false,
			sortOrder: group?.sort_order || 0,
			groupDescription: group?.description?.en || '',
		});
	}

	return result;
}

export function fetchModulesByGroup(groupId) {
	const allModules = fetchAllModulesWithGroup();
	return allModules.filter(m => m.groupId === groupId);
}
