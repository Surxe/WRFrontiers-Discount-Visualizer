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
- **Completions are capped, and the cap depends on Premium** (see below). The
  panel asks how many you *actually complete*, not a rate — because most players
  don't max every slot every day.

A full week of jobs is `dailyJobsDone × 7` daily jobs plus `weeklyJobsDone`
weekly jobs (daily counts are per-day and multiplied out to the week; weekly
counts are already per-week).

### 2. Matches

Every match played pays **Credits only** (no Intel), scaled by your **impact**
score for that match — the game's single per-match performance number. The
per-match payout is:

```
creditsPerMatch = round( avgImpact × 0.97 × premiumMultiplier )
```

- The `0.97` factor is the game's baseline impact-to-credits rate.
- `premiumMultiplier` is `1.5` with Premium, otherwise `1.0`.

A week of matches is `creditsPerMatch × gamesPerDay × 7`.

---

## How Premium changes things

Premium (the game's paid subscription tier) affects the model in **two separate
places** — this is easy to miss and was a key piece of context:

1. **It raises the Job caps** — you can complete more jobs per period:

   | | Free | Premium |
   |---|---:|---:|
   | Daily jobs / day | 4 | 6 |
   | Weekly jobs / week | 2 | 3 |

2. **It multiplies match Credits by 1.5** (the `premiumMultiplier` above).

So toggling Premium changes both how many jobs you're allowed to bank *and* how
much each match is worth.

---

## Mapping earnings onto spending currencies

The final piece: the calculator's costs are in Salvage + Intel, but play yields
Credits + Intel. The bridge is a fixed conversion:

- **1 Credit → 10 Salvage** (`creditToSalvage`). The game lets you convert
  Credits into Salvage, so all Credit income is expressed as Salvage for
  apples-to-apples comparison with upgrade costs.
- **Intel is already a spending currency** and passes through unchanged.

Putting it together, the weekly totals are:

| Source | Salvage | Intel |
|--------|---------|-------|
| **Jobs** | `(dailyJobs × 700 + weeklyJobs × 5,000) × 10` | `dailyJobs × 15 + weeklyJobs × 70` |
| **Matches** | `creditsPerMatch × gamesPerDay × 7 × 10` | 0 |

where `dailyJobs = dailyJobsDone × 7` and `weeklyJobs = weeklyJobsDone`.

The reference implementation is `computeWeeklyIncome()` in
`cost-calculator-store.js`.

---

## How the UI feature works today

The **Weekly income** panel is a fixed section pinned to the bottom of the Cost
Calculator drawer (`src/frontend/src/components/CostCalculator.astro`). It is
always visible while the drawer is open, independent of the shopping list above
it.

**Inputs** (all persisted to `localStorage` alongside the shopping list, so they
survive reloads):

- **Premium** — checkbox; drives both the job caps and the match multiplier.
- **Games / day** — matches played per day.
- **Avg impact / game** — your typical per-match impact score.
- **Daily jobs / day** — completed daily jobs, clamped to the tier cap (6 / 4).
- **Weekly jobs** — completed weekly jobs, clamped to the tier cap (3 / 2).

**Clamping behavior:** numeric inputs are floored at 0. Job counts are clamped
to the current Premium tier's cap. Toggling Premium *off* clamps an over-cap
value down, but toggling Premium *on* never auto-raises a value the user
entered ("preserve & clamp down"). Defaults seed Premium on, 5 games/day, 250
avg impact, and both job counts at their premium maximums.

**Outputs** are recomputed live on every input change (the store emits a
`change` event carrying `weeklyIncome`) and shown split by source, matching the
model:

- **Jobs** → Salvage + Intel
- **Matches** → Salvage (matches produce no Intel, so no Intel row)

The panel is display-only in one direction: it reports what you *earn* per week;
it does not currently subtract the shopping-list *cost* above it or compute a
"weeks to afford" figure. Layout is a two-column grid — Premium on its own row,
the four numeric fields as an aligned 2×2 grid, and the Jobs/Matches totals
lined up under those columns.
