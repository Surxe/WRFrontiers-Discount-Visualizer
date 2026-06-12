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

export function getLastDiscountBeforeDate(discountWeeks, currentDate) {
	if (!discountWeeks || discountWeeks.length === 0) {
		return null;
	}
	
	// Sort weeks in descending order (most recent first)
	const sortedWeeks = [...discountWeeks].sort((a, b) => {
		return new Date(b) - new Date(a);
	});
	
	// Find the most recent week before the current date
	const currentWeekDate = new Date(currentDate);
	for (const week of sortedWeeks) {
		const weekDate = new Date(week);
		if (weekDate < currentWeekDate) {
			return week;
		}
	}
	
	return null;
}

export function formatDiscountDate(dateStr) {
	if (!dateStr) return 'Never';
	const date = new Date(dateStr);
	return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export function extractDiscountedItemsFromGrid(gridData, currentWeekSlug) {
	const items = [];
	
	// Category mapping based on columns.json indices
	// 1: VirtualBots, 5: Light Weapon, 6: Heavy Weapon, 7: Supply Gear, 8: Cycle Gear
	const categoryMap = {
		'1': 'Bot',
		'5': 'Light Wep',
		'6': 'Heavy Wep',
		'7': 'Supply Gear',
		'8': 'Cycle Gear'
	};
	
	// Process both standard and titan rows
	const allRows = [...(gridData.standardRows || []), ...(gridData.titanRows || [])];
	
	for (const row of allRows) {
		for (const [colIndex, cellData] of Object.entries(row.cells || {})) {
			const category = categoryMap[colIndex];
			if (!category) continue; // Skip columns we don't want (torso, shoulder, chassis)
			
			if (cellData && cellData.id) {
				const itemType = cellData.ref?.startsWith('OBJID_VirtualBot') ? 'vbot' : 'module';
				items.push({
					id: cellData.id,
					name: cellData.name,
					iconPath: cellData.icon_path,
					category: category,
					itemType: itemType,
					ref: cellData.ref
				});
			}
		}
	}
	
	// Remove duplicates (same item can appear in multiple rows)
	const uniqueItems = [];
	const seenIds = new Set();
	
	for (const item of items) {
		if (!seenIds.has(item.id)) {
			seenIds.add(item.id);
			uniqueItems.push(item);
		}
	}
	
	return uniqueItems;
}
