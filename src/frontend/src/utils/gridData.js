export const isTitan = (item) =>
  item.group && item.group.toLowerCase().startsWith('titan-');

export const categorize = (item) => {
  const cat = (item.category || '').toLowerCase();
  if (cat.includes('chassis')) return 'chassis';
  if (cat.includes('shoulder')) return 'shoulder';
  if (cat.includes('torso')) return 'torso';
  return null;
};

export const assignWeaponTypeToBots = (bots, weapons) => {
  // Assign a single weapon type to bots based on preferred_vbot
  const botIds = new Set(bots.map(b => b.vbot));
  const weaponsByVbot = new Map();
  const unmatchedWeapons = [];
  
  for (const weapon of weapons) {
    // Only consider preferred_vbot if that bot exists in the current list
    if (weapon.preferred_vbot && botIds.has(weapon.preferred_vbot)) {
      if (!weaponsByVbot.has(weapon.preferred_vbot)) {
        weaponsByVbot.set(weapon.preferred_vbot, []);
      }
      weaponsByVbot.get(weapon.preferred_vbot).push(weapon);
    } else {
      unmatchedWeapons.push(weapon);
    }
  }
  
  // Assign weapons to their preferred bots
  const assignedWeapons = new Set();
  const botWeapons = bots.map(bot => {
    // Use the vbot ID stored in the bot object
    const botId = bot.vbot;
    const preferredWeapons = weaponsByVbot.get(botId) || [];
    const assigned = preferredWeapons.slice(0, 1); // Take first preferred weapon
    assigned.forEach(w => assignedWeapons.add(w.id));
    return assigned[0] || null;
  });
  
  // Fill remaining slots with unmatched weapons
  const remainingUnmatched = unmatchedWeapons.filter(w => !assignedWeapons.has(w.id));
  let unmatchedIndex = 0;
  
  for (let i = 0; i < botWeapons.length; i++) {
    if (!botWeapons[i] && unmatchedIndex < remainingUnmatched.length) {
      botWeapons[i] = remainingUnmatched[unmatchedIndex];
      assignedWeapons.add(remainingUnmatched[unmatchedIndex].id);
      unmatchedIndex++;
    }
  }
  
  // Create slots for all remaining unmatched weapons
  while (unmatchedIndex < remainingUnmatched.length) {
    botWeapons.push(remainingUnmatched[unmatchedIndex]);
    unmatchedIndex++;
  }
  
  return botWeapons;
};

export const processBots = (botItems, vbotMetaById = {}) => {
  const botParts = botItems.filter((i) => categorize(i) !== null);
  const botsMap = {};
  for (const part of botParts) {
    const vbot = part.vbot || part.id;
    if (!botsMap[vbot]) {
      botsMap[vbot] = {
        torso: [],
        shoulder: [],
        chassis: [],
        rarity: part.rarity,
        icon_path: part.vbot_icon_path,
        name: part.name,
        vbot,
        ...(vbotMetaById[vbot] || {}),
      };
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
