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

## Where it lives

- Backend: `src/backend/build_predictions.py` (run from step 3 and `regen_grids`)
  writes `src/frontend/public/data/predictions.json` and appends to
  `accuracy_history.json`.
- Frontend: `src/frontend/src/pages/predictions.astro`, composed from the
  `PredictionCard`, `AssociatedGear`, and `InfoTooltip` components.
- Tests: `tests/test_predictions.py`.

## Ideas (not yet built)

- **Page-specific og:image** — a dedicated Discord/link-preview image for
  `/predictions` (the site already captures screenshots via Puppeteer).
- **Copy-to-share button** — one click to copy the predicted week and picks.
- **"Next" link on the week list** — a special-looking "next" label on the
  current week in the `/weeks` and index views, linking through to the predicted
  next week on `/predictions`.
