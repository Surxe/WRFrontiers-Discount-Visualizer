"""Phase 0 gate: backtest the proposed due-ness formula against the live
position-calibrated method, head-to-head, with no look-ahead.

Read-only. Touches nothing the pipeline writes. Run:

    .venv/bin/python scripts/backtest_formula.py

For every scorable historical week it:
  * fits the formula's shape constant ``alpha`` on strictly-prior weeks
    (cumulative / nested walk-forward, minimizing walk-forward Brier), then
  * scores that week out-of-sample with the fitted alpha and grades it, and
  * scores the SAME week with the current per-position table (also fit on
    strictly-prior weeks) for a like-for-like comparison.

Metrics (mech pool is the headline; titan reported secondarily):
  * Brier (calibration; lower is better) over the full eligible-bot set.
  * precision@top_n and at-least-one-of-top-3 (ranking; higher is better).

The formula and the current method rank differently -- the current method ranks
by weeks-since-discount ``w``; the formula ranks by the due-ness ratio
``w/mu`` -- so the ranking metrics are a real comparison, not a tautology.

See docs/PREDICTION_FORMULA.md for the model and the nested-walk-forward caveat.
"""

import sys
from pathlib import Path

# The backend modules import `from config import ...`, so src/backend must be on
# the path before we import build_predictions.
BACKEND = Path(__file__).resolve().parent.parent / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from build_predictions import (  # noqa: E402
    _load_pools,
    _rank_pool,
    _calibrate,
    period_actuals,
    _prior_count,
    MIN_HISTORY,
    BOTS_TOP_N,
    TITANS_TOP_N,
)

# Search grid for the shape constant. [0, ALPHA_MAX], coarse enough to be fast,
# fine enough to place the optimum. ALPHA_PRIOR is the fallback until there is
# enough prior history to fit.
ALPHA_MAX = 4.0
ALPHA_STEP = 0.1
ALPHA_PRIOR = 1.0
ALPHA_GRID = [round(i * ALPHA_STEP, 3) for i in range(int(ALPHA_MAX / ALPHA_STEP) + 1)]

# Need at least this many prior scorable weeks before we trust a fitted alpha;
# below it we fall back to ALPHA_PRIOR.
MIN_FIT_WEEKS = 5

AT_LEAST_ONE_K = 3


# ---------------------------------------------------------------------------
# Formula pieces (no-look-ahead: every input is derived from weeks < as_of)
# ---------------------------------------------------------------------------

def _mu_prior(weeknums, as_of):
    """Mean gap between consecutive PRIOR discounts, or None if < 2 priors."""
    prior = [w for w in weeknums if w < as_of]
    if len(prior) < 2:
        return None
    gaps = [prior[i + 1] - prior[i] for i in range(len(prior) - 1)]
    return sum(gaps) / len(gaps)


def _eligible(pool_weeknums, as_of, min_history=MIN_HISTORY):
    """Bot ids with enough prior history to be scored (and a defined mu)."""
    out = {}
    for bot_id, weeknums in pool_weeknums.items():
        if _prior_count(weeknums, as_of) < min_history:
            continue
        mu = _mu_prior(weeknums, as_of)
        if mu is None or mu <= 0:
            continue
        prior = [w for w in weeknums if w < as_of]
        w = as_of - prior[-1]
        out[bot_id] = (w, mu)
    return out


def _pool_K(pool_weeknums, all_weeknums, as_of):
    """Expected discounts/week for this pool, from prior weeks only."""
    weeks = [w for w in all_weeknums if w < as_of]
    if not weeks:
        return 0.0
    total = sum(1 for wns in pool_weeknums.values() for w in wns if w < as_of)
    return total / len(weeks)


def _formula_probs(pool_weeknums, all_weeknums, as_of, alpha, min_history=MIN_HISTORY):
    """p_i = min(1, K * (w/mu)^alpha / sum_j s_j) over eligible bots.

    Returns (probs: bot->p, ranking: bot ids by due-ness ratio desc).
    """
    elig = _eligible(pool_weeknums, as_of, min_history)
    if not elig:
        return {}, []
    scores = {b: (w / mu) ** alpha for b, (w, mu) in elig.items()}
    sum_s = sum(scores.values())
    K = _pool_K(pool_weeknums, all_weeknums, as_of)
    if sum_s <= 0:
        probs = {b: 0.0 for b in elig}
    else:
        probs = {b: min(1.0, K * s / sum_s) for b, s in scores.items()}
    # Rank by the due-ness ratio (w/mu), which is what the formula orders on.
    ranking = sorted(elig, key=lambda b: (elig[b][0] / elig[b][1], b), reverse=True)
    return probs, ranking


def _baseline_probs(pool_weeknums, all_weeknums, as_of, top_n, min_history=MIN_HISTORY):
    """Current method: per-position calibrated odds on weeks < as_of, assigned to
    the weeks-since-discount ranking. Bots past top_n get 0.

    Returns (probs: bot->p, ranking: bot ids by weeks-since-discount desc).
    """
    pa = period_actuals(pool_weeknums, all_weeknums, max_weeknum=as_of)
    calib = _calibrate(pool_weeknums, pa, top_n, min_history)
    per_pos = calib["per_position"]
    ranking = _rank_pool(pool_weeknums, as_of, min_history)
    probs = {}
    for i, bot_id in enumerate(ranking):
        probs[bot_id] = per_pos[i] if i < top_n else 0.0
    return probs, ranking


def _actual_eligible(pool_weeknums, as_of, min_history=MIN_HISTORY):
    """Eligible bots actually discounted in ``as_of`` (restricted like _calibrate)."""
    return {
        b for b, wns in pool_weeknums.items()
        if as_of in wns and _prior_count(wns, as_of) >= min_history
        and _mu_prior(wns, as_of) not in (None,) and (_mu_prior(wns, as_of) or 0) > 0
    }


def _brier(probs, eligible_ids, actual_ids):
    """Mean squared error over the eligible-bot set for one week."""
    if not eligible_ids:
        return None
    total = 0.0
    for b in eligible_ids:
        y = 1.0 if b in actual_ids else 0.0
        total += (probs.get(b, 0.0) - y) ** 2
    return total / len(eligible_ids)


# ---------------------------------------------------------------------------
# alpha fit (nested walk-forward): fit on weeks strictly before `t`
# ---------------------------------------------------------------------------

def _fit_alpha(pool_weeknums, all_weeknums, t, top_n, min_history=MIN_HISTORY):
    """Return alpha minimizing mean walk-forward Brier over scorable weeks < t."""
    prior_weeks = [
        u for u in all_weeknums
        if u < t and len(_rank_pool(pool_weeknums, u, min_history)) >= top_n
    ]
    if len(prior_weeks) < MIN_FIT_WEEKS:
        return ALPHA_PRIOR, len(prior_weeks)

    best_alpha, best_loss = ALPHA_PRIOR, float("inf")
    for alpha in ALPHA_GRID:
        losses = []
        for u in prior_weeks:
            elig = set(_eligible(pool_weeknums, u, min_history))
            if not elig:
                continue
            probs, _ = _formula_probs(pool_weeknums, all_weeknums, u, alpha, min_history)
            actual = _actual_eligible(pool_weeknums, u, min_history)
            b = _brier(probs, elig, actual)
            if b is not None:
                losses.append(b)
        if losses:
            mean_loss = sum(losses) / len(losses)
            if mean_loss < best_loss:
                best_loss, best_alpha = mean_loss, alpha
    return best_alpha, len(prior_weeks)


# ---------------------------------------------------------------------------
# Head-to-head evaluation
# ---------------------------------------------------------------------------

def _precision(ranking, actual_ids, top_n):
    top = ranking[:top_n]
    if not top:
        return None
    return sum(1 for b in top if b in actual_ids) / top_n


def _at_least_one(ranking, actual_ids, k):
    top = ranking[:k]
    if not top:
        return None
    return 1.0 if any(b in actual_ids for b in top) else 0.0


def backtest_pool(ctx, pool_name, top_n):
    pool = ctx["pools"][pool_name]
    all_weeknums = ctx["all_weeknums"]

    rows = []  # per scored week
    alphas = []
    for t in all_weeknums:
        # A week is scorable when prior history can rank a full slate.
        if len(_rank_pool(pool, t, MIN_HISTORY)) < top_n:
            continue
        elig = set(_eligible(pool, t, MIN_HISTORY))
        if not elig:
            continue
        actual = _actual_eligible(pool, t)

        alpha, n_fit = _fit_alpha(pool, all_weeknums, t, top_n)
        alphas.append(alpha)

        f_probs, f_rank = _formula_probs(pool, all_weeknums, t, alpha)
        b_probs, b_rank = _baseline_probs(pool, all_weeknums, t, top_n)

        rows.append({
            "t": t,
            "alpha": alpha,
            "n_fit": n_fit,
            "elig": len(elig),
            "actual": len(actual),
            "f_brier": _brier(f_probs, elig, actual),
            "b_brier": _brier(b_probs, elig, actual),
            "f_prec": _precision(f_rank, actual, top_n),
            "b_prec": _precision(b_rank, actual, top_n),
            "f_alo3": _at_least_one(f_rank, actual, AT_LEAST_ONE_K),
            "b_alo3": _at_least_one(b_rank, actual, AT_LEAST_ONE_K),
        })
    return rows, alphas


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else float("nan")


def _report(name, rows, alphas):
    print(f"\n=== {name} pool ===")
    print(f"scored weeks: {len(rows)}")
    if not rows:
        return
    print(f"alpha: mean {_mean(alphas):.2f}  last {alphas[-1]:.2f}  "
          f"min {min(alphas):.2f}  max {max(alphas):.2f}")
    f_brier, b_brier = _mean([r["f_brier"] for r in rows]), _mean([r["b_brier"] for r in rows])
    f_prec, b_prec = _mean([r["f_prec"] for r in rows]), _mean([r["b_prec"] for r in rows])
    f_alo, b_alo = _mean([r["f_alo3"] for r in rows]), _mean([r["b_alo3"] for r in rows])

    def verdict(f, b, lower_better):
        if abs(f - b) < 1e-6:
            return "tie"
        better = (f < b) if lower_better else (f > b)
        return "formula" if better else "baseline"

    print(f"{'metric':<24}{'formula':>10}{'baseline':>10}{'winner':>10}")
    print(f"{'Brier (lower better)':<24}{f_brier:>10.4f}{b_brier:>10.4f}"
          f"{verdict(f_brier, b_brier, True):>10}")
    print(f"{'precision@'+str(BOTS_TOP_N if name=='Mech' else TITANS_TOP_N):<24}"
          f"{f_prec:>10.4f}{b_prec:>10.4f}{verdict(f_prec, b_prec, False):>10}")
    print(f"{'at-least-one-top3':<24}{f_alo:>10.4f}{b_alo:>10.4f}"
          f"{verdict(f_alo, b_alo, False):>10}")


def main():
    ctx = _load_pools()
    if ctx is None:
        print("No data loaded; cannot backtest.")
        return
    print("Formula vs. current per-position method (walk-forward, no look-ahead)")
    print(f"alpha grid: 0..{ALPHA_MAX} step {ALPHA_STEP}; "
          f"min fit weeks {MIN_FIT_WEEKS}; MIN_HISTORY {MIN_HISTORY}")

    mech_rows, mech_alphas = backtest_pool(ctx, "Mech", BOTS_TOP_N)
    _report("Mech", mech_rows, mech_alphas)

    titan_rows, titan_alphas = backtest_pool(ctx, "Titan", TITANS_TOP_N)
    _report("Titan", titan_rows, titan_alphas)

    print("\nHeadline gate: Mech Brier + Mech precision. Formula ships only if it "
          "wins or ties both.")


if __name__ == "__main__":
    main()
