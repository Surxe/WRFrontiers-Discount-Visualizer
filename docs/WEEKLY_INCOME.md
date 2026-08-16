# Weekly Income

This document explains the in-game earning model behind the Cost Calculator's
**Weekly income** panel, and how that panel currently works. It extends
[`BACKGROUND.md`](./BACKGROUND.md), which already covers the currencies
themselves (Salvage, Intel, Credits) — read that first. The focus here is the
part BACKGROUND only names in passing: *how* a player actually earns those
currencies over a week, and why the panel models it the way it does.

---

## Why this needed explaining

The Cost Calculator prices upgrades in the two **spending** currencies a module
consumes: **Salvage** and **Intel**. To make an income panel meaningful next to
those costs, income has to be expressed in the *same* two currencies — otherwise
"you earn X" can't be compared to "this costs Y".

The catch is that the game does **not** pay you in Salvage and Intel directly
from playing. It pays you in **Credits** and **Intel**, from two distinct
activities (Jobs and Matches), each with its own rules, and Credits only become
Salvage through a conversion. So the model needs three pieces of domain
knowledge that aren't derivable from the cost data alone:

1. What the two income **sources** are and what each one pays.
2. How **Premium** changes those payouts.
3. How raw earnings (Credits + Intel) map onto the **spending** currencies
   (Salvage + Intel) the calculator deals in.

Each is covered below. The concrete numbers are the current in-game rates and
live as a single source of truth in `INCOME_RATES` inside
`src/frontend/src/scripts/cost-calculator-store.js` — correct them there if the
game rebalances.

---

## The two income sources

Weekly income is the sum of two independent streams. They are kept separate all
the way through the model (and in the UI) because they behave differently and
yield different currencies.

### 1. Jobs

Jobs are the daily/weekly mission system already named in BACKGROUND as the
source of Intel. There are two tiers, each a fixed reward bundle:

| Job type | Credits | Intel | Cadence |
|----------|--------:|------:|---------|
| **Daily job** | 700 | 15 | completed *per day* |
| **Weekly job** | 5,000 | 70 | completed *per week* |

Two things make jobs the more nuanced source:

- **Jobs are the only source of Intel.** Matches yield none. So every bit of
  Intel income in the model comes from job completions.
- **The panel asks for the *weekly total* you actually complete**, not a rate —
  `dailiesPerWeek` and `weeklyJobsPerWeek`. Premium raises the per-period caps
  (see below), but the panel no longer enforces them: you type the real count.
  This matters because of the reset overlap described next, which can legitimately
  push your weekly-job total above a single week's cap.

A full week of jobs is simply `dailiesPerWeek` daily jobs plus
`weeklyJobsPerWeek` weekly jobs — both entered as per-week totals.

### 2. Matches

Every match played pays **Credits only** (no Intel), scaled by your **impact**
score for that match — the game's single per-match performance number. The
per-match payout is:

```
creditsPerMatch = round( avgImpact × 0.97 × multiplier )
```

- The `0.97` factor is the game's baseline impact-to-credits rate.
- `multiplier` is `1.5` for a match played while Premium was active, otherwise
  `1.0`.

Because Premium may cover only part of a week, matches are entered as **two
weekly counts** — `premiumGames` (played on Premium days, earning the 1.5×) and
`freeGames` (played without it). A week of match Credits is therefore:

```
creditsFromMatches = round(avgImpact × 0.97 × 1.5) × premiumGames
                   + round(avgImpact × 0.97)       × freeGames
```

---

## How Premium changes things

Premium (the game's paid subscription tier) affects the model in **two separate
places** — this is easy to miss and was a key piece of context:

1. **It raises the Job caps** — you can complete more jobs per period:

   | | Free | Premium |
   |---|---:|---:|
   | Daily jobs / day | 4 | 6 |
   | Weekly jobs / week | 2 | 3 |

2. **It multiplies match Credits by 1.5.**

The important shift from an earlier version of this panel: **Premium is no longer
a single whole-week toggle.** Real play is rarely all-Premium or all-Free for a
clean seven days, so the model stopped inferring your earnings from a tier flag
and instead asks for the totals you *actually* earned:

- Matches are split into `premiumGames` and `freeGames` (only the former get the
  1.5×).
- Jobs are entered as raw weekly totals, with **no cap enforced**.

### Why jobs have no cap: the Wednesday reset overlap

Daily and weekly jobs reset **Wednesday overnight**. A Premium purchase that
straddles that reset therefore touches **two** game-weeks, and you can bank the
Premium weekly-job bonus in *both* — so a single seven-day span can legitimately
yield more weekly jobs than one week's cap of 3. The same logic applies to
dailies on the Premium days either side of the reset. Rather than model the reset
explicitly, the panel simply lets you enter whatever you completed; the two
**seed buttons** (below) fill in a clean full free/premium week as a starting
point you adjust from.

---

## Mapping earnings onto spending currencies

The final piece: the calculator's costs are in Salvage + Intel, but play yields
Credits + Intel. The bridge is a Credit → Salvage conversion:

- **`creditToSalvage`** is the salvage-per-credit rate, and unlike before it is a
  **user input**, not a fixed constant. The game converts Credits to Salvage in
  fixed bundles whose rate improves with size (6.25 → 7.5 → 10; see
  [`BACKGROUND.md`](./BACKGROUND.md)). The panel offers those bundles as presets
  and also accepts a manually entered **blended average** for players who buy
  across several rates. All Credit income is expressed as Salvage at this rate for
  apples-to-apples comparison with upgrade costs.
- **Intel is already a spending currency** and passes through unchanged.

Putting it together, the weekly totals are:

| Source | Salvage | Intel |
|--------|---------|-------|
| **Jobs** | `(dailiesPerWeek × 700 + weeklyJobsPerWeek × 5,000) × rate` | `dailiesPerWeek × 15 + weeklyJobsPerWeek × 70` |
| **Matches** | `creditsFromMatches × rate` | 0 |

where `rate` is `creditToSalvage` and `creditsFromMatches` is the premium/free
split shown above.

The reference implementation is `computeWeeklyIncome()` in
`cost-calculator-store.js`.

---

## How the UI feature works today

The **Weekly income** panel is a fixed section pinned to the bottom of the Cost
Calculator drawer (`src/frontend/src/components/CostCalculator.astro`). It is
always visible while the drawer is open, independent of the shopping list above
it.

**Inputs** (all persisted to `localStorage` alongside the shopping list, so they
survive reloads). There is **no Premium checkbox** anymore — every field is
"how much of X did you actually do," and Premium is implicit in those numbers:

- **Avg impact / game** — your typical per-match impact score.
- **Premium games / wk** — matches played while Premium was active (earn 1.5×).
- **Free games / wk** — matches played without Premium.
- **Dailies / wk** — total daily jobs completed this week.
- **Weekly jobs / wk** — total weekly jobs completed this week.
- **Rate (salvage / credit)** — the Credit → Salvage conversion rate.

**Seed buttons** — `Free week` and `Premium week` sit above the job fields under
an "Autofill job counts for a full week" label, and each button shows the counts
it fills (`28 daily · 2 weekly`, `42 daily · 3 weekly`, from `JOB_SEEDS` in the
store). They prefill **only** the two job counts — a starting point, not a lock,
since the fields stay freely editable for a partial-Premium week or the reset
overlap. Games volume is personal, so the seeds leave the games fields alone.

**Conversion presets** — the **Salvage / credit** field has an integrated
dropdown listing the in-game bundles (`CREDIT_SALVAGE_PRESETS`, e.g.
`3.2k → 24k (7.5)`). Picking one fills the rate input and the dropdown snaps back
to its `Rates…` label; the input still accepts a manually typed blended average.

**Validation:** every numeric input is floored at 0, with **no maximum** — job
counts can exceed a single week's cap to represent the reset overlap. Defaults
seed a full Premium week: 250 avg impact, 35 premium games, 0 free games, 42
dailies, 3 weekly jobs, and a rate of 10.

**Outputs** are recomputed live on every input change (the store emits a
`change` event carrying `weeklyIncome`) and shown split by source, matching the
model:

- **Jobs** → Salvage + Intel
- **Matches** → Salvage (matches produce no Intel, so no Intel row)

The panel is display-only in one direction: it reports what you *earn* per week;
it does not currently subtract the shopping-list *cost* above it or compute a
"weeks to afford" figure. Layout is vertical and narrow-drawer friendly — the
numeric fields are paired into compact two-column rows (premium/free games,
dailies/weekly jobs, and avg impact alongside the rate field), the seed buttons
sit as their own row above the job fields, and the Jobs/Matches totals line up
below.
