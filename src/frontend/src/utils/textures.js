/**
 * Resolve WRFrontiersDB-Data texture URLs for static assets.
 */

export function getTexturePath(uePath, baseUrl = '') {
  if (!uePath) return '';
  const iconPath = uePath.startsWith('/') ? uePath : `/${uePath}`;
  return `${baseUrl}WRFrontiersDB-Data/textures${iconPath}.png`;
}

/** Resolve the currency icon URL for 'salvage' (Alloys) or 'intel'. */
export function getCurrencyIconUrl(currency, baseUrl = '') {
  const file = currency === 'intel' ? 'T_IntelLarge.png' : 'T_AlloysLarge.png';
  return `${baseUrl}WRFrontiersDB-Data/textures/WRFrontiers/Content/Sparrow/UI/Textures/Meta/Currency/${file}`;
}

/** Always uses horizontal shop-card backgrounds (DA_CardSize_SH.0). */
export function getRarityBackgroundUrl(rarityId, shopCards, baseUrl = '') {
  if (!rarityId) return '';
  const bgObjId = `OBJID_Rarity::${rarityId}`;
  const bgObj = shopCards['DA_CardSize_SH.0']?.backgrounds;
  if (!bgObj?.[bgObjId]) return '';
  return getTexturePath(bgObj[bgObjId], baseUrl);
}
