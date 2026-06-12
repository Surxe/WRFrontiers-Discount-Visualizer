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
		if (fs.existsSync(path.join(dir, 'discount_data.json'))) {
			return dir;
		}
	}
	console.warn('discount_data.json not found. Tried:', candidates.join(', '));
	return candidates[0];
}

let reverseLookupCache = null;

export function fetchDiscountHistory() {
	if (reverseLookupCache) {
		return reverseLookupCache;
	}

	const dataDir = resolveDataDir();
	try {
		const filePath = path.join(dataDir, 'discount_data.json');
		const content = fs.readFileSync(filePath, 'utf-8');
		reverseLookupCache = JSON.parse(content);
		return reverseLookupCache;
	} catch (e) {
		console.error('Error reading discount_data.json:', e);
		return { virtualBots: {}, modules: {} };
	}
}

export function getModuleDiscountWeeks(moduleId) {
	const history = fetchDiscountHistory();
	const moduleRef = `OBJID_Module::${moduleId}`;
	const moduleData = history.modules[moduleRef];
	// Handle both old format (array) and new format (object with weeks field)
	if (Array.isArray(moduleData)) {
		return moduleData;
	}
	return moduleData?.weeks || [];
}

export function getVbotDiscountWeeks(vbotId) {
	const history = fetchDiscountHistory();
	const vbotRef = `OBJID_VirtualBot::${vbotId}`;
	const vbotData = history.virtualBots[vbotRef];
	// Handle both old format (array) and new format (object with weeks field)
	if (Array.isArray(vbotData)) {
		return vbotData;
	}
	return vbotData?.weeks || [];
}

export function getModuleVirtualBots(moduleId) {
	const history = fetchDiscountHistory();
	const moduleRef = `OBJID_Module::${moduleId}`;
	const moduleData = history.modules[moduleRef];
	// Only return virtual_bots if it exists in the new format
	if (moduleData && typeof moduleData === 'object' && !Array.isArray(moduleData)) {
		return moduleData.virtual_bots || [];
	}
	return [];
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

export function calculateWeeksAgo(fromDate, toDate) {
	if (!fromDate || !toDate) return null;
	
	const from = new Date(fromDate);
	const to = new Date(toDate);
	
	// Calculate the difference in weeks
	const diffTime = to - from;
	const diffDays = diffTime / (1000 * 60 * 60 * 24);
	const weeksAgo = Math.floor(diffDays / 7);
	
	return weeksAgo;
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

export function transformToWeekCentric(items) {
	// Transform item-centric data to week-centric data
	const weekMap = new Map();
	
	items.forEach(item => {
		item.discountWeeks.forEach(week => {
			if (!weekMap.has(week)) {
				weekMap.set(week, []);
			}
			weekMap.get(week).push({
				id: item.id,
				name: item.name,
				iconPath: item.iconPath
			});
		});
	});
	
	// Convert to array and sort weeks chronologically (oldest first)
	const weekArray = Array.from(weekMap.entries()).map(([week, items]) => ({
		week,
		items,
		itemsCount: items.length
	})).sort((a, b) => new Date(a.week) - new Date(b.week));
	
	return weekArray;
}
