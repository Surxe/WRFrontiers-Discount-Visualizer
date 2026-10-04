"""Backtest how recently-released bots enter the discount predictions.

Read-only research harness behind the historical-rate ranking (todo t-0157).
Touches nothing the pipeline writes. Run:

    .venv/bin/python scripts/backtest_new_bots.py [Mech|Titan]

The previous live method ranked a pool by weeks-since-last-discount and dropped
any bot with fewer than 2 prior discounts. That exclusion also hid those bots
from grading, so its accuracy figures were measured on an easier target set.
Here every variant is graded against the SAME target: every bot actually
discounted that week that had been released by then. Excluding a bot is
therefore a guaranteed miss whenever it gets discounted.

Variants (all walk-forward, no look-ahead, scored on the same weeks):
  * min2 (old)      -- the previous live method.
  * min1            -- one prior discount is enough; no release dates needed.
  * release         -- every released bot eligible; a bot with no prior
                       discount waits from its release ("release counts as a
                       discount"), i.e. new bots treated equally.
  * release+d       -- as `release`, but a never-discounted bot's wait is
                       shifted by d (d>0 = new bots come due sooner), with d fit
                       walk-forward on strictly-prior weeks.
  * rate (live)     -- the shipped method: rank by historical discount rate for
                       the bot's (stage, wait), via build_predictions'
                       DiscountRateModel / _rank_pool.

Per-slot odds are position-calibrated for every variant (as on the live page),
and Brier is taken over the full released roster: top slots get their prior
slot hit-rate, every other bot (outranked or excluded) the prior residual rate.
"""

import sys
from pathlib import Path
from statistics import mean, median

BACKEND = Path(__file__).resolve().parent.parent / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from build_predictions import (  # noqa: E402
    BOTS_HEADLINE_MIN_HITS,
    BOTS_TOP_N,
    MIN_PRIOR_WEEKS,
    STAGE_RELEASE,
    TITANS_TOP_N,
    DiscountRateModel,
    _bot_state,
    _load_pools,
    _rank_pool,
    period_actuals,
)

RECENT_WINDOW = 20  # weeks; new bots only exist in volume in recent history
SHIFT_GRID = list(range(-6, 9))
MIN_FIT_WEEKS = 5


# ---------------------------------------------------------------------------
# Rankers: (pool, as_of, release_weeks, model, params) -> [bot_id, ...] best
# first. Ties break on bot_id descending, matching _rank_pool.
# ---------------------------------------------------------------------------

def rank_min_history(min_history):
    def ranker(pool, as_of, release_weeks, _model, _params):
        c = []
        for b, wns in pool.items():
            prior = [w for w in wns if w < as_of]
            if len(prior) >= min_history and prior:
                c.append((as_of - prior[-1], b))
        c.sort(reverse=True)
        return [b for _, b in c]
    return ranker


def rank_release(pool, as_of, release_weeks, _model, params):
    shift = params.get("shift", 0)
    c = []
    for b, wns in pool.items():
        state = _bot_state(wns, as_of, release_weeks.get(b))
        if state is None:
            continue
        stage, wait = state
        c.append((wait + (shift if stage == STAGE_RELEASE else 0), b))
    c.sort(reverse=True)
    return [b for _, b in c]


def rank_rate(pool, as_of, release_weeks, model, _params):
    return [c["id"] for c in _rank_pool(pool, as_of, release_weeks, model)]


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def released_targets(pool, as_of, actual, release_weeks):
    return {b for b in actual if _bot_state(pool[b], as_of, release_weeks.get(b)) is not None}


def fit_best_shift(pool, actuals, release_weeks, as_of, top_n):
    prior = [(w, a) for w, a in actuals if w < as_of]
    if len(prior) < MIN_FIT_WEEKS:
        return 0
    best = None
    for d in SHIFT_GRID:
        tot = 0
        for w, a in prior:
            top = rank_release(pool, w, release_weeks, None, {"shift": d})[:top_n]
            tot += sum(b in released_targets(pool, w, a, release_weeks) for b in top)
        # Prefer the smallest |d| on ties (equal treatment unless data says otherwise).
        key = (tot, -abs(d))
        if best is None or key > best[0]:
            best = (key, d)
    return best[1]


def grade(ranker, pool, actuals, release_weeks, top_n, fit_shift=False):
    rows = []
    model = DiscountRateModel()
    slot_hits = [0] * top_n
    slot_n = 0
    rest_hits = rest_n = 0
    for prior_weeks, (as_of, actual) in enumerate(actuals):
        params = {}
        if fit_shift:
            params["shift"] = fit_best_shift(pool, actuals, release_weeks, as_of, top_n)
        ranking = ranker(pool, as_of, release_weeks, model, params)
        model.observe(pool, release_weeks, as_of, actual)
        if prior_weeks < MIN_PRIOR_WEEKS:
            continue
        tgt = released_targets(pool, as_of, actual, release_weeks)
        top = ranking[:top_n]
        hits = [b in tgt for b in top]
        released = [b for b in pool if _bot_state(pool[b], as_of, release_weeks.get(b))]
        rest = [b for b in released if b not in top]
        probs = [(slot_hits[i] / slot_n) if slot_n else 0.2 for i in range(top_n)]
        rest_p = rest_hits / rest_n if rest_n else 0.05
        brier = sum((probs[i] - hits[i]) ** 2 for i in range(len(top)))
        brier += sum((rest_p - (b in tgt)) ** 2 for b in rest)
        rows.append({
            "week": as_of,
            "hits": sum(hits),
            "targets": len(tgt),
            "top1": bool(hits) and hits[0],
            "any3": any(hits[:3]),
            "brier": brier,
            "excluded_targets": sum(b not in ranking for b in tgt),
            "shift": params.get("shift"),
        })
        for i, h in enumerate(hits):
            slot_hits[i] += h
        slot_n += 1
        rest_hits += sum(b in tgt for b in rest)
        rest_n += len(rest)
    return rows


def summarize(rows, top_n):
    n = len(rows)
    targets = sum(r["targets"] for r in rows)
    return {
        "weeks": n,
        "prec@N": sum(r["hits"] for r in rows) / (top_n * n),
        "recall@N": sum(r["hits"] for r in rows) / targets if targets else 0.0,
        f">={BOTS_HEADLINE_MIN_HITS}ofN": sum(r["hits"] >= BOTS_HEADLINE_MIN_HITS for r in rows) / n,
        "top1": sum(r["top1"] for r in rows) / n,
        "any3": sum(r["any3"] for r in rows) / n,
        "brier/wk": sum(r["brier"] for r in rows) / n,
        "excl_tgts": sum(r["excluded_targets"] for r in rows),
    }


def interval_stats(pool, release_weeks):
    """Release->1st, 1st->2nd (released bots) and all later intervals."""
    first, second, later = [], [], []
    for b, wns in pool.items():
        rw = release_weeks.get(b)
        if rw is not None and wns:
            first.append(wns[0] - rw)
        if rw is not None and len(wns) >= 2:
            second.append(wns[1] - wns[0])
        start = 1 if rw is not None else 0
        later += [wns[i + 1] - wns[i] for i in range(start, len(wns) - 1)]

    def fmt(xs):
        if not xs:
            return "-"
        return f"n={len(xs)} median={median(xs)} mean={mean(xs):.1f} min={min(xs)} max={max(xs)}"
    return {"release->1st": fmt(first), "1st->2nd (released)": fmt(second), "later": fmt(later)}


def main():
    pool_name = sys.argv[1] if len(sys.argv) > 1 else "Mech"
    top_n = TITANS_TOP_N if pool_name == "Titan" else BOTS_TOP_N
    ctx = _load_pools()
    pool = ctx["pools"][pool_name]
    release_weeks = ctx["release_weeks"]
    actuals = period_actuals(pool, ctx["all_weeknums"])

    print(f"== {pool_name}: intervals (weeks) ==")
    for k, v in interval_stats(pool, release_weeks).items():
        print(f"  {k:>20}: {v}")

    variants = [
        ("min2 (old)", rank_min_history(2), False),
        ("min1", rank_min_history(1), False),
        ("release", rank_release, False),
        ("release+d (fit)", rank_release, True),
        ("rate (live)", rank_rate, False),
    ]
    results = {name: grade(r, pool, actuals, release_weeks, top_n, fit)
               for name, r, fit in variants}

    weeks = sorted({r["week"] for r in results["rate (live)"]})
    windows = (("ALL scored weeks", set(weeks)), (f"RECENT {RECENT_WINDOW}", set(weeks[-RECENT_WINDOW:])))
    for label, wset in windows:
        print(f"\n== {pool_name}: {label} (top {top_n}) ==")
        hdr = None
        for name, rows in results.items():
            s = summarize([r for r in rows if r["week"] in wset], top_n)
            if hdr is None:
                hdr = list(s)
                print(f"{'variant':>16}  " + "  ".join(f"{h:>9}" for h in hdr))
            vals = [f"{s[h]:9.3f}" if isinstance(s[h], float) else f"{s[h]:9d}" for h in hdr]
            print(f"{name:>16}  " + "  ".join(vals))

    shifts = [r["shift"] for r in results["release+d (fit)"] if r["week"] in windows[1][1]]
    print(f"\nfitted shift d over recent weeks: {shifts}")


if __name__ == "__main__":
    main()
