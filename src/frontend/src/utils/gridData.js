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
  const botIds = new Set(bots.map(b => b.vbot));
  const weaponsByVbot = new Map();
  const unmatchedWeapons = new Set(weapons);
  
  for (const weapon of weapons) {
    let hasPreference = false;
    const prefs = Array.isArray(weapon.preferred_vbot) ? weapon.preferred_vbot : (weapon.preferred_vbot ? [weapon.preferred_vbot] : []);
    
    for (const vbot of prefs) {
      if (botIds.has(vbot)) {
        if (!weaponsByVbot.has(vbot)) {
          weaponsByVbot.set(vbot, []);
        }
        weaponsByVbot.get(vbot).push(weapon);
        hasPreference = true;
      }
    }
    
    if (hasPreference) {
      unmatchedWeapons.delete(weapon);
    }
  }
  
  // Assign weapons to their preferred bots
  const assignedWeapons = new Set();
  const botWeapons = bots.map(bot => {
    const botId = bot.vbot;
    const preferredWeapons = weaponsByVbot.get(botId) || [];
    const assigned = preferredWeapons[0] || null;
    if (assigned) {
       assignedWeapons.add(assigned.id);
    }
    return assigned;
  });
  
  // Fill remaining slots with unmatched weapons
  const remainingUnmatched = Array.from(unmatchedWeapons);
  let unmatchedIndex = 0;
  
  for (let i = 0; i < botWeapons.length; i++) {
    if (!botWeapons[i] && unmatchedIndex < remainingUnmatched.length) {
      botWeapons[i] = remainingUnmatched[unmatchedIndex];
      assignedWeapons.add(remainingUnmatched[unmatchedIndex].id);
      unmatchedIndex++;
    }
  }
  
  // Create slots for all remaining unplaced weapons, replacing duplicates if the column is full
  const allWeapons = new Set(weapons);
  const unplacedWeapons = Array.from(allWeapons).filter(w => !assignedWeapons.has(w.id));
  const targetLength = Math.max(bots.length, weapons.length);
  
  for (const w of unplacedWeapons) {
    if (botWeapons.length < targetLength) {
      botWeapons.push(w);
      assignedWeapons.add(w.id);
    } else {
      const counts = {};
      for (let i = 0; i < botWeapons.length; i++) {
        if (botWeapons[i]) {
          counts[botWeapons[i].id] = (counts[botWeapons[i].id] || 0) + 1;
        }
      }
      
      const duplicateId = Object.keys(counts).find(id => counts[id] > 1);
      
      if (duplicateId) {
        const lastIndex = botWeapons.map(bw => bw ? bw.id : null).lastIndexOf(duplicateId);
        botWeapons[lastIndex] = w;
        assignedWeapons.add(w.id);
      } else {
        throw new Error(`Cannot place ${w.name} (${w.id}): No duplicate modules to replace, and grid column is full!`);
      }
    }
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
