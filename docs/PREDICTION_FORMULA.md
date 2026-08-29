# Discount Prediction Formula (proposal)

**Status: REJECTED by backtest (2026-08-29).** The head-to-head gate
(`scripts/backtest_formula.py`) found this formula strictly worse than the
current position-calibrated method on every metric, in both pools. It is NOT
live and should not be shipped as designed. Numbers and takeaways are in the
"Validation gate" section below; the rest of the document is retained as the
record of what was tried and why it failed.

This documents a proposed replacement for the
current position-calibrated likelihoods (see `PREDICTIONS.md` for what ships
today). The goal is a per-bot likelihood that is a *closed-form function of that
bot's own numbers*, with a single self-tuning constant refit each week from the
backtest we already run — instead of a lookup table indexed by rank slot.

The two methods are not mutually exclusive: the plan is to build this one
alongside the current one and backtest them head-to-head before anything on the
live page changes.

---

## Why change anything

Today the `likelihood_pct` on a bot is the historical hit-rate of the **rank
slot** it lands in, not a number derived from the bot. Two very different bots in
the same slot show the same %. It works, and it is auto-calibrated, but it is a
loop over history rather than an equation, so it is neither documentable as a
formula nor sensitive to *how* overdue a given bot is.

This proposal keeps the auto-calibrating virtue (the constant still comes from
the backtest, so it can never go stale) but moves the self-tuning into one
interpretable number inside a published equation.

---

## The primary formula (fixed, closed-form, publishable)

For each eligible bot `i` in a pool, in the week being predicted:

```
w_i   = weeks since bot i was last discounted
mu_i  = bot i's average weeks between discounts
r_i   = w_i / mu_i                      # due-ness ratio: <1 not due, ~1 due, >1 overdue
s_i   = r_i ** alpha                    # score, sharpened/softened by the shape constant alpha
p_i   = min(1,  K * s_i / sum_j s_j)    # normalized to the weekly quota K
```

- **`r_i` (due-ness ratio)** is the whole signal, per bot, from data already
  computed (`weeks_since_discount`, `avg_interval`).
- **`alpha` (shape constant)** is the only free parameter. It controls how much
  overdue-ness is rewarded:
  - `alpha = 0` -> every eligible bot equal (dueness ignored, uniform odds).
  - `alpha = 1` -> odds linear in the ratio.
  - `alpha -> infinity` -> winner-take-all, i.e. today's pure "most overdue wins".
  So `alpha` interpolates the entire spectrum between "cadence does not matter"
  and "cadence is everything," and the data picks the point.
- **`K` (weekly quota)** is the expected number of discounts in the pool per week.
  Empirically stable (mech+titan combined: mean ~3.3/week, stdev ~0.8, 89% of
  weeks are 3-4), so the normalizer tracks a real game constraint rather than
  being a fudge factor. `K` is measured from prior history per pool, so it is also
  self-updating.
- **Normalization to `K`** is what encodes the non-independence the current
  per-position table captures empirically: only ~K bots can be picked, so one
  bot's probability rises only at the expense of others'. This is the
  Plackett-Luce / conditional-logit selection model (choose K of N by score).

`min(1, ...)` clips a saturated bot; at moderate `alpha` few bots approach 1, so
the "probabilities sum to K" property holds in practice. (A v2 could redistribute
clipped mass; not needed for v1.)

Eligibility is unchanged from today: a bot needs at least `MIN_HISTORY` (2) prior
discounts to be scored, and titans are scored as their own pool with their own
`K`.

---

## The secondary formula (the constant, refit each week)

`alpha` is not a magic number chosen once. It is **estimated every week from all
prior history**, by the same walk-forward backtest the pipeline already runs.
This is the part worth getting precise, because it is what makes the method
self-tuning and, as discussed below, still fully publishable.

### Estimator

```
alpha*(t) = argmin over alpha in [0, ALPHA_MAX]  of   L(alpha; history before week t)
```

where `L` is a **proper scoring rule** over the walk-forward predictions the model
would have made for every scorable week `< t`:

```
L(alpha) = mean over scored weeks u < t  of   Brier(u, alpha)

Brier(u, alpha) = sum over eligible bots i of ( p_i(u; alpha) - y_iu )^2
                  (y_iu = 1 if bot i was actually discounted in week u, else 0)
```

- **Objective is Brier (recommended), not precision.** Brier is a proper scoring
  rule, so minimizing it makes the reported % *mean what it says* -- bots called
  40% are discounted ~40% of the time. Precision@K optimizes ordering, which the
  ranking already handles; calibration is the weak spot, so fit to calibration.
  (Log-loss is the alternative proper rule; Brier is less punishing of confident
  misses on a short, noisy history, so prefer it here.)
- **`alpha` is one parameter** fit against ~45 scorable weeks (fewer early on).
  One parameter on that much data does not overfit. Clamp to `[0, ALPHA_MAX]`
  (say `ALPHA_MAX = 4`) so the thin early weeks cannot produce a wild value, and
  fall back to a prior (`alpha = 1`, the linear ratio) until there are enough
  scorable weeks to fit meaningfully.
- **No closed form for `alpha*`.** Plackett-Luce / Brier minimization has no
  algebraic solution; it is a 1-D numerical search. Because it is one bounded
  parameter, a coarse-to-fine line search over `[0, ALPHA_MAX]` is exact enough
  and fully reproducible. (This is normal: regressions publish the loss function,
  not a closed-form root.)

### The one correctness trap: nested / cumulative walk-forward

`alpha` must be estimated **cumulatively** -- from all weeks strictly before the
one being predicted -- and nowhere else. Two layers of walk-forward stack here:

1. To grade past week `t` on the `/history` page, fit `alpha*(t)` on weeks `< t`.
2. Fitting `alpha*(t)` *itself* requires running the walk-forward backtest inside
   the `< t` window (each candidate `alpha` is scored against weeks `u < t`, and
   each such `p_i(u)` uses only weeks `< u`).

So it is a backtest inside a backtest. Skipping the nesting -- fitting one
`alpha` over *all* history and reusing it to "reconstruct" past weeks -- leaks the
future into the past and inflates the reported accuracy. That is the single thing
this method must not get wrong.

Cost: O(weeks^2 * alpha-grid). With ~45 weeks and a ~40-point alpha grid that is
~80k rank operations -- a fraction of a second. The existing code already does
no-look-ahead reconstruction via `calib_max_weeknum` / `period_actuals(...,
max_weeknum=...)`, so the machinery is in place; the fit just wraps it.

For the **live upcoming week**, "all prior history" is simply all accumulated
weeks (nothing is later), so `alpha*` is fit once over everything -- exactly the
cumulative rule, no special case.

---

## How the weekly precompute runs

This slots into `build_predictions.py` next to the current path; it changes how a
likelihood is computed, not when the build runs.

**Live upcoming week (`build_predictions`)**
1. Load pools, histories, `K` per pool from all accumulated weeks.
2. Fit `alpha*` over all history by minimizing walk-forward Brier (line search).
3. Score eligible bots with `s_i = (w_i/mu_i)**alpha*`, normalize to `K`, emit
   `p_i` as each bot's `likelihood_pct`.
4. Write `predictions.json` (same shape as today; the `method` string and an
   `alpha` field record which constant was used).
5. Append the fitted `alpha*`, `K`, and the achieved Brier to a new
   `alpha_history.json`, mirroring how `accuracy_history.json` already tracks the
   calibration trend -- so the constant's trajectory is auditable over time.

**Per-week history (`build_prediction_history`)**
- For each archived week `t`, fit `alpha*(t)` on weeks `< t` (nested walk-forward
  above), score, grade against actuals, and freeze the snapshot -- same
  one-file-per-week convention as today. Each snapshot records the `alpha*(t)` it
  used, so any past week's number can be reproduced from the public data alone.

Everything stays idempotent and no-look-ahead, consistent with the current
pipeline.

---

## New / changed outputs

| File | Change |
|------|--------|
| `predictions.json` | `likelihood_pct` now formula-derived; add `alpha`, `K` per pool; updated `method` string. |
| `predictions_history/prediction_<slug>.json` | each snapshot records the `alpha*(t)` used that week. |
| `alpha_history.json` (new) | one row per predicted week: fitted `alpha*`, `K`, walk-forward Brier -- the constant's audit trail. |
| `accuracy_history.json` | unchanged in shape; precision/Brier now reflect the formula method once switched. |

---

## Validation gate before it goes live

Build this beside the current method and backtest both over the same walk-forward
weeks, scored on **Brier** (calibration) and **precision@K / at-least-one**
(ranking). Ship the formula only if it wins or ties. If it loses, the finding
itself is documentable: the empirical per-position table is hard to beat, and we
say so.

### Result (2026-08-29): rejected

`scripts/backtest_formula.py`, walk-forward with a nested per-week alpha fit
(mean alpha 1.23, range 0.20-4.00), 45 scored Mech weeks / 43 Titan weeks:

| Metric | Formula | Current (per-position) | Winner |
|--------|---------|------------------------|--------|
| Mech Brier (lower better) | 0.1001 | 0.0672 | current |
| Mech precision@5 | 0.2533 | 0.3067 | current |
| Mech at-least-one-top-3 | 0.6000 | 0.6222 | current |
| Titan Brier | 0.0622 | 0.0566 | current |
| Titan precision@2 | 0.0930 | 0.1163 | current |

The formula loses on every metric, and it is robust (alpha is fit freely per
week and still loses at every point). Two takeaways:

1. **Ranking by the due-ness ratio `w/mu` is worse than ranking by raw
   weeks-since-discount `w`.** Normalizing by each bot's average interval
   degrades the ranking rather than sharpening it -- raw overdue-ness is the
   stronger signal on this data. This refutes the core premise of the proposal.
2. **The quota/softmax normalization hurts calibration.** Spreading K (~3) units
   of probability mass smoothly across ~20 eligible bots yields larger squared
   error than the current method's concentration on the top few slots. For a
   sparse selection problem, concentrated beats smooth.

Consequence: the current per-position method stays live. A methodology page that
documents the *real* live method (not this formula) is still worth building; the
two-layer alpha framing does not apply to it. Any future formula attempt should
keep the raw-`w` ranking and only try to replace the probability read (e.g. a
fitted monotonic calibration curve on rank or on `w`), rather than re-ranking by
a ratio.

---

## Publishing the method: what is and is not shareable

Discussed in full in the working notes; summary of the conclusion:

- **The primary formula is publishable as an equation** -- it is closed form.
- **The secondary formula (the weekly fit) is publishable as an estimator**, not
  as a fixed number. You cannot print `alpha` as a constant because it moves each
  week, but you can publish (a) the loss function `L`, (b) the search domain and
  the cumulative walk-forward rule, and (c) the actual `alpha` trajectory via
  `alpha_history.json`. That is standard practice (publish the objective, not the
  root) and is arguably *more* transparent than a frozen constant, because a
  reader can recompute every week's `alpha` from the public data repo and get the
  same number. There is no adversarial-gaming risk: the schedule is
  publisher-controlled, and reproducibility is a feature, not a leak.

---

## Symbols

| Symbol | Meaning |
|--------|---------|
| `w_i` | weeks since bot `i` was last discounted |
| `mu_i` | bot `i`'s average weeks between discounts (`avg_interval`) |
| `r_i` | due-ness ratio `w_i / mu_i` |
| `alpha` | shape constant; refit weekly by the backtest |
| `s_i` | score `r_i ** alpha` |
| `K` | expected discounts per week in the pool (measured from prior history) |
| `p_i` | predicted likelihood `min(1, K * s_i / sum_j s_j)` |
| `L` | walk-forward Brier loss minimized to fit `alpha` |
