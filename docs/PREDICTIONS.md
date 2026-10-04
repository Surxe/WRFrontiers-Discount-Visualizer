# Discount Predictions

Predicts the most likely bot and titan discounts for the upcoming period, on the
`/predictions` page.

## How it works

- **Eligibility:** every bot released before the predicted week is ranked and
  graded -- including brand-new bots with no discount yet. Release dates come
  from `WRFrontiersDB-Data/curated/robot_release_dates.json`; Early Access
  carry-overs (no release date) count from the start of the history. Roster
  bots never discounted (absent from `discount_data.json`) are added from
  `VirtualBot.json` with an empty history.
- **Wait:** weeks since the bot's last discount, or since its release if it has
  never been discounted. These are two *stages* (`discount` / `release`).
  Backtested, a new bot runs on the normal cycle from release: release -> 1st
  discount has a median of 9 weeks, 1st -> 2nd 11, every later interval 11, so
  no "needs 2 discounts before it has a cadence" rule is warranted.
- **Ranking:** by *historical discount rate* -- the share of past bot-weeks at
  the same stage and wait (+/- `RATE_WAIT_WINDOW` = 2 weeks) that ended in a
  discount. A stage with fewer than `RATE_MIN_BASIS` bot-weeks in the window
  borrows the other stage's counts, and a Beta(1, 9) prior (~10%/week) keeps
  thin cells off 0%/100%. The `DiscountRateModel` is fit walk-forward, so a week
  is ranked only from weeks before it. This replaced pure "most overdue first":
  a bot far beyond the usual cycle has historically a *low* rate (Bulgasari sat
  in the most-overdue slot for 20 straight misses), and the rate demotes it.
- **Likelihoods** are position-calibrated: the % on the Nth-ranked bot is the
  historical hit-rate of that rank slot, from a walk-forward, no-look-ahead
  backtest recomputed over all history on every build. Bots tied on the
  displayed rate share their slots' odds (`_pool_tied_odds`). The list is
  sorted by likelihood, so it can differ slightly from rank order. This method
  is explained publicly on the `/methodology` page
  (`src/pages/methodology.astro`), which renders a worked example precomputed
  into the `methodology` block of `predictions.json` by
  `_methodology_example()`.
- **Scoring window:** a week is scored (calibration) or graded (`/history`) only
  once `MIN_PRIOR_WEEKS` (8) archived weeks precede it.
- **Regular bots** headline the chance at least one of the top 3 is discounted;
  cards also show each bot's factory-preset weapons and gear (bundled at
  discount) and link to its items-page entry.
- **Titans** are discounted in a minority of weeks, so their odds are framed
  conditionally ("odds of the next titan discount being this titan"), with a note
  on how often no titan is discounted at all.
- **Predicted week** is the period after the most recent one (same length); it is
  never labeled "next" since it is revealed up to a week early.

## Per-week history (the `/history` page)

The live `/predictions` page only ever holds the upcoming week, and its accuracy
figures are recomputed over all history on every build, so they drift. To keep a
*frozen, per-week record*, `build_prediction_history()` reconstructs, for every
already-archived week, the prediction that would have been shown that week —
using only the history strictly *before* it (no look-ahead) — and grades it
against what was actually discounted ("snapshot on reveal").

- **Faithful reconstruction:** each week's ranking and calibrated odds use only
  weeks before it (`_build_pool(..., calib_max_weeknum=weeknum)` /
  `period_actuals(..., max_weeknum=weeknum)`). The earliest weeks lack enough
  history to rank a full slate and are flagged `insufficient_history` and left
  out of the scoreboard.
- **Grading / metric:** every released bot's discount is a target, so a miss on
  a new bot counts against the slate (the old eligibility rule silently dropped
  those, flattering accuracy). The regular-bot headline is "at least 2 of the
  top 5 predicted robots were discounted" (the threshold is
  `BOTS_HEADLINE_MIN_HITS`; each snapshot stores the boolean as
  `result.bots.headline_hit`). The titan headline is
  "the top predicted titan was discounted, or no titan was discounted at all".
  The scoreboard is
  windowed to the most recent `SCOREBOARD_WINDOW` (15) weeks so it tracks
  current accuracy. Each snapshot also stores raw hit data (per-pick `hit`,
  exact-rank hits, "at least one of top 3", titan hit/miss).
- **Kept separate from calibration:** the realized per-week accuracy here is
  distinct from the live calibration trend in `accuracy_history.json`; the two
  are never conflated.

Output mirrors the rest of the site's one-file-per-week convention:
`src/frontend/public/data/predictions_history/prediction_<slug>.json` per week,
plus an `index.json` (thin manifest rows + a rolling `scoreboard`). The build is
idempotent (overwrites in place, prunes weeks that leave the manifest), so it
doubles as the one-time historical migration and any future manual rebuild:
`python src/backend/build_predictions.py` (or `regen_grids.py`, or the pipeline).

## Where it lives

- Backend: `src/backend/build_predictions.py`.
  - `build_predictions()` (run from step 3 and `regen_grids`) writes
    `src/frontend/public/data/predictions.json` and appends to
    `accuracy_history.json`.
  - `build_prediction_history()` (also run from step 3 and `regen_grids`) writes
    the per-week `predictions_history/` snapshots + `index.json`.
- Frontend:
  - `src/frontend/src/pages/predictions.astro` (upcoming week), composed from the
    `PredictionCard`, `AssociatedGear`, and `InfoTooltip` components.
  - `src/frontend/src/pages/history.astro` (`/history`, all past weeks), reading
    `predictions_history/index.json` via `utils/predictionHistory.js`; reuses
    `PredictionCard` with its `hit` state.
- Tests: `tests/test_predictions.py`.
- Backtests: `scripts/backtest_new_bots.py` (ranking/eligibility),
  `scripts/backtest_formula.py` (rejected formula).

## Backtest

`scripts/backtest_new_bots.py [Mech|Titan]` (read-only) grades every variant on
the same weeks and the same target (all released bots), with position-calibrated
odds and a full-roster Brier. Mech, 50 scored weeks, as of 2026-10-03:

| Variant | prec@5 | >=2 of top 5 | top pick hit | excluded targets |
|---------|--------|--------------|--------------|------------------|
| weeks-since-discount, 2 prior discounts (old) | 0.300 | 0.56 | 0.18 | 42 |
| weeks-since-discount, 1 prior discount | 0.364 | 0.64 | 0.22 | 15 |
| weeks-since-discount, release counts as discount | 0.372 | 0.70 | 0.28 | 0 |
| same, plus fitted head start for new bots | 0.364 | 0.70 | 0.24 | 0 |
| **historical discount rate (live)** | **0.388** | **0.72** | **0.46** | 0 |

The fitted head start settles at about +1 week -- effectively equal treatment.

### Refinements tested and rejected

- **Roster-size scaling.** Mech discounts per week are flat (~2.9-3.0) while
  the released roster grew from ~24 to ~37, so the cycle stretches: about
  +0.26 weeks per extra bot over gap-free intervals (r = 0.28, n = 98). Rescaling
  waits to a reference roster size scored *worse* (prec@5 0.376, top pick 0.32).
  Roster size is shared by every bot in a given week, so it cannot reorder them;
  it only regroups historical cells, and odds are already per rank slot.
- **Recency weighting** of the rate model (exponential decay, half-life 13 / 26
  / 52 weeks): prec@5 0.376 / 0.384 / 0.384, no better than unweighted.
- **Due-ness formula** (`w / mu`, softmax to a weekly quota): see
  `PREDICTION_FORMULA.md`; `scripts/backtest_formula.py` keeps a frozen copy of
  the old baseline it was run against.

## Ideas (not yet built)

- **Page-specific og:image** — a dedicated Discord/link-preview image for
  `/predictions` (the site already captures screenshots via Puppeteer).
- **Copy-to-share button** — one click to copy the predicted week and picks.
- **"Next" link on the week list** — a special-looking "next" label on the
  current week in the `/weeks` and index views, linking through to the predicted
  next week on `/predictions`.
