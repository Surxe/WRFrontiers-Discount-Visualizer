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
let moduleTypeCache = null;
let moduleCategoryCache = null;

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

export function getModuleCategoryName(categoryId) {
	const categories = fetchModuleCategories();
	const category = categories[categoryId];
	return category?.name?.en || 'Unknown';
}

export function getModuleCategorySlug(categoryId) {
	// Map category ID to URL slug
	const slugMap = {
		'DA_ModuleCategory_Ability.0': 'ability',
		'DA_ModuleCategory_Chassis.0': 'chassis',
		'DA_ModuleCategory_Shoulder.0': 'shoulder',
		'DA_ModuleCategory_Torso.0': 'torso',
		'DA_ModuleCategory_Weapon.0': 'weapon',
	};
	return slugMap[categoryId] || 'unknown';
}

export function getCategoryIdFromSlug(slug) {
	const slugMap = {
		'ability': 'DA_ModuleCategory_Ability.0',
		'chassis': 'DA_ModuleCategory_Chassis.0',
		'shoulder': 'DA_ModuleCategory_Shoulder.0',
		'torso': 'DA_ModuleCategory_Torso.0',
		'weapon': 'DA_ModuleCategory_Weapon.0',
	};
	return slugMap[slug] || null;
}

export function getModuleData(moduleId) {
	const modules = fetchModules();
	return modules[moduleId] || null;
}

export function getModuleName(module) {
	return module?.name?.en || module?.id || 'Unknown';
}

export function getModuleIconPath(module) {
	return module?.inventory_icon_path || null;
}

export function getModuleCategoryForModule(module) {
	const moduleTypes = fetchModuleTypes();
	const moduleTypeRef = module?.module_type_ref;
	
	if (!moduleTypeRef) {
		return null;
	}

	// Extract the type ID from the ref (e.g., "OBJID_ModuleType::DA_ModuleType_Chassis.0" -> "DA_ModuleType_Chassis.0")
	const typeId = moduleTypeRef.includes('::') 
		? moduleTypeRef.split('::')[1] 
		: moduleTypeRef;

	const moduleType = moduleTypes[typeId];
	if (!moduleType) {
		return null;
	}

	const categoryRef = moduleType.module_category_ref;
	if (!categoryRef) {
		return null;
	}

	// Extract the category ID from the ref
	const categoryId = categoryRef.includes('::')
		? categoryRef.split('::')[1]
		: categoryRef;

	return categoryId;
}

export function fetchAllModulesWithCategory() {
	const modules = fetchModules();
	const moduleTypes = fetchModuleTypes();
	const categories = fetchModuleCategories();

	const result = [];

	for (const [moduleId, module] of Object.entries(modules)) {
		const categoryId = getModuleCategoryForModule(module);
		const categoryName = categoryId ? getModuleCategoryName(categoryId) : 'Unknown';
		
		result.push({
			id: moduleId,
			name: getModuleName(module),
			iconPath: getModuleIconPath(module),
			categoryId: categoryId,
			categoryName: categoryName,
		});
	}

	return result;
}

export function fetchModulesByCategory(categoryId) {
	const allModules = fetchAllModulesWithCategory();
	return allModules.filter(m => m.categoryId === categoryId);
}
