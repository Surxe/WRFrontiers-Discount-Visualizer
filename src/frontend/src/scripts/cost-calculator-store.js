class CostCalculatorStore extends EventTarget {
  constructor() {
    super();
    this.shoppingList = [];
    this.isOpen = false;
    this.loadFromStorage();
  }

  loadFromStorage() {
    try {
      const stored = localStorage.getItem('wrf-calculator-list');
      if (stored) {
        this.shoppingList = JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load calculator list', e);
    }
  }

  saveToStorage() {
    try {
      localStorage.setItem('wrf-calculator-list', JSON.stringify(this.shoppingList));
    } catch (e) {
      console.error('Failed to save calculator list', e);
    }
  }

  addItem(module) {
    // Generate a unique ID for each instance to allow multiple of same module to be added separately
    const instanceId = Math.random().toString(36).substring(2, 11);
    
    this.shoppingList.push({
      instanceId,
      moduleId: module.id || '',
      name: module.name,
      iconSrc: module.iconSrc,
      quantity: 1,
      fromLvl: 1,
      toLvl: 2,
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

  removeItem(instanceId) {
    this.shoppingList = this.shoppingList.filter(i => i.instanceId !== instanceId);
    this.saveToStorage();
    this.emitChange();
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
      isOpen: this.isOpen
    }}));
  }
}

export const calculatorStore = new CostCalculatorStore();
