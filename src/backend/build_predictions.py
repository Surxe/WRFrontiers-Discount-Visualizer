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
    VIRTUAL_BOT_JSON,
    MODULE_JSON,
    CHARACTER_PRESET_JSON,
    STANDALONE_MODULE_GROUPS,
)
from week_dates import format_week, normalize_week, week_slug

# Discountable module groups that ride along with a regular bot's factory
# loadout. Titan weapons are excluded (they never co-discount with a mech).
GEAR_GROUPS = {g for g in STANDALONE_MODULE_GROUPS if g != "titan-weapon"}

# How many bots to surface per pool on the page.
BOTS_TOP_N = 5
TITANS_TOP_N = 2

# "At least one of the top K" figures to compute per pool. Top 3 is the headline
# the page highlights for regular bots.
AT_LEAST_ONE_KS = (1, 2, 3, 4, 5)


def _slug_to_date(slug: str) -> date:
    return datetime.strptime(slug, "%Y-%m-%d").date()


def _week_number(d: date, origin: date) -> int:
    """Integer week index of a date relative to the first discount ever seen."""
    return round((d - origin).days / 7)


def _rank_pool(pool_weeknums: dict, as_of_week: int) -> list[str]:
    """Rank a pool's bots by weeks-since-discount, most overdue first.

    ``pool_weeknums`` maps bot_id -> sorted list of week-numbers it was
    discounted. Only discounts strictly before ``as_of_week`` are considered, so
    the ranking never peeks at the week it is predicting. Bots with no prior
    discount are omitted (no baseline to measure overdue-ness from).

    Ties break on bot_id descending, purely for deterministic output.
    """
    candidates = []
    for bot_id, weeknums in pool_weeknums.items():
        prior = [w for w in weeknums if w < as_of_week]
        if not prior:
            continue
        wsd = as_of_week - prior[-1]
        candidates.append((wsd, bot_id))
    candidates.sort(reverse=True)
    return [bot_id for _wsd, bot_id in candidates]


def _calibrate(pool_weeknums: dict, period_actuals: list[tuple[int, set]], top_n: int) -> dict:
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
        ranking = _rank_pool(pool_weeknums, as_of_week)
        if len(ranking) < top_n:
            continue
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


def build_predictions():
    print("  -> Building upcoming-week predictions...")

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

    # Chronological (week_number, discounted-set) per pool for the backtest.
    def period_actuals(pool_weeknums):
        by_week = {w: set() for w in all_weeknums}
        for bot_id, weeknums in pool_weeknums.items():
            for w in weeknums:
                by_week[w].add(bot_id)
        return sorted(by_week.items())

    # Predicted week + its week-number.
    pred_week = _predicted_week(manifest)
    pred_start = date(pred_week["start_year"], pred_week["start_month"], pred_week["start_day"])
    pred_weeknum = _week_number(pred_start, origin)
    pred_label = format_week(pred_week, style="long")
    pred_slug = week_slug(pred_week)

    def build_pool(pool_name, top_n, conditional=False, include_gear=False):
        # conditional=True frames each likelihood as "if a bot from this pool is
        # discounted, the odds it is this one" -- used for titans, which are
        # discounted in a minority of weeks so an unconditional odds reads as
        # misleadingly low. include_gear attaches each bot's factory loadout
        # (regular bots only).
        pool_weeknums = pools[pool_name]
        calib = _calibrate(pool_weeknums, period_actuals(pool_weeknums), top_n)
        odds_key = "per_position_conditional" if conditional else "per_position"
        ranking = _rank_pool(pool_weeknums, pred_weeknum)[:top_n]
        listed = []
        for i, bot_id in enumerate(ranking):
            last_week = pool_weeknums[bot_id][-1]
            listed.append({
                "ref": meta[bot_id]["ref"],
                "id": bot_id,
                "name": meta[bot_id]["name"],
                "icon_path": meta[bot_id]["icon_path"],
                "items_anchor": meta[bot_id]["items_anchor"],
                "overdue_rank": i + 1,
                "weeks_since_discount": pred_weeknum - last_week,
                "avg_interval": meta[bot_id]["avg_interval"],
                "likelihood_pct": round(calib[odds_key][i] * 100, 1),
                "associated": (
                    _resolve_gear(bot_id, vbot_data, modules_data, preset_data)
                    if include_gear else []
                ),
            })
        # The most-overdue bot is not necessarily the most likely (a very long dry
        # spell often means a bot that keeps getting skipped), so present the list
        # ordered by its calibrated likelihood to match the "most likely" framing.
        listed.sort(key=lambda b: (b["likelihood_pct"], b["weeks_since_discount"]), reverse=True)
        return listed, calib

    bots, bots_calib = build_pool("Mech", BOTS_TOP_N, include_gear=True)
    titans, titans_calib = build_pool("Titan", TITANS_TOP_N, conditional=True)

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


if __name__ == "__main__":
    build_predictions()
