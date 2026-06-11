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
