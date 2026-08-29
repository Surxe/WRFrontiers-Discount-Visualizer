"""Build discount predictions for the upcoming (not-yet-populated) week.

Reads the per-bot discount history (``discount_data.json``, produced by
``build_reverse_lookup``), the bot roster (``VirtualBot.json``) and the week
manifest (``weeks.json``), then:

  1. Works out the date range of the next discount period (the week after the
     most recently populated one).
  2. Ranks bot composites by weeks-since-discount ("most overdue wins"). This
     ranking method was validated by backtest as the most accurate for both
     regular bots and titans; both pools use it for simplicity.
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
    STANDALONE_MODULE_GROUPS,
)
from week_dates import format_week, normalize_week, week_slug, week_sort_key

# Discountable module groups that ride along with a regular bot's factory
# loadout. Titan weapons are excluded (they never co-discount with a mech).
GEAR_GROUPS = {g for g in STANDALONE_MODULE_GROUPS if g != "titan-weapon"}

# How many bots to surface per pool on the page.
BOTS_TOP_N = 5
TITANS_TOP_N = 2

# Raw detail retained on each snapshot: whether at least one of the K most-overdue
# picks was discounted (matches the live page's ``at_least_one`` framing).
BOTS_HEADLINE_K = 3

# The /history headline metric for regular bots: a week counts as a hit when at
# least this many of the top-5 predicted robots were actually discounted. ("At
# least one of the top 3" is trivially ~100% over recent weeks, so it is kept
# only as raw detail.) Set to 2 rather than 3 because bots with fewer than
# MIN_HISTORY prior discounts are excluded from the predictions yet can still
# take a discount slot in the actual week, so a 2-of-5 bar is a fairer read of
# the model's real skill.
BOTS_HEADLINE_MIN_HITS = 2

# The /history headline scoreboard summarizes only the most recent this-many
# weeks, so it tracks current accuracy instead of being diluted by the earliest
# thin-history weeks. The full per-week list below it is unaffected.
SCOREBOARD_WINDOW = 15

# "At least one of the top K" figures to compute per pool. Top 3 is the headline
# the page highlights for regular bots.
AT_LEAST_ONE_KS = (1, 2, 3, 4, 5)

# A bot needs at least this many prior discounts to be ranked or scored.
# Recently-added bots (0 or 1 discounts) have no established cadence and would
# otherwise dominate the "most overdue" ranking, so they are excluded from both
# the predictions (numerator) and the accuracy backtest (denominator).
MIN_HISTORY = 2


def _slug_to_date(slug: str) -> date:
    return datetime.strptime(slug, "%Y-%m-%d").date()


def _prior_count(weeknums, as_of_week: int) -> int:
    return sum(1 for w in weeknums if w < as_of_week)


def _week_number(d: date, origin: date) -> int:
    """Integer week index of a date relative to the first discount ever seen."""
    return round((d - origin).days / 7)


def _rank_pool(pool_weeknums: dict, as_of_week: int, min_history: int = MIN_HISTORY) -> list[str]:
    """Rank a pool's bots by weeks-since-discount, most overdue first.

    ``pool_weeknums`` maps bot_id -> sorted list of week-numbers it was
    discounted. Only discounts strictly before ``as_of_week`` are considered, so
    the ranking never peeks at the week it is predicting. Bots with fewer than
    ``min_history`` prior discounts are omitted -- they have no established
    cadence yet.

    Ties break on bot_id descending, purely for deterministic output.
    """
    candidates = []
    for bot_id, weeknums in pool_weeknums.items():
        prior = [w for w in weeknums if w < as_of_week]
        if len(prior) < min_history:
            continue
        wsd = as_of_week - prior[-1]
        candidates.append((wsd, bot_id))
    candidates.sort(reverse=True)
    return [bot_id for _wsd, bot_id in candidates]


def _calibrate(pool_weeknums: dict, period_actuals: list[tuple[int, set]], top_n: int,
               min_history: int = MIN_HISTORY) -> dict:
    """Walk-forward backtest for one pool.

    ``period_actuals`` is a chronologically-ascending list of
    ``(week_number, set_of_bot_ids_discounted_that_period)``.

    For every scorable period (one where the prior history can produce at least
    ``top_n`` ranked candidates), we rank as-of that period and check the
    predictions against what was actually discounted. Returns per-position hit
    rates, per-slot precision, and empirical "at least one of top K" rates.

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

    for as_of_week, actual in period_actuals:
        ranking = _rank_pool(pool_weeknums, as_of_week, min_history)
        if len(ranking) < top_n:
            continue
        # Restrict the target set to bots that are eligible to be ranked, so a
        # discount of an ineligible (too-new) bot counts as neither a hit nor a
        # miss -- excluded from numerator and denominator alike.
        eligible = {
            bot_id for bot_id, weeknums in pool_weeknums.items()
            if _prior_count(weeknums, as_of_week) >= min_history
        }
        actual = actual & eligible
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
    }


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

    Keys: ``pools`` (name -> {bot_id: sorted week-numbers}), ``meta`` (bot_id ->
    display metadata), ``origin`` (date fixing week-number 0), ``all_weeknums``
    (sorted, both pools), ``manifest``, and the raw ``vbot_data`` /
    ``modules_data`` / ``preset_data`` needed to resolve gear.
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
    for ref, info in vbots.items():
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

    return {
        "discount_data": discount_data,
        "manifest": manifest,
        "vbot_data": vbot_data,
        "modules_data": modules_data,
        "preset_data": preset_data,
        "pools": pools,
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

    pa = period_actuals(pool_weeknums, all_weeknums, max_weeknum=calib_max_weeknum)
    calib = _calibrate(pool_weeknums, pa, top_n)

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
    ranking = _rank_pool(pool_weeknums, as_of_weeknum)[:top_n]
    # When reconstructing a very early week the backtest may have scored so few
    # prior weeks that no rank slot has ever been hit -- every position then
    # calibrates to 0%, which reads as a confident "no chance" rather than the
    # truth ("not enough history to estimate yet"). Detect that degenerate case
    # and surface the likelihood as null so the UI can say so instead of 0%.
    # Live predictions always have hits, so this never fires for them.
    odds = calib[odds_key]
    odds_available = any(odds[i] > 0 for i in range(len(ranking)))
    listed = []
    for i, bot_id in enumerate(ranking):
        last_week = [w for w in pool_weeknums[bot_id] if w < as_of_weeknum]
        last_week = last_week[-1] if last_week else pool_weeknums[bot_id][-1]
        listed.append({
            "ref": meta[bot_id]["ref"],
            "id": bot_id,
            "name": meta[bot_id]["name"],
            "icon_path": meta[bot_id]["icon_path"],
            "items_anchor": meta[bot_id]["items_anchor"],
            "overdue_rank": i + 1,
            "weeks_since_discount": as_of_weeknum - last_week,
            "avg_interval": meta[bot_id]["avg_interval"],
            "likelihood_pct": round(odds[i] * 100, 1) if odds_available else None,
            "associated": (
                _resolve_gear(bot_id, ctx["vbot_data"], ctx["modules_data"], ctx["preset_data"])
                if include_gear else []
            ),
        })
    # The most-overdue bot is not necessarily the most likely (a very long dry
    # spell often means a bot that keeps getting skipped), so present the list
    # ordered by its calibrated likelihood to match the "most likely" framing.
    # With no odds available, fall back to most-overdue-first via the tiebreak.
    listed.sort(
        key=lambda b: (
            b["likelihood_pct"] if b["likelihood_pct"] is not None else -1.0,
            b["weeks_since_discount"],
        ),
        reverse=True,
    )
    return listed, calib


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
        "method": "weeks-since-discount (most overdue first); position-calibrated odds",
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
    graded week (eligibility-restricted, so too-new bots are neither hit nor
    miss). ``headline_k`` (e.g. 3 for bots) reports whether at least one of the
    K most-overdue picks was discounted -- the same framing as the calibration
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
        top_k = {p["id"] for p in listed if p["overdue_rank"] <= headline_k}
        result["top3_hit"] = bool(top_k & actual_ids)
    return result


def _eligible_actual(pool_weeknums, weeknum):
    """Bot_ids of this pool discounted in ``weeknum`` that were eligible then."""
    return {
        bot_id for bot_id, weeknums in pool_weeknums.items()
        if weeknum in weeknums and _prior_count(weeknums, weeknum) >= MIN_HISTORY
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

    # A pool is "insufficient" when the prior history cannot produce a full slate
    # of ranked candidates -- there is not yet an established cadence to predict
    # from, so the week is shown as such and left out of the scoreboard.
    bots_insufficient = len(bots) < BOTS_TOP_N
    titans_insufficient = len(titans) < TITANS_TOP_N
    if bots_insufficient:
        bots = []
    if titans_insufficient:
        titans = []
    insufficient = {"bots": bots_insufficient, "titans": titans_insufficient}

    actual_bots = _eligible_actual(ctx["pools"]["Mech"], weeknum)
    actual_titans = _eligible_actual(ctx["pools"]["Titan"], weeknum)
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
        "method": "weeks-since-discount; walk-forward, history-before-week only",
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
