# Discount Predictions

Predicts the most likely bot and titan discounts for the upcoming period, on the
`/predictions` page.

## How it works

- **Ranking:** bots are ranked by weeks-since-discount (most overdue first) —
  backtested as the most accurate method for both pools. Both pools use it.
- **Eligibility:** a bot needs at least 2 prior discounts to be ranked or scored;
  newer bots have no established cadence and are excluded from the predictions
  and the accuracy math alike.
- **Likelihoods** are position-calibrated: the % on the Nth-listed bot is the
  historical hit-rate of that rank slot, from a walk-forward, no-look-ahead
  backtest recomputed over all history on every build. The list is sorted by
  likelihood, so the most-overdue bot is not necessarily first.
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
- **Grading / metric:** the headline is "at least one of the top 3 robots was
  discounted" (same framing as the live page); each snapshot also stores raw hit
  data (per-pick `hit`, exact-rank hits, titan hit/miss).
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

## Ideas (not yet built)

- **Page-specific og:image** — a dedicated Discord/link-preview image for
  `/predictions` (the site already captures screenshots via Puppeteer).
- **Copy-to-share button** — one click to copy the predicted week and picks.
- **"Next" link on the week list** — a special-looking "next" label on the
  current week in the `/weeks` and index views, linking through to the predicted
  next week on `/predictions`.
