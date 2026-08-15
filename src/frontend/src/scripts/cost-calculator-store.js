/**
 * Returns true if the given moduleId is in the discount schedule for the given weekSlug.
 * Reads window.WRF_CALC_META which is populated by the inline script in CostCalculator.astro.
 */
function computeIsDiscounted(moduleId, weekSlug) {
  const meta = window.WRF_CALC_META;
  if (!meta || !weekSlug || !moduleId) return false;
  const ids = meta.discountSchedule[weekSlug] || [];
  return ids.includes(moduleId);
}

/**
 * Weekly-income rates. Single source of truth for the income panel math —
 * correct these here if the game's numbers change. See the "Weekly income"
 * section in CostCalculator.astro for the UI that consumes them.
 */
const INCOME_RATES = {
  dailyJob: { credits: 700, intel: 15 },
  weeklyJob: { credits: 5000, intel: 70 },
  dailyJobCap: { premium: 6, free: 4 },
  weeklyJobCap: { premium: 3, free: 2 },
  matchCreditFactor: 0.97,      // credits = impact * 0.97 ...
  premiumMatchMultiplier: 1.5,  // ... then * 1.5 with premium
  creditToSalvage: 10,          // 1 credit converts to 10 salvage
  daysPerWeek: 7,
};

const DEFAULT_INCOME = {
  premium: true,
  gamesPerDay: 5,
  avgImpact: 250,
  dailyJobsDone: INCOME_RATES.dailyJobCap.premium,   // default to tier max
  weeklyJobsDone: INCOME_RATES.weeklyJobCap.premium, // default to tier max
};

class CostCalculatorStore extends EventTarget {
  constructor() {
    super();
    this.shoppingList = [];
    this.isOpen = false;
    this.activeWeek = null;
    this.income = { ...DEFAULT_INCOME };
    this.loadFromStorage();
  }

  loadFromStorage() {
    try {
      const stored = localStorage.getItem('wrf-calculator-list');
      if (stored) {
        const parsed = JSON.parse(stored);
        this.shoppingList = parsed.shoppingList || parsed || [];
        this.activeWeek = parsed.activeWeek || null;
        this.income = { ...DEFAULT_INCOME, ...(parsed.income || {}) };
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
        income: this.income,
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
      discountOn: computeIsDiscounted(module.id || '', this.activeWeek),
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
    this.income = { ...DEFAULT_INCOME };
    this.saveToStorage();
    this.emitChange();
  }

  /**
   * Updates one or more income inputs (premium, gamesPerDay, avgImpact,
   * dailyJobsDone, weeklyJobsDone). Numeric fields are clamped to >= 0.
   * Job counts are clamped to the current tier cap: turning premium off
   * clamps a value down when it exceeds the lower cap, but toggling premium
   * never auto-raises an entered value ("preserve & clamp down").
   */
  setIncome(partial) {
    Object.assign(this.income, partial);
    this.income.premium = !!this.income.premium;
    this.income.gamesPerDay = Math.max(0, Number(this.income.gamesPerDay) || 0);
    this.income.avgImpact = Math.max(0, Number(this.income.avgImpact) || 0);

    const r = INCOME_RATES;
    const dCap = this.income.premium ? r.dailyJobCap.premium : r.dailyJobCap.free;
    const wCap = this.income.premium ? r.weeklyJobCap.premium : r.weeklyJobCap.free;
    this.income.dailyJobsDone = Math.min(dCap, Math.max(0, Number(this.income.dailyJobsDone) || 0));
    this.income.weeklyJobsDone = Math.min(wCap, Math.max(0, Number(this.income.weeklyJobsDone) || 0));

    this.saveToStorage();
    this.emitChange();
  }

  /**
   * Computes weekly income in salvage + intel, split between the two sources:
   * jobs (using the user's completed-job counts) and matches (from avg impact
   * and games/day). Credits convert to salvage via INCOME_RATES.creditToSalvage.
   * Matches yield no intel in the model. Returns separated { jobs, matches }
   * plus combined { salvage, intel } totals for any other consumer.
   */
  computeWeeklyIncome() {
    const r = INCOME_RATES;
    const { premium, gamesPerDay, avgImpact, dailyJobsDone, weeklyJobsDone } = this.income;

    const dailyJobs = dailyJobsDone * r.daysPerWeek; // completed per day * 7
    const weeklyJobs = weeklyJobsDone;               // completed per week

    const creditsFromJobs = dailyJobs * r.dailyJob.credits + weeklyJobs * r.weeklyJob.credits;
    const intelFromJobs = dailyJobs * r.dailyJob.intel + weeklyJobs * r.weeklyJob.intel;

    const creditsPerMatch = Math.round(avgImpact * r.matchCreditFactor * (premium ? r.premiumMatchMultiplier : 1));
    const creditsFromMatches = creditsPerMatch * gamesPerDay * r.daysPerWeek;

    const jobsSalvage = creditsFromJobs * r.creditToSalvage;
    const matchesSalvage = creditsFromMatches * r.creditToSalvage;

    return {
      jobs: { salvage: jobsSalvage, intel: intelFromJobs },
      matches: { salvage: matchesSalvage, intel: 0 },
      salvage: jobsSalvage + matchesSalvage,
      intel: intelFromJobs,
    };
  }

  setActiveWeek(slug) {
    this.activeWeek = slug || null;
    // Reset every row's discount state to match the new week.
    for (const item of this.shoppingList) {
      item.discountOn = computeIsDiscounted(item.moduleId, this.activeWeek);
    }
    this.saveToStorage();
    this.emitChange();
  }

  /**
   * Flips the discountOn toggle for a single row.
   */
  toggleItemDiscount(instanceId) {
    const item = this.shoppingList.find(i => i.instanceId === instanceId);
    if (item) {
      item.discountOn = !item.discountOn;
      this.saveToStorage();
      this.emitChange();
    }
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

    // item.discountOn is the single source of truth — set on add and
    // on week change, and manually flippable by the user.
    const isDiscounted = item.discountOn ?? false;

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
      income: this.income,
      weeklyIncome: this.computeWeeklyIncome(),
    }}));
  }
}

export const calculatorStore = new CostCalculatorStore();


