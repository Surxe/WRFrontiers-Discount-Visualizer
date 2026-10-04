"""Build discount predictions for the upcoming (not-yet-populated) week.

Reads the per-bot discount history (``discount_data.json``, produced by
``build_reverse_lookup``), the bot roster (``VirtualBot.json``) and the week
manifest (``weeks.json``), then:

  1. Works out the date range of the next discount period (the week after the
     most recently populated one).
  2. Ranks every released bot by its *historical discount rate*: how often,
     in the weeks before, a bot that had waited this long (since its last
     discount, or since release if it has none) was discounted that week. This
     replaced pure "most overdue wins" after a backtest
     (``scripts/backtest_new_bots.py``): it lets newly-released bots compete on
     equal terms instead of being excluded, and it demotes bots on a dry spell
     far beyond the usual cycle (which historically are rarely discounted).
  3. Re-runs a walk-forward, no-look-ahead backtest over the ENTIRE accumulated
     history every time it is invoked, so the reported accuracy figures update
     themselves as new weeks are archived rather than being a static constant.
  4. Writes ``predictions.json`` (consumed by the frontend Predictions page)
     and appends a row to ``accuracy_history.json`` so the accuracy trend over
     time stays inspectable.

Predictions are position-based: the likelihood shown for the Nth-listed bot is
the historical hit-rate of the Nth rank slot, not a per-bot number.

This module also builds the *per-week prediction history* (see
``build_prediction_history``): for every already-archived week it reconstructs
the prediction that would have been shown that week -- using only the history
strictly before it -- and grades it against what was actually discounted. That
frozen, contemporaneous record is what the ``/history`` page renders, and it is
kept distinct from the live calibration trend in ``accuracy_history.json``.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from config import (
    REPO_ROOT,
    WEEKS_MANIFEST,
    REVERSE_LOOKUP_OUTPUT,
    PREDICTIONS_OUTPUT,
    ACCURACY_HISTORY_OUTPUT,
    PREDICTION_HISTORY_DIR,
    PREDICTION_HISTORY_INDEX,
    VIRTUAL_BOT_JSON,
    MODULE_JSON,
    CHARACTER_PRESET_JSON,
    ROBOT_RELEASE_DATES_JSON,
    STANDALONE_MODULE_GROUPS,
)
from week_dates import format_week, normalize_week, week_slug, week_sort_key

# Discountable module groups that ride along with a regular bot's factory
# loadout. Titan weapons are excluded (they never co-discount with a mech).
GEAR_GROUPS = {g for g in STANDALONE_MODULE_GROUPS if g != "titan-weapon"}

# How many bots to surface per pool on the page.
BOTS_TOP_N = 5
TITANS_TOP_N = 2

# Raw detail retained on each snapshot: whether at least one of the K top-ranked
# picks was discounted (matches the live page's ``at_least_one`` framing).
BOTS_HEADLINE_K = 3

# The /history headline metric for regular bots: a week counts as a hit when at
# least this many of the top-5 predicted robots were actually discounted. ("At
# least one of the top 3" is trivially ~100% over recent weeks, so it is kept
# only as raw detail.)
BOTS_HEADLINE_MIN_HITS = 2

# The /history headline scoreboard summarizes only the most recent this-many
# weeks, so it tracks current accuracy instead of being diluted by the earliest
# thin-history weeks. The full per-week list below it is unaffected.
SCOREBOARD_WINDOW = 15

# "At least one of the top K" figures to compute per pool. Top 3 is the headline
# the page highlights for regular bots.
AT_LEAST_ONE_KS = (1, 2, 3, 4, 5)

# Historical discount rate (the ranking signal). A bot's "wait" is the weeks
# since its last discount, or since its release if it has never been discounted
# (stage "release" vs "discount"). The rate for a (stage, wait) is the share of
# prior bot-weeks at that stage and wait, give or take RATE_WAIT_WINDOW weeks,
# that ended in a discount. A stage with fewer than RATE_MIN_BASIS bot-weeks in
# the window borrows the other stage's counts, and a Beta(RATE_PRIOR_HITS,
# RATE_PRIOR_MISSES) prior (~10% a week) keeps thin cells from reading 0% or 100%.
RATE_WAIT_WINDOW = 2
RATE_MIN_BASIS = 5
RATE_PRIOR_HITS = 1
RATE_PRIOR_MISSES = 9

# A week is only scored (backtest) or graded (/history) once this many archived
# weeks precede it; before that the rate model has nothing to go on. Matches
# where the old two-prior-discounts rule first filled a five-bot slate.
MIN_PRIOR_WEEKS = 8

STAGE_RELEASE = "release"
STAGE_DISCOUNT = "discount"


def _slug_to_date(slug: str) -> date:
    return datetime.strptime(slug, "%Y-%m-%d").date()


def _week_number(d: date, origin: date) -> int:
    """Integer week index of a date relative to the first discount ever seen."""
    return round((d - origin).days / 7)


def _bot_state(weeknums, as_of_week: int, release_week: int | None):
    """``(stage, wait)`` for a bot as-of a week, or ``None`` if not yet released.

    Only discounts strictly before ``as_of_week`` count, so the state never
    peeks at the week being predicted. A bot with no release date (carried over
    from Early Access) always exists; before its first recorded discount it is
    anchored at week 0, the start of the history.
    """
    prior = [w for w in weeknums if w < as_of_week]
    if prior:
        return STAGE_DISCOUNT, as_of_week - prior[-1]
    if release_week is not None and release_week >= as_of_week:
        return None
    return STAGE_RELEASE, as_of_week - (release_week if release_week is not None else 0)


def _released(weeknums, as_of_week: int, release_week: int | None) -> bool:
    return _bot_state(weeknums, as_of_week, release_week) is not None


class DiscountRateModel:
    """Empirical weekly discount rate by (stage, wait), fit incrementally.

    ``observe`` one week at a time in chronological order; ``rate`` then only
    reflects weeks already observed, which is what keeps the walk-forward
    backtest free of look-ahead.
    """

    def __init__(self):
        self.hits = {}
        self.basis = {}

    def observe(self, pool_weeknums: dict, release_weeks: dict, week: int, actual: set):
        for bot_id, weeknums in pool_weeknums.items():
            state = _bot_state(weeknums, week, release_weeks.get(bot_id))
            if state is None:
                continue
            self.basis[state] = self.basis.get(state, 0) + 1
            if bot_id in actual:
                self.hits[state] = self.hits.get(state, 0) + 1

    def _window(self, stage, wait):
        hits = basis = 0
        for w in range(wait - RATE_WAIT_WINDOW, wait + RATE_WAIT_WINDOW + 1):
            hits += self.hits.get((stage, w), 0)
            basis += self.basis.get((stage, w), 0)
        return hits, basis

    def rate(self, stage, wait) -> float:
        hits, basis = self._window(stage, wait)
        if basis < RATE_MIN_BASIS:
            other = STAGE_DISCOUNT if stage == STAGE_RELEASE else STAGE_RELEASE
            h2, b2 = self._window(other, wait)
            hits, basis = hits + h2, basis + b2
        return (hits + RATE_PRIOR_HITS) / (basis + RATE_PRIOR_HITS + RATE_PRIOR_MISSES)


def _rank_pool(pool_weeknums: dict, as_of_week: int, release_weeks: dict,
               model: DiscountRateModel) -> list[dict]:
    """Rank every released bot in a pool by historical discount rate, best first.

    ``pool_weeknums`` maps bot_id -> sorted week-numbers it was discounted;
    ``model`` must have observed only weeks strictly before ``as_of_week``. Each
    entry is ``{id, stage, wait, rate}``. Ties on rate break on the longer wait,
    then bot_id descending, purely for deterministic output.
    """
    candidates = []
    for bot_id, weeknums in pool_weeknums.items():
        state = _bot_state(weeknums, as_of_week, release_weeks.get(bot_id))
        if state is None:
            continue
        stage, wait = state
        candidates.append({"id": bot_id, "stage": stage, "wait": wait,
                           "rate": model.rate(stage, wait)})
    candidates.sort(key=lambda c: (c["rate"], c["wait"], c["id"]), reverse=True)
    return candidates


def _calibrate(pool_weeknums: dict, period_actuals: list[tuple[int, set]], top_n: int,
               release_weeks: dict) -> tuple[dict, DiscountRateModel]:
    """Walk-forward backtest for one pool.

    ``period_actuals`` is a chronologically-ascending list of
    ``(week_number, set_of_bot_ids_discounted_that_period)``.

    For every scorable period (at least ``MIN_PRIOR_WEEKS`` periods before it
    and at least ``top_n`` bots released),
    we rank as-of that period with a discount-rate model fit only on the periods
    before it, and check the predictions against what was actually discounted.
    Returns ``(calib, model)``: per-position hit rates, per-slot precision and
    empirical "at least one of top K" rates, plus the rate model fit on every
    period in ``period_actuals`` (ready to rank the week after them).

    The "at least one of top K" rate is measured directly here rather than
    derived from the per-position rates, because rank slots are NOT independent
    (weeks with several discounts tend to hit multiple top slots together), so
    an independence formula would misestimate it.
    """
    ks = [k for k in AT_LEAST_ONE_KS if k <= top_n]
    pos_hits = [0] * top_n
    at_least_one_hits = {k: 0 for k in ks}
    scored = 0

    any_weeks = 0  # scored weeks in which the pool had at least one discount
    model = DiscountRateModel()

    for prior_weeks, (as_of_week, actual) in enumerate(period_actuals):
        ranking = [c["id"] for c in _rank_pool(pool_weeknums, as_of_week, release_weeks, model)]
        model.observe(pool_weeknums, release_weeks, as_of_week, actual)
        if prior_weeks < MIN_PRIOR_WEEKS or len(ranking) < top_n:
            continue
        # Every released bot is ranked, so every discount of a released bot is
        # a target -- an excluded bot can no longer flatter the accuracy.
        actual = {b for b in actual
                  if _released(pool_weeknums[b], as_of_week, release_weeks.get(b))}
        scored += 1
        if actual:
            any_weeks += 1
        top = ranking[:top_n]
        for i, bot_id in enumerate(top):
            if bot_id in actual:
                pos_hits[i] += 1
        for k in ks:
            if any(b in actual for b in top[:k]):
                at_least_one_hits[k] += 1

    per_position = [round(h / scored, 4) if scored else 0.0 for h in pos_hits]
    precision = round(sum(pos_hits) / (top_n * scored), 4) if scored else 0.0
    at_least_one = {
        str(k): round(at_least_one_hits[k] / scored, 4) if scored else 0.0 for k in ks
    }
    # Conditional on the pool being discounted at all that week: "if a bot from
    # this pool is discounted, how often is it the one in this slot". This is the
    # meaningful framing for a sparse pool like titans, which is absent most weeks.
    per_position_conditional = [
        round(h / any_weeks, 4) if any_weeks else 0.0 for h in pos_hits
    ]
    return {
        "top_n": top_n,
        "scored_weeks": scored,
        "any_weeks": any_weeks,
        "any_rate": round(any_weeks / scored, 4) if scored else 0.0,
        "per_position": per_position,
        "per_position_conditional": per_position_conditional,
        "precision": precision,
        "at_least_one": at_least_one,
    }, model


def _pool_tied_odds(odds: list[float], signal_by_pos: list) -> list[float]:
    """Share slot odds equally across each run of picks tied on the ranking signal.

    ``odds`` are the per-position (slot) hit-rates in ranked order and
    ``signal_by_pos`` the ranking signal (historical discount rate) of the pick
    in each of those slots. Bots tied on it are interchangeable to the model --
    the only thing separating them is the deterministic tiebreak in
    ``_rank_pool``, which arbitrarily drops one into a fatter slot than another. Handing each the
    distinct slot odds it happened to fall into would invent a ranking among
    equals, so every position in a tied run instead gets the mean of that run's
    slot odds. Untied positions keep their own slot's odds unchanged. The pooled
    list is position-aligned with the inputs and preserves their sum.
    """
    pooled = list(odds)
    i = 0
    n = len(signal_by_pos)
    while i < n:
        j = i
        while j < n and signal_by_pos[j] == signal_by_pos[i]:
            j += 1
        if j - i > 1:
            shared = sum(odds[i:j]) / (j - i)
            for k in range(i, j):
                pooled[k] = shared
        i = j
    return pooled


def _resolve_gear(bot_id, vbot_data, modules_data, preset_data):
    """Weapons/gear bundled with a regular bot's factory preset.

    This is display context, not a prediction: when a bot is discounted its
    factory loadout's discountable modules (weapons + gear, titan weapons
    excluded) are discounted alongside it. Deduped, in preset order.
    """
    vb = vbot_data.get(bot_id, {})
    preset_refs = vb.get("factory_preset_refs", [])
    if isinstance(preset_refs, str):
        preset_refs = [preset_refs]
    if not preset_refs:
        return []
    # Prefer the flagged factory preset; fall back to the first listed.
    chosen = None
    for ref in preset_refs:
        pid = ref.split("::", 1)[-1]
        preset = preset_data.get(pid)
        if preset and preset.get("is_factory_preset"):
            chosen = preset
            break
    if chosen is None:
        chosen = preset_data.get(preset_refs[0].split("::", 1)[-1], {})

    gear = []
    seen = set()
    for module_entry in chosen.get("modules", []):
        mid = module_entry.get("module_ref", "").split("::", 1)[-1]
        if not mid or mid in seen:
            continue
        seen.add(mid)
        m = modules_data.get(mid)
        if not m:
            continue
        group = (m.get("module_group_ref") or "").split("::", 1)[-1]
        if group not in GEAR_GROUPS:
            continue
        gear.append({
            "id": mid,
            "name": (m.get("name") or {}).get("en", mid),
            "icon_path": m.get("inventory_icon_path"),
            "rarity": (m.get("module_rarity_ref") or "").split("::", 1)[-1] or None,
            "group": group,
        })
    return gear


def _predicted_week(manifest: dict) -> dict:
    """Date range of the next discount period, from the most recent one.

    The next period starts when the latest one ends and spans the same length,
    so its exact dates are known even though it is only discovered up to a week
    in advance (hence the page never labels it "next").
    """
    weeks = manifest.get("weeks", [])
    if not weeks:
        raise ValueError("weeks.json manifest is empty; cannot predict.")
    latest = normalize_week(weeks[0]["week"])
    start = date(latest["start_year"], latest["start_month"], latest["start_day"])
    end = date(latest["end_year"], latest["end_month"], latest["end_day"])
    length = end - start
    pred_start = end
    pred_end = end + length
    return {
        "start_year": pred_start.year,
        "start_month": pred_start.month,
        "start_day": pred_start.day,
        "end_year": pred_end.year,
        "end_month": pred_end.month,
        "end_day": pred_end.day,
    }


def period_actuals(pool_weeknums: dict, all_weeknums: list[int], max_weeknum: int | None = None):
    """Chronological ``(week_number, discounted-set)`` pairs for a pool.

    Covers every historical discount week (both pools) so weeks in which the
    pool had no discount count as genuine "miss" weeks. When ``max_weeknum`` is
    given, only weeks strictly before it are included -- used to reconstruct a
    past week's prediction from the history that preceded it, with no look-ahead.
    """
    weeks = [w for w in all_weeknums if max_weeknum is None or w < max_weeknum]
    by_week = {w: set() for w in weeks}
    for bot_id, weeknums in pool_weeknums.items():
        for w in weeknums:
            if w in by_week:
                by_week[w].add(bot_id)
    return sorted(by_week.items())


def _load_pools():
    """Load discount history and split the roster into Mech/Titan pools.

    Returns a context dict shared by the live prediction and the per-week
    history reconstruction, or ``None`` if required inputs are missing.

    Keys: ``pools`` (name -> {bot_id: sorted week-numbers}; roster bots never yet
    discounted map to ``[]``), ``release_weeks`` (bot_id -> release week-number,
    ``None`` for Early Access carry-overs), ``meta`` (bot_id -> display
    metadata), ``origin`` (date fixing week-number 0), ``all_weeknums`` (sorted,
    both pools), ``manifest``, and the raw ``vbot_data`` / ``modules_data`` /
    ``preset_data`` needed to resolve gear.
    """
    if not REVERSE_LOOKUP_OUTPUT.exists():
        print(f"  [WARN] {REVERSE_LOOKUP_OUTPUT} missing; skipping predictions.")
        return None
    if not WEEKS_MANIFEST.exists():
        print(f"  [WARN] {WEEKS_MANIFEST} missing; skipping predictions.")
        return None

    with open(REVERSE_LOOKUP_OUTPUT, encoding="utf-8") as f:
        discount_data = json.load(f)
    with open(WEEKS_MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)

    def _load(path, label):
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        print(f"  [WARN] {label} not found at {path}")
        return {}

    vbot_data = _load(VIRTUAL_BOT_JSON, "VirtualBot.json")
    modules_data = _load(MODULE_JSON, "Module.json")
    preset_data = _load(CHARACTER_PRESET_JSON, "CharacterPreset.json")
    release_data = _load(ROBOT_RELEASE_DATES_JSON, "robot_release_dates.json")

    vbots = discount_data.get("virtualBots", {})

    # Collect every discount date to fix the week-number origin.
    all_slugs = set()
    for info in vbots.values():
        for slug in info.get("weeks", []):
            all_slugs.add(slug)
    if not all_slugs:
        print("  [WARN] No virtual bot discount history; skipping predictions.")
        return None
    origin = min(_slug_to_date(s) for s in all_slugs)

    # Split roster into pools and build bot_id -> sorted week-number list.
    # Pool membership comes from VirtualBot.json character_type ("Titan" vs Mech).
    pools = {"Mech": {}, "Titan": {}}
    meta = {}  # bot_id -> {name, icon_path, char_type}
    # Roster bots never discounted yet (recent releases) have no discount_data
    # entry; add them with an empty history so they can be ranked from release.
    roster = dict(vbots)
    for bot_id in vbot_data:
        roster.setdefault(f"OBJID_VirtualBot::{bot_id}", {"weeks": []})
    for ref, info in roster.items():
        bot_id = ref.split("::", 1)[-1]
        vb = vbot_data.get(bot_id, {})
        char_type = vb.get("character_type", "Mech")
        pool = "Titan" if char_type == "Titan" else "Mech"
        weeknums = sorted(_week_number(_slug_to_date(s), origin) for s in info.get("weeks", []))
        pools[pool][bot_id] = weeknums
        meta[bot_id] = {
            "ref": ref,
            "name": (vb.get("name") or {}).get("en", bot_id),
            "icon_path": vb.get("icon_path"),
            "char_type": char_type,
            "avg_interval": info.get("avg_weeks_between_discounts"),
            "items_anchor": f"bot-{bot_id}",
        }

    # Every historical discount week (both pools). Scoring must cover ALL of
    # these, including weeks where the pool had no discount at all -- those are
    # genuine "miss" weeks for a prediction. Restricting to weeks the pool was
    # discounted would condition accuracy on the outcome and overstate it
    # (badly for titans, which are absent most weeks).
    all_weeknums = sorted(
        {w for pool in pools.values() for weeknums in pool.values() for w in weeknums}
    )

    # Release week per bot (robots and titans share one namespace of refs). A
    # release before the history origin yields a negative week, which is fine.
    release_weeks = {}
    for section in ("robots", "titans"):
        for ref, info in (release_data.get(section) or {}).items():
            rd = info.get("release_date")
            if rd:
                release_weeks[ref.split("::", 1)[-1]] = _week_number(_slug_to_date(rd), origin)

    return {
        "discount_data": discount_data,
        "manifest": manifest,
        "vbot_data": vbot_data,
        "modules_data": modules_data,
        "preset_data": preset_data,
        "pools": pools,
        "release_weeks": release_weeks,
        "meta": meta,
        "origin": origin,
        "all_weeknums": all_weeknums,
    }


def _build_pool(ctx, pool_name, as_of_weeknum, top_n, *,
                conditional=False, include_gear=False, calib_max_weeknum=None):
    """Build one pool's ranked prediction as-of ``as_of_weeknum``.

    ``conditional=True`` frames each likelihood as "if a bot from this pool is
    discounted, the odds it is this one" -- used for titans, which are
    discounted in a minority of weeks so an unconditional odds reads as
    misleadingly low. ``include_gear`` attaches each regular bot's factory
    loadout.

    ``calib_max_weeknum`` restricts the walk-forward calibration to weeks
    strictly before it. Leave it ``None`` for the live upcoming prediction (all
    history); set it to the target week to reconstruct a past week's prediction
    faithfully, with no look-ahead.

    Returns ``(listed, calib)`` where ``listed`` is the display-ordered picks.
    """
    pools = ctx["pools"]
    meta = ctx["meta"]
    all_weeknums = ctx["all_weeknums"]
    pool_weeknums = pools[pool_name]

    release_weeks = ctx["release_weeks"]

    pa = period_actuals(pool_weeknums, all_weeknums, max_weeknum=calib_max_weeknum)
    calib, model = _calibrate(pool_weeknums, pa, top_n, release_weeks)

    # Real-world (unfiltered) share of discount weeks in which this pool had ANY
    # discount -- used for the "titans are absent most weeks" note. Kept separate
    # from the eligibility-filtered backtest so the caveat reflects reality. When
    # reconstructing a past week, measure it over that week's prior history only.
    window = [w for w in all_weeknums if calib_max_weeknum is None or w < calib_max_weeknum]
    present_weeks = {
        w for wns in pool_weeknums.values() for w in wns
        if calib_max_weeknum is None or w < calib_max_weeknum
    }
    calib["presence_rate"] = round(len(present_weeks) / len(window), 4) if window else 0.0

    odds_key = "per_position_conditional" if conditional else "per_position"
    ranking = _rank_pool(pool_weeknums, as_of_weeknum, release_weeks, model)[:top_n]
    # When reconstructing a very early week the backtest may have scored so few
    # prior weeks that no rank slot has ever been hit -- every position then
    # calibrates to 0%, which reads as a confident "no chance" rather than the
    # truth ("not enough history to estimate yet"). Detect that degenerate case
    # and surface the likelihood as null so the UI can say so instead of 0%.
    # Live predictions always have hits, so this never fires for them.
    odds = calib[odds_key]
    odds_available = any(odds[i] > 0 for i in range(len(ranking)))

    # Picks tied on historical discount rate share their slots' odds equally, so
    # an arbitrary tiebreak can't fabricate a likelihood gap between equals.
    # Compared at display precision, so the page can never show two equal rates
    # with different odds (or a pooled pair with different rates).
    pooled_odds = _pool_tied_odds(odds[:len(ranking)],
                                  [round(c["rate"] * 100, 1) for c in ranking])

    listed = []
    for i, cand in enumerate(ranking):
        bot_id = cand["id"]
        discounted = cand["stage"] == STAGE_DISCOUNT
        listed.append({
            "ref": meta[bot_id]["ref"],
            "id": bot_id,
            "name": meta[bot_id]["name"],
            "icon_path": meta[bot_id]["icon_path"],
            "items_anchor": meta[bot_id]["items_anchor"],
            "rank": i + 1,
            # A never-discounted bot waits from its release instead.
            "weeks_since_discount": cand["wait"] if discounted else None,
            "weeks_since_release": None if discounted else cand["wait"],
            "historical_rate_pct": round(cand["rate"] * 100, 1),
            "avg_interval": meta[bot_id]["avg_interval"],
            "likelihood_pct": round(pooled_odds[i] * 100, 1) if odds_available else None,
            "associated": (
                _resolve_gear(bot_id, ctx["vbot_data"], ctx["modules_data"], ctx["preset_data"])
                if include_gear else []
            ),
        })
    # Present the list ordered by calibrated likelihood to match the "most
    # likely" framing; slot hit-rates are not strictly monotonic, so this can
    # differ slightly from rank order. With no odds available, keep rank order.
    listed.sort(
        key=lambda b: (
            b["likelihood_pct"] if b["likelihood_pct"] is not None else -1.0,
            -b["rank"],
        ),
        reverse=True,
    )
    return listed, calib


def _methodology_example(bots, bots_calib, pred_slug):
    """Precompute the worked example the /methodology page renders.

    Documents the live method for the top displayed robot, so the page's
    arithmetic always reproduces the number on that card and refreshes every
    deploy. Pure read-out of quantities already computed -- no new method.

    The top card (``bots[0]``, already sorted by likelihood) holds rank slot R,
    earned by its historical discount rate (step 1); its likelihood is that
    slot's hit-rate over the backtested weeks, i.e. ``slot_hits / scored_weeks``
    (step 2). When the top card is tied with other robots on that rate, those
    tied slots' rates are pooled (averaged) into the shared number on the card
    (see ``_pool_tied_odds``); the example exposes the tie so the page
    reproduces that averaging rather than a single slot's rate.
    """
    if not bots:
        return None
    top = bots[0]
    rank = top.get("rank")
    per_pos = bots_calib.get("per_position") or []
    scored = bots_calib.get("scored_weeks") or 0
    if not rank or rank - 1 >= len(per_pos):
        return None

    # The tie group is every displayed pick sharing the top card's rate, ordered
    # by the slot it occupies. A lone top card yields a one-element group and the
    # example collapses to the simple single-slot walk-through.
    rate = top.get("historical_rate_pct")
    tie_group = sorted(
        (b for b in bots
         if b.get("historical_rate_pct") == rate
         and b.get("rank") and b["rank"] - 1 < len(per_pos)),
        key=lambda b: b["rank"],
    )
    tie_ranks = [b["rank"] for b in tie_group]
    tie_slot_rates = [per_pos[r - 1] for r in tie_ranks]
    tie_slot_hits = [round(r * scored) for r in tie_slot_rates]
    slot_rate = per_pos[rank - 1]
    return {
        "method": "historical-rate ranked, position-calibrated",
        "predicted_week": pred_slug,
        "scored_weeks": scored,
        "rate_wait_window": RATE_WAIT_WINDOW,
        "example": {
            "bot_id": top.get("id"),
            "name": top.get("name"),
            "rank": rank,
            "weeks_since_discount": top.get("weeks_since_discount"),
            "weeks_since_release": top.get("weeks_since_release"),
            "historical_rate_pct": rate,
            "slot_hit_rate": slot_rate,
            "slot_hits": round(slot_rate * scored),
            "likelihood_pct": top.get("likelihood_pct"),
            "pooled": len(tie_ranks) > 1,
            "tie_ranks": tie_ranks,
            "tie_slot_rates": tie_slot_rates,
            "tie_slot_hits": tie_slot_hits,
        },
    }


def build_predictions():
    print("  -> Building upcoming-week predictions...")

    ctx = _load_pools()
    if ctx is None:
        return None

    # Predicted week + its week-number.
    pred_week = _predicted_week(ctx["manifest"])
    pred_start = date(pred_week["start_year"], pred_week["start_month"], pred_week["start_day"])
    pred_weeknum = _week_number(pred_start, ctx["origin"])
    pred_label = format_week(pred_week, style="long")
    pred_slug = week_slug(pred_week)

    # Live prediction calibrates over ALL accumulated history (nothing is later
    # than the upcoming week), so calib_max_weeknum stays None.
    bots, bots_calib = _build_pool(ctx, "Mech", pred_weeknum, BOTS_TOP_N, include_gear=True)
    titans, titans_calib = _build_pool(ctx, "Titan", pred_weeknum, TITANS_TOP_N, conditional=True)

    generated_at = datetime.now().astimezone().isoformat()
    predictions = {
        "generated_at": generated_at,
        "method": "historical discount rate by wait (since discount or release); position-calibrated odds",
        "predictedWeek": {
            **pred_week,
            "slug": pred_slug,
            "label": pred_label,
        },
        "bots": bots,
        "titans": titans,
        "accuracy": {
            "bots": bots_calib,
            "titans": titans_calib,
        },
        "methodology": _methodology_example(bots, bots_calib, pred_slug),
    }

    with open(PREDICTIONS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote predictions to {PREDICTIONS_OUTPUT.relative_to(REPO_ROOT)}")

    _append_accuracy_history(pred_slug, generated_at, bots_calib, titans_calib)
    return predictions


def _append_accuracy_history(pred_slug, generated_at, bots_calib, titans_calib):
    """Append one row per predicted week so the accuracy trend is inspectable.

    Skips writing when the newest row already covers the same predicted week, so
    re-running the pipeline for the same week updates in place instead of piling
    up duplicate rows.
    """
    history = []
    if ACCURACY_HISTORY_OUTPUT.exists():
        try:
            with open(ACCURACY_HISTORY_OUTPUT, encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []

    row = {
        "predicted_week": pred_slug,
        "generated_at": generated_at,
        "bots_precision": bots_calib["precision"],
        "bots_at_least_one_top3": bots_calib["at_least_one"].get("3"),
        "bots_scored_weeks": bots_calib["scored_weeks"],
        "titans_precision": titans_calib["precision"],
        "titans_scored_weeks": titans_calib["scored_weeks"],
    }

    if history and history[-1].get("predicted_week") == pred_slug:
        history[-1] = row
    else:
        history.append(row)

    with open(ACCURACY_HISTORY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"  -> Updated accuracy history at {ACCURACY_HISTORY_OUTPUT.relative_to(REPO_ROOT)}")


# ---------------------------------------------------------------------------
# Per-week prediction history (the /history page)
# ---------------------------------------------------------------------------

def _grade_pool(listed, actual_ids, headline_k=None):
    """Mark each listed pick hit/miss and summarize the pool's result.

    ``actual_ids`` is the set of bot_ids from this pool actually discounted the
    graded week (every released bot counts). ``headline_k`` (e.g. 3 for bots)
    reports whether at least one of the K top-ranked picks was discounted --
    the same framing as the calibration
    ``at_least_one`` figure. Mutates ``listed`` in place (adds ``hit``).
    """
    hits = 0
    for pick in listed:
        pick["hit"] = pick["id"] in actual_ids
        if pick["hit"]:
            hits += 1
    result = {
        "hits": hits,
        "listed": len(listed),
        "eligible_actual": len(actual_ids),
        "top_hit": bool(listed) and listed[0]["id"] in actual_ids,
    }
    if headline_k is not None:
        top_k = {p["id"] for p in listed if p["rank"] <= headline_k}
        result["top3_hit"] = bool(top_k & actual_ids)
    return result


def _eligible_actual(pool_weeknums, release_weeks, weeknum):
    """Bot_ids of this pool discounted in ``weeknum`` that were released by then."""
    return {
        bot_id for bot_id, weeknums in pool_weeknums.items()
        if weeknum in weeknums and _released(weeknums, weeknum, release_weeks.get(bot_id))
    }


def _snapshot_week(ctx, week):
    """Reconstruct and grade the prediction for one already-archived week.

    Uses only history strictly before the week, so the snapshot is the
    prediction that would have been shown that week. Returns the per-week record
    plus a compact index row.
    """
    slug = week_slug(week)
    start = date(week["start_year"], week["start_month"], week["start_day"])
    weeknum = _week_number(start, ctx["origin"])
    label = format_week(week, style="long")

    bots, _ = _build_pool(ctx, "Mech", weeknum, BOTS_TOP_N,
                          include_gear=True, calib_max_weeknum=weeknum)
    titans, _ = _build_pool(ctx, "Titan", weeknum, TITANS_TOP_N,
                            conditional=True, calib_max_weeknum=weeknum)

    # A pool is "insufficient" when too few bots are released to fill a slate;
    # the week is shown as such and left out of the scoreboard.
    prior_weeks = sum(1 for w in ctx["all_weeknums"] if w < weeknum)
    bots_insufficient = prior_weeks < MIN_PRIOR_WEEKS or len(bots) < BOTS_TOP_N
    titans_insufficient = prior_weeks < MIN_PRIOR_WEEKS or len(titans) < TITANS_TOP_N
    if bots_insufficient:
        bots = []
    if titans_insufficient:
        titans = []
    insufficient = {"bots": bots_insufficient, "titans": titans_insufficient}

    actual_bots = _eligible_actual(ctx["pools"]["Mech"], ctx["release_weeks"], weeknum)
    actual_titans = _eligible_actual(ctx["pools"]["Titan"], ctx["release_weeks"], weeknum)
    any_titan = any(weeknum in wns for wns in ctx["pools"]["Titan"].values())

    bots_result = _grade_pool(bots, actual_bots, headline_k=BOTS_HEADLINE_K)
    # Headline: at least BOTS_HEADLINE_MIN_HITS of the top-5 picks were discounted.
    bots_result["headline_hit"] = bots_result["hits"] >= BOTS_HEADLINE_MIN_HITS
    titans_result = _grade_pool(titans, actual_titans)
    titans_result["any_titan"] = any_titan

    # Whether calibrated odds could be shown (see _build_pool). Picks and their
    # grading are still valid when odds are unavailable -- only the % is hidden.
    odds_available = {
        "bots": bool(bots) and bots[0]["likelihood_pct"] is not None,
        "titans": bool(titans) and titans[0]["likelihood_pct"] is not None,
    }

    record = {
        "week": week,
        "slug": slug,
        "label": label,
        "reconstructed": True,
        "graded": True,
        "insufficient_history": insufficient,
        "odds_available": odds_available,
        "method": "historical discount rate; walk-forward, history-before-week only",
        "bots": bots,
        "titans": titans,
        "actuals": {"bots": sorted(actual_bots), "titans": sorted(actual_titans)},
        "result": {"bots": bots_result, "titans": titans_result},
    }
    index_row = {
        "slug": slug,
        "week": week,
        "label": label,
        "file": f"predictions_history/prediction_{slug}.json",
        "graded": True,
        "insufficient_history": insufficient,
        "result": {"bots": bots_result, "titans": titans_result},
    }
    return record, index_row


def build_prediction_history():
    """Reconstruct and grade a per-week prediction snapshot for every archived
    week, then write the index + rolling scoreboard.

    Idempotent: overwrites each ``prediction_<slug>.json`` in place and prunes
    snapshots whose week is no longer in the manifest. Cheap enough (dozens of
    weeks) to regenerate wholesale, so both the pipeline and a full regen call
    it, and it doubles as the one-time historical migration.
    """
    print("  -> Building per-week prediction history...")

    ctx = _load_pools()
    if ctx is None:
        return None

    weeks = ctx["manifest"].get("weeks", [])
    if not weeks:
        print("  [WARN] weeks.json manifest is empty; skipping prediction history.")
        return None

    PREDICTION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    index_rows = []
    kept_files = set()
    for entry in weeks:
        week = normalize_week(entry["week"])
        record, index_row = _snapshot_week(ctx, week)
        out = PREDICTION_HISTORY_DIR / f"prediction_{record['slug']}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        kept_files.add(out.name)
        index_rows.append(index_row)

    # Prune stale snapshots for weeks that dropped out of the manifest.
    for stale in PREDICTION_HISTORY_DIR.glob("prediction_*.json"):
        if stale.name not in kept_files:
            stale.unlink()

    index_rows.sort(key=lambda r: week_sort_key(r["week"]), reverse=True)

    # Rolling scoreboard over the most recent weeks only, so the headline
    # reflects current accuracy rather than being diluted by the thin-history
    # early weeks. Rows are newest-first, so the window is a simple slice.
    recent = index_rows[:SCOREBOARD_WINDOW]

    # Headline is the "at least 2 of the top 5 robots were discounted" hit rate.
    bots_scored = [r for r in recent if not r["insufficient_history"]["bots"]]
    bots_hits = sum(1 for r in bots_scored if r["result"]["bots"].get("headline_hit"))
    # A titan week counts as correct when the top predicted titan was the one
    # discounted OR no titan was discounted at all -- since titans are absent
    # most weeks, "no titan" is a correct call for a next-titan prediction, not a
    # miss.
    titans_scored = [r for r in recent if not r["insufficient_history"]["titans"]]
    titans_hits = sum(
        1 for r in titans_scored
        if r["result"]["titans"].get("top_hit") or not r["result"]["titans"].get("any_titan")
    )
    scoreboard = {
        "window_weeks": len(recent),
        "bots_scored_weeks": len(bots_scored),
        "bots_hits": bots_hits,
        "bots_rate": round(bots_hits / len(bots_scored), 4) if bots_scored else 0.0,
        "titans_scored_weeks": len(titans_scored),
        "titans_hits": titans_hits,
        "titans_rate": round(titans_hits / len(titans_scored), 4) if titans_scored else 0.0,
    }

    index = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "scoreboard": scoreboard,
        "weeks": index_rows,
    }
    with open(PREDICTION_HISTORY_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"  -> Wrote prediction history ({len(index_rows)} weeks) to "
          f"{PREDICTION_HISTORY_DIR.relative_to(REPO_ROOT)}")
    return index


if __name__ == "__main__":
    build_predictions()
    build_prediction_history()
