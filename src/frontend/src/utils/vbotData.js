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
		if (fs.existsSync(path.join(dir, 'VirtualBot.json'))) {
			return dir;
		}
	}
	console.warn('WRFrontiersDB-Data Objects not found. Tried:', candidates.join(', '));
	return candidates[0];
}

let vbotCache = null;

export function fetchAllVbots() {
	if (vbotCache) {
		return vbotCache;
	}

	const objectsDir = resolveObjectsDir();
	try {
		const filePath = path.join(objectsDir, 'VirtualBot.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		vbotCache = JSON.parse(content);
		return vbotCache;
	} catch (e) {
		console.error('Error reading VirtualBot.json:', e);
		return {};
	}
}

export function getVbotData(vbotId) {
	const vbots = fetchAllVbots();
	return vbots[vbotId] || null;
}

export function getVbotName(vbot) {
	return vbot?.name?.en || vbot?.id || 'Unknown';
}

export function getVbotIconPath(vbot) {
	return vbot?.icon_path || null;
}

export function getVbotCharacterType(vbot) {
	return vbot?.character_type || 'Unknown';
}
