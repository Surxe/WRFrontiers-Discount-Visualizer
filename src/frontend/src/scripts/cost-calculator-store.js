class CostCalculatorStore extends EventTarget {
  constructor() {
    super();
    this.shoppingList = [];
    this.isOpen = false;
    this.activeWeek = null;
    this.loadFromStorage();
  }

  loadFromStorage() {
    try {
      const stored = localStorage.getItem('wrf-calculator-list');
      if (stored) {
        const parsed = JSON.parse(stored);
        this.shoppingList = parsed.shoppingList || parsed || [];
        this.activeWeek = parsed.activeWeek || null;
      }
    } catch (e) {
      console.error('Failed to load calculator list', e);
    }
  }

  saveToStorage() {
    try {
      localStorage.setItem('wrf-calculator-list', JSON.stringify({
        shoppingList: this.shoppingList,
        activeWeek: this.activeWeek,
      }));
    } catch (e) {
      console.error('Failed to save calculator list', e);
    }
  }

  addItem(module) {
    const instanceId = Math.random().toString(36).substring(2, 11);
    this.shoppingList.push({
      instanceId,
      moduleId: module.id || '',
      name: module.name,
      iconSrc: module.iconSrc,
      bgSrc: module.bgSrc,
      rarityRef: module.rarityRef || '',
      quantity: 1,
      fromLvl: 1,
      toLvl: 13,
    });
    this.saveToStorage();
    this.emitChange();
  }

  updateQuantity(instanceId, delta) {
    const item = this.shoppingList.find(i => i.instanceId === instanceId);
    if (item) {
      item.quantity += delta;
      if (item.quantity <= 0) {
        this.removeItem(instanceId);
      } else {
        this.saveToStorage();
        this.emitChange();
      }
    }
  }

  updateItem(instanceId, changes) {
    const item = this.shoppingList.find(i => i.instanceId === instanceId);
    if (item) {
      Object.assign(item, changes);
      // Ensure toLvl is always > fromLvl
      if (item.toLvl <= item.fromLvl) {
        item.toLvl = item.fromLvl + 1;
      }
      this.saveToStorage();
      this.emitChange();
    }
  }

  removeItem(instanceId) {
    this.shoppingList = this.shoppingList.filter(i => i.instanceId !== instanceId);
    this.saveToStorage();
    this.emitChange();
  }

  clearList() {
    this.shoppingList = [];
    this.saveToStorage();
    this.emitChange();
  }

  setActiveWeek(slug) {
    this.activeWeek = slug || null;
    this.saveToStorage();
    this.emitChange();
  }

  /**
   * Returns row costs for a single item.
   * Cost keys are destination levels: upgrading 9→13 sums costs at levels 10–13.
   * Uses window.WRF_CALC_META (rarityUpgradeCosts, discountSchedule).
   */
  calculateRowCost(item) {
    const meta = window.WRF_CALC_META;
    if (!meta || !item.rarityRef) return { salvage: 0, intel: 0 };

    const rarityEntry = meta.rarityUpgradeCosts[item.rarityRef];
    if (!rarityEntry) return { salvage: 0, intel: 0 };

    const discountedIds = this.activeWeek
      ? (meta.discountSchedule[this.activeWeek] || [])
      : [];
    const isDiscounted = discountedIds.includes(item.moduleId);

    let totalSalvage = 0;
    let totalIntel = 0;
    let standardSalvage = 0;
    let standardIntel = 0;

    for (let lvl = item.fromLvl + 1; lvl <= item.toLvl; lvl++) {
      const costNode = rarityEntry.costs[String(lvl)];
      if (!costNode) continue;

      const stdSalv = costNode.salvage.standard ?? 0;
      const stdIntel = costNode.intel.standard ?? 0;

      const salvage = isDiscounted && costNode.salvage.discounted != null
        ? costNode.salvage.discounted
        : stdSalv;

      const intel = isDiscounted && costNode.intel.discounted != null
        ? costNode.intel.discounted
        : stdIntel;

      totalSalvage += salvage * item.quantity;
      totalIntel += intel * item.quantity;
      standardSalvage += stdSalv * item.quantity;
      standardIntel += stdIntel * item.quantity;
    }

    return { 
      salvage: totalSalvage, 
      intel: totalIntel, 
      standardSalvage, 
      standardIntel, 
      isDiscounted 
    };
  }

  toggleDrawer(forceState) {
    if (forceState !== undefined) {
      this.isOpen = forceState;
    } else {
      this.isOpen = !this.isOpen;
    }
    this.emitChange();
  }

  emitChange() {
    this.dispatchEvent(new CustomEvent('change', { detail: {
      shoppingList: this.shoppingList,
      isOpen: this.isOpen,
      activeWeek: this.activeWeek,
    }}));
  }
}

export const calculatorStore = new CostCalculatorStore();


