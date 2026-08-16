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
  matchCreditFactor: 0.97,      // credits = impact * 0.97 ...
  premiumMatchMultiplier: 1.5,  // ... then * 1.5 for premium-day matches
};

/**
 * In-game credit -> salvage conversion bundles. The user picks one (its `rate`
 * fills the editable conversion field) or types a custom blended average.
 * `rate` is salvage per credit; credits/salvage are the bundle amounts shown.
 */
export const CREDIT_SALVAGE_PRESETS = [
  { credits: 1600, salvage: 10000, rate: 6.25 },
  { credits: 3200, salvage: 24000, rate: 7.5  },
  { credits: 6000, salvage: 60000, rate: 10   },
  { credits: 9000, salvage: 90000, rate: 10   },
];

/**
 * Full-week job totals for each tier, used by the "Free week" / "Premium week"
 * seed buttons to prefill the (uncapped) job-count inputs. Derived from the old
 * per-day caps: 4/day free and 6/day premium over a 7-day week, plus 2/3 weekly.
 */
export const JOB_SEEDS = {
  free:    { dailiesPerWeek: 28, weeklyJobsPerWeek: 2 },
  premium: { dailiesPerWeek: 42, weeklyJobsPerWeek: 3 },
};

const DEFAULT_INCOME = {
  avgImpact: 250,
  premiumGames: 35,        // premium-day matches per week (5/day * 7)
  freeGames: 0,            // non-premium matches per week
  dailiesPerWeek: JOB_SEEDS.premium.dailiesPerWeek,
  weeklyJobsPerWeek: JOB_SEEDS.premium.weeklyJobsPerWeek,
  creditToSalvage: 10,     // salvage per credit; user-editable (see presets)
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
   * Updates one or more income inputs. All fields are per-week totals the user
   * enters directly (avgImpact, premiumGames, freeGames, dailiesPerWeek,
   * weeklyJobsPerWeek, creditToSalvage). Every numeric field is floored at 0;
   * there are deliberately no maxes — a premium window spanning the Wednesday
   * job reset can push job counts above a single week's cap.
   */
  setIncome(partial) {
    Object.assign(this.income, partial);
    for (const k of ['avgImpact', 'premiumGames', 'freeGames',
                     'dailiesPerWeek', 'weeklyJobsPerWeek', 'creditToSalvage']) {
      this.income[k] = Math.max(0, Number(this.income[k]) || 0);
    }
    this.saveToStorage();
    this.emitChange();
  }

  /**
   * Computes weekly income in salvage + intel, split between the two sources:
   * jobs (from the user's per-week completed-job totals) and matches (from avg
   * impact and the premium/free games split — premium-day matches earn the 1.5x
   * multiplier). Credits convert to salvage via the user's creditToSalvage rate.
   * Matches yield no intel in the model. Returns separated { jobs, matches }
   * plus combined { salvage, intel } totals for any other consumer.
   */
  computeWeeklyIncome() {
    const r = INCOME_RATES;
    const { avgImpact, premiumGames, freeGames,
            dailiesPerWeek, weeklyJobsPerWeek, creditToSalvage } = this.income;

    const creditsFromJobs = dailiesPerWeek * r.dailyJob.credits + weeklyJobsPerWeek * r.weeklyJob.credits;
    const intelFromJobs = dailiesPerWeek * r.dailyJob.intel + weeklyJobsPerWeek * r.weeklyJob.intel;

    const base = avgImpact * r.matchCreditFactor;
    const creditsFromMatches = Math.round(base * r.premiumMatchMultiplier) * premiumGames
                             + Math.round(base) * freeGames;

    const jobsSalvage = creditsFromJobs * creditToSalvage;
    const matchesSalvage = creditsFromMatches * creditToSalvage;

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


