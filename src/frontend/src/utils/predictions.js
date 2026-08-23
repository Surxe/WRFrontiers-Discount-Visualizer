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
		if (fs.existsSync(path.join(dir, 'predictions.json'))) {
			return dir;
		}
	}
	console.warn('predictions.json not found. Tried:', candidates.join(', '));
	return candidates[0];
}

let predictionsCache = null;

export function fetchPredictions() {
	if (predictionsCache) {
		return predictionsCache;
	}

	const dataDir = resolveDataDir();
	try {
		const filePath = path.join(dataDir, 'predictions.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		predictionsCache = JSON.parse(content);
		return predictionsCache;
	} catch (e) {
		console.error('Error reading predictions.json:', e);
		return null;
	}
}
