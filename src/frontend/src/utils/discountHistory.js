import fs from 'fs';
import path from 'path';

function resolveDataDir() {
	if (process.env.DATA_DIR) {
		return process.env.DATA_DIR;
	}
	const candidates = [
		path.resolve('public/data'),
		path.resolve('../../public/data'),
		path.resolve('../../../public/data'),
	];
	for (const dir of candidates) {
		if (fs.existsSync(path.join(dir, 'discount_reverse_lookup.json'))) {
			return dir;
		}
	}
	console.warn('discount_reverse_lookup.json not found. Tried:', candidates.join(', '));
	return candidates[0];
}

let reverseLookupCache = null;

export function fetchDiscountHistory() {
	if (reverseLookupCache) {
		return reverseLookupCache;
	}

	const dataDir = resolveDataDir();
	try {
		const filePath = path.join(dataDir, 'discount_reverse_lookup.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		reverseLookupCache = JSON.parse(content);
		return reverseLookupCache;
	} catch (e) {
		console.error('Error reading discount_reverse_lookup.json:', e);
		return { virtualBots: {}, modules: {} };
	}
}

export function getModuleDiscountWeeks(moduleId) {
	const history = fetchDiscountHistory();
	const moduleRef = `OBJID_Module::${moduleId}`;
	return history.modules[moduleRef] || [];
}

export function getVbotDiscountWeeks(vbotId) {
	const history = fetchDiscountHistory();
	const vbotRef = `OBJID_VirtualBot::${vbotId}`;
	return history.virtualBots[vbotRef] || [];
}
