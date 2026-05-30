export const isTitan = (item) =>
  item.group && item.group.toLowerCase().startsWith('titan-');

export const categorize = (item) => {
  const cat = (item.category || '').toLowerCase();
  if (cat.includes('chassis')) return 'chassis';
  if (cat.includes('shoulder')) return 'shoulder';
  if (cat.includes('torso')) return 'torso';
  return null;
};

export const processBots = (botItems) => {
  const botParts = botItems.filter((i) => categorize(i) !== null);
  const botsMap = {};
  for (const part of botParts) {
    const vbot = part.vbot || part.id;
    if (!botsMap[vbot]) {
      botsMap[vbot] = { torso: [], shoulder: [], chassis: [], rarity: part.rarity };
    }
    const cat = categorize(part);
    if (cat && botsMap[vbot][cat].length === 0) {
      botsMap[vbot][cat].push(part);
    }
  }
  return Object.values(botsMap);
};

export const getWeaponAndGear = (colItems) => {
  const lightWep = colItems.filter(
    (i) => i.group && i.group.toLowerCase().includes('light')
  );
  const heavyWep = colItems.filter(
    (i) => i.group && i.group.toLowerCase().includes('heavy')
  );
  const supply = colItems.filter(
    (i) => i.group && i.group.toLowerCase().includes('supply')
  );
  const cycle = colItems.filter(
    (i) => i.group && i.group.toLowerCase().includes('cycle')
  );
  return { lightWep, heavyWep, supply, cycle };
};

export const countStandardRows = (standardBots, stdWeapons) =>
  Math.max(
    standardBots.length,
    stdWeapons.lightWep.length,
    stdWeapons.heavyWep.length,
    stdWeapons.supply.length,
    stdWeapons.cycle.length
  );

export const countTitanRows = (titanBots, titanWeapons) =>
  Math.max(titanBots.length, titanWeapons.length);
