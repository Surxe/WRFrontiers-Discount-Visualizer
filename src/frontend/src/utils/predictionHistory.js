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
		if (fs.existsSync(path.join(dir, 'predictions_history', 'index.json'))) {
			return dir;
		}
	}
	return candidates[0];
}

let indexCache = null;

// The per-week prediction history index: a rolling `scoreboard` plus one row
// per archived week (see build_prediction_history in the backend). Returns
// `{ scoreboard, weeks }`, or empty defaults if the file is absent.
export function fetchPredictionHistoryIndex() {
	if (indexCache) {
		return indexCache;
	}
	const dataDir = resolveDataDir();
	try {
		const content = fs.readFileSync(path.join(dataDir, 'predictions_history', 'index.json'), 'utf-8');
		indexCache = JSON.parse(content);
	} catch (e) {
		console.warn('predictions_history/index.json not found or unreadable:', e.message);
		indexCache = { scoreboard: null, weeks: [] };
	}
	return indexCache;
}

// One week's frozen snapshot, by the `file` path stored in an index row.
export function fetchPredictionSnapshot(file) {
	const dataDir = resolveDataDir();
	try {
		const content = fs.readFileSync(path.join(dataDir, file), 'utf-8');
		return JSON.parse(content);
	} catch (e) {
		console.error(`Error reading prediction snapshot ${file}:`, e.message);
		return null;
	}
}
