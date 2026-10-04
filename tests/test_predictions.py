import json
import os
import sys
import unittest

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from build_predictions import (
    DiscountRateModel,
    _bot_state,
    _rank_pool,
    _calibrate,
    _pool_tied_odds,
    period_actuals,
    _grade_pool,
    BOTS_HEADLINE_MIN_HITS,
    MIN_PRIOR_WEEKS,
    STAGE_DISCOUNT,
    STAGE_RELEASE,
)

DATA_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'frontend', 'public', 'data'
)
PREDICTIONS_JSON = os.path.join(DATA_DIR, 'predictions.json')
HISTORY_INDEX_JSON = os.path.join(DATA_DIR, 'predictions_history', 'index.json')


class TestBotState(unittest.TestCase):
    def test_waits_from_last_prior_discount(self):
        self.assertEqual(_bot_state([0, 3], 5, None), (STAGE_DISCOUNT, 2))

    def test_discount_in_the_week_itself_is_not_prior(self):
        self.assertEqual(_bot_state([0, 5], 5, None), (STAGE_DISCOUNT, 5))

    def test_never_discounted_waits_from_release(self):
        self.assertEqual(_bot_state([], 10, 4), (STAGE_RELEASE, 6))

    def test_not_released_yet_is_none(self):
        self.assertIsNone(_bot_state([], 4, 4))
        self.assertIsNone(_bot_state([], 3, 4))

    def test_early_access_bot_anchors_at_origin(self):
        self.assertEqual(_bot_state([], 3, None), (STAGE_RELEASE, 3))


class TestDiscountRateModel(unittest.TestCase):
    def test_empty_model_is_the_prior(self):
        self.assertAlmostEqual(DiscountRateModel().rate(STAGE_DISCOUNT, 10), 0.1)

    def test_rate_counts_hits_over_basis_in_window(self):
        m = DiscountRateModel()
        # 'a' waits 2 at week 2 and is discounted; 'b' waits 2 and is not.
        pool = {'a': [0, 2], 'b': [0]}
        m.observe(pool, {}, 2, {'a'})
        # 1 hit / 2 basis at wait 2 (stage borrows nothing: release stage empty,
        # but basis < RATE_MIN_BASIS pulls in the empty other stage -> same).
        self.assertAlmostEqual(m.rate(STAGE_DISCOUNT, 2), (1 + 1) / (2 + 10))

    def test_unreleased_bots_are_not_observed(self):
        m = DiscountRateModel()
        m.observe({'n': []}, {'n': 5}, 3, set())
        self.assertEqual(m.basis, {})


class TestRankPool(unittest.TestCase):
    def test_new_bot_is_ranked_from_release(self):
        pool = {'old': [0, 3], 'new': []}
        ranking = _rank_pool(pool, 9, {'new': 1}, DiscountRateModel())
        # Empty model ties every rate, so the longer wait wins: new waits 8.
        self.assertEqual([c['id'] for c in ranking], ['new', 'old'])
        self.assertEqual(ranking[0]['stage'], STAGE_RELEASE)

    def test_unreleased_bot_is_excluded(self):
        pool = {'old': [0, 3], 'future': []}
        ranking = _rank_pool(pool, 5, {'future': 7}, DiscountRateModel())
        self.assertEqual([c['id'] for c in ranking], ['old'])

    def test_rate_outranks_raw_wait(self):
        """A bot far past the usual cycle ranks below one at a historically
        productive wait -- the Bulgasari case the old most-overdue rule missed."""
        m = DiscountRateModel()
        m.hits[(STAGE_DISCOUNT, 10)] = 8
        m.basis[(STAGE_DISCOUNT, 10)] = 10
        m.basis[(STAGE_DISCOUNT, 30)] = 10
        pool = {'stale': [0], 'due': [20]}
        ranking = _rank_pool(pool, 30, {}, m)
        self.assertEqual([c['id'] for c in ranking], ['due', 'stale'])


class TestCalibrate(unittest.TestCase):
    def _history(self, pool):
        by_week = {}
        for bot, weeks in pool.items():
            for w in weeks:
                by_week.setdefault(w, set()).add(bot)
        return sorted(by_week.items())

    def test_skips_weeks_without_enough_prior_history(self):
        pool = {'a': list(range(0, 20, 2)), 'b': list(range(1, 20, 2))}
        pa = self._history(pool)
        calib, model = _calibrate(pool, pa, top_n=2, release_weeks={})
        self.assertEqual(calib['scored_weeks'], len(pa) - MIN_PRIOR_WEEKS)
        # The returned model has observed every period.
        # No release dates -> both bots exist every period.
        self.assertEqual(sum(model.basis.values()), 2 * len(pa))

    def test_new_bot_discount_is_a_target(self):
        """A week where only a freshly released bot was discounted must count as
        a pool-discount week (it used to be dropped from grading altogether)."""
        pool = {'a': list(range(0, 17, 2)), 'b': list(range(1, 17, 2)), 'n': [18]}
        pa = self._history(pool)
        calib, _ = _calibrate(pool, pa, top_n=1, release_weeks={'n': 15})
        self.assertEqual(pa[-1], (18, {'n'}))
        self.assertEqual(calib['any_weeks'], calib['scored_weeks'])

    def test_at_least_one_is_non_decreasing_in_k(self):
        pool = {
            'a': [0, 2, 4, 6, 8, 10, 12, 14],
            'b': [0, 3, 6, 9, 12],
            'c': [1, 5, 9, 13],
            'd': [2, 7, 11, 15],
        }
        calib, _ = _calibrate(pool, self._history(pool), top_n=3, release_weeks={})
        vals = [calib['at_least_one'][str(k)] for k in (1, 2, 3)]
        self.assertTrue(all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)))


class TestPoolTiedOdds(unittest.TestCase):
    def test_averages_runs_of_tied_positions(self):
        # Slots 1,2,3 are tied (wsd 11); slot 0 and slot 4 stand alone.
        odds = [0.20, 0.5333, 0.3778, 0.2667, 0.1556]
        wsd = [27, 11, 11, 11, 10]
        pooled = _pool_tied_odds(odds, wsd)
        shared = (0.5333 + 0.3778 + 0.2667) / 3
        self.assertAlmostEqual(pooled[0], 0.20, places=6)      # untied
        self.assertAlmostEqual(pooled[1], shared, places=6)
        self.assertAlmostEqual(pooled[2], shared, places=6)
        self.assertAlmostEqual(pooled[3], shared, places=6)
        self.assertAlmostEqual(pooled[4], 0.1556, places=6)    # untied
        # Pooling redistributes but never changes the total expected hits.
        self.assertAlmostEqual(sum(pooled), sum(odds), places=6)

    def test_no_ties_is_identity(self):
        odds = [0.5, 0.4, 0.3]
        self.assertEqual(_pool_tied_odds(odds, [5, 4, 3]), odds)

    def test_all_tied_flattens_to_the_mean(self):
        odds = [0.6, 0.3, 0.0]
        pooled = _pool_tied_odds(odds, [7, 7, 7])
        self.assertTrue(all(abs(p - 0.3) < 1e-9 for p in pooled))


class TestGeneratedPredictions(unittest.TestCase):
    """Invariants on the on-disk predictions.json (skipped if not generated)."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(PREDICTIONS_JSON):
            raise unittest.SkipTest('predictions.json not generated')
        with open(PREDICTIONS_JSON, encoding='utf-8') as f:
            cls.data = json.load(f)

    def test_shape_and_bounds(self):
        d = self.data
        self.assertIn('predictedWeek', d)
        self.assertIn('label', d['predictedWeek'])
        self.assertLessEqual(len(d['bots']), 5)
        self.assertLessEqual(len(d['titans']), 2)
        for bot in d['bots'] + d['titans']:
            self.assertGreaterEqual(bot['likelihood_pct'], 0)
            self.assertLessEqual(bot['likelihood_pct'], 100)
            # Exactly one wait is set: since last discount, or since release.
            waits = [bot['weeks_since_discount'], bot['weeks_since_release']]
            self.assertEqual(sum(w is not None for w in waits), 1)
            self.assertGreater(next(w for w in waits if w is not None), 0)
            self.assertGreater(bot['historical_rate_pct'], 0)

    def test_lists_sorted_by_likelihood_desc(self):
        for key in ('bots', 'titans'):
            pcts = [b['likelihood_pct'] for b in self.data[key]]
            self.assertEqual(pcts, sorted(pcts, reverse=True))

    def test_regular_bots_carry_gear_and_avg_titans_do_not(self):
        for bot in self.data['bots']:
            self.assertIn('associated', bot)
            self.assertIsInstance(bot['associated'], list)
            self.assertIn('items_anchor', bot)
            self.assertTrue(bot['items_anchor'].startswith('bot-'))
            self.assertIn('avg_interval', bot)
        # Titans are display-only for gear (no factory-weapon bundling shown).
        for titan in self.data['titans']:
            self.assertEqual(titan.get('associated', []), [])

    def test_gear_items_are_well_formed(self):
        for bot in self.data['bots']:
            for gear in bot['associated']:
                self.assertIn('name', gear)
                self.assertIn('group', gear)
                self.assertIn(
                    gear['group'],
                    {'light-weapon', 'heavy-weapon', 'supply-gear', 'cycle-gear'},
                )

    def test_accuracy_precision_matches_positions(self):
        for pool in ('bots', 'titans'):
            acc = self.data['accuracy'][pool]
            per_pos = acc['per_position']
            expected = round(sum(per_pos) / len(per_pos), 4)
            self.assertAlmostEqual(acc['precision'], expected, places=3)

    def test_tied_bots_share_pooled_odds(self):
        """Robots tied on historical discount rate must show identical odds -- an
        arbitrary tiebreak may not open a likelihood gap between equals."""
        for key in ('bots', 'titans'):
            by_rate = {}
            for b in self.data[key]:
                by_rate.setdefault(b['historical_rate_pct'], []).append(b['likelihood_pct'])
            for rate, pcts in by_rate.items():
                self.assertEqual(
                    len(set(pcts)), 1,
                    f"{key} tied at rate={rate} show differing odds {pcts}",
                )

    def test_methodology_example_reproduces_top_card(self):
        """The /methodology worked example must match the top robot's card, so the
        page's arithmetic can never contradict it -- pooling the tied slots when
        the top card is tied, else the single overdue-rank slot's rate."""
        m = self.data.get('methodology')
        if not self.data['bots']:
            self.assertIsNone(m)
            return
        self.assertIsNotNone(m)
        ex = m['example']
        top = self.data['bots'][0]
        # Example is the top displayed robot.
        self.assertEqual(ex['bot_id'], top['id'])
        self.assertEqual(ex['likelihood_pct'], top['likelihood_pct'])
        self.assertEqual(ex['rank'], top['rank'])
        self.assertEqual(ex['historical_rate_pct'], top['historical_rate_pct'])
        per_pos = self.data['accuracy']['bots']['per_position']
        scored = self.data['accuracy']['bots']['scored_weeks']
        self.assertEqual(m['scored_weeks'], scored)
        # The example's own-slot fields always describe its overdue-rank slot.
        slot_rate = per_pos[ex['rank'] - 1]
        self.assertAlmostEqual(ex['slot_hit_rate'], slot_rate, places=4)
        self.assertEqual(ex['slot_hits'], round(slot_rate * scored))
        # The shown % is the mean of the tied slots' rates (a lone card is a
        # one-slot tie group, so this reduces to that slot's rate).
        tie_rates = [per_pos[r - 1] for r in ex['tie_ranks']]
        self.assertIn(ex['rank'], ex['tie_ranks'])
        self.assertEqual(ex['pooled'], len(ex['tie_ranks']) > 1)
        expected_pct = round(sum(tie_rates) / len(tie_rates) * 100, 1)
        self.assertAlmostEqual(ex['likelihood_pct'], expected_pct, places=1)


class TestPeriodActualsCutoff(unittest.TestCase):
    """Walk-forward reconstruction must not peek past the target week."""

    def test_max_weeknum_excludes_the_week_and_later(self):
        pool = {'a': [0, 2, 4], 'b': [1, 3]}
        all_weeknums = [0, 1, 2, 3, 4]
        pa = period_actuals(pool, all_weeknums, max_weeknum=3)
        weeks = [w for w, _ in pa]
        self.assertEqual(weeks, [0, 1, 2])  # 3 and 4 excluded
        self.assertEqual(dict(pa), {0: {'a'}, 1: {'b'}, 2: {'a'}})

    def test_no_cutoff_covers_all_weeks(self):
        pool = {'a': [0, 2], 'b': [1]}
        pa = period_actuals(pool, [0, 1, 2], max_weeknum=None)
        self.assertEqual([w for w, _ in pa], [0, 1, 2])


class TestGradePool(unittest.TestCase):
    def test_marks_hits_and_headline(self):
        listed = [
            {'id': 'x', 'rank': 2},  # display order != rank order
            {'id': 'y', 'rank': 1},
            {'id': 'z', 'rank': 4},
        ]
        result = _grade_pool(listed, {'x', 'z'}, headline_k=3)
        self.assertEqual([p['hit'] for p in listed], [True, False, True])
        self.assertEqual(result['hits'], 2)
        self.assertEqual(result['listed'], 3)
        self.assertEqual(result['eligible_actual'], 2)
        self.assertTrue(result['top_hit'])       # listed[0] ('x') was discounted
        self.assertTrue(result['top3_hit'])      # rank<=3 picks x,y; x hit

    def test_top3_ignores_picks_below_rank_3(self):
        listed = [
            {'id': 'y', 'rank': 1},
            {'id': 'z', 'rank': 5},
        ]
        # Only the rank-5 pick was discounted -> not a top-3 hit.
        result = _grade_pool(listed, {'z'}, headline_k=3)
        self.assertFalse(result['top3_hit'])
        self.assertFalse(result['top_hit'])
        self.assertEqual(result['hits'], 1)


class TestPredictionHistoryIndex(unittest.TestCase):
    """Invariants on the on-disk prediction history (skipped if not generated)."""

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(HISTORY_INDEX_JSON):
            raise unittest.SkipTest('prediction history not generated')
        with open(HISTORY_INDEX_JSON, encoding='utf-8') as f:
            cls.index = json.load(f)

    def test_scoreboard_windowed_to_recent_weeks(self):
        board = self.index['scoreboard']
        # Rows are newest-first; the scoreboard summarizes only the recent window.
        recent = self.index['weeks'][:board['window_weeks']]
        self.assertLessEqual(board['window_weeks'], len(self.index['weeks']))

        # Bots headline: at least 2 of the top 5 predicted robots were discounted.
        scored = [r for r in recent if not r['insufficient_history']['bots']]
        hits = sum(1 for r in scored if r['result']['bots'].get('headline_hit'))
        self.assertEqual(board['bots_scored_weeks'], len(scored))
        self.assertEqual(board['bots_hits'], hits)
        if scored:
            self.assertAlmostEqual(board['bots_rate'], hits / len(scored), places=3)
        # headline_hit must agree with the raw hit count on every scored week.
        for r in scored:
            self.assertEqual(
                r['result']['bots']['headline_hit'],
                r['result']['bots']['hits'] >= BOTS_HEADLINE_MIN_HITS,
            )

        # A titan week is correct when the top titan hit OR no titan appeared.
        t_scored = [r for r in recent if not r['insufficient_history']['titans']]
        t_hits = sum(
            1 for r in t_scored
            if r['result']['titans'].get('top_hit') or not r['result']['titans'].get('any_titan')
        )
        self.assertEqual(board['titans_scored_weeks'], len(t_scored))
        self.assertEqual(board['titans_hits'], t_hits)

    def test_every_row_snapshot_exists_and_is_consistent(self):
        for row in self.index['weeks']:
            snap_path = os.path.join(DATA_DIR, row['file'])
            self.assertTrue(os.path.exists(snap_path), f"missing snapshot {row['file']}")
            with open(snap_path, encoding='utf-8') as f:
                snap = json.load(f)
            self.assertEqual(snap['slug'], row['slug'])
            self.assertTrue(snap['reconstructed'])
            # Insufficient pools carry no picks; sufficient bot pools are full.
            if row['insufficient_history']['bots']:
                self.assertEqual(snap['bots'], [])
            else:
                self.assertEqual(len(snap['bots']), 5)
            # Each pick's hit flag must agree with the graded actuals set.
            for pick in snap['bots']:
                self.assertEqual(pick['hit'], pick['id'] in snap['actuals']['bots'])
            # Odds are suppressed (null) together when the pool has no calibration
            # basis yet, never a confusing all-zero slate.
            if snap['bots']:
                available = snap['odds_available']['bots']
                for pick in snap['bots']:
                    self.assertEqual(pick['likelihood_pct'] is not None, available)
                if available:
                    # If odds are shown, at least one slot must be non-zero.
                    self.assertTrue(any(p['likelihood_pct'] for p in snap['bots']))


if __name__ == '__main__':
    unittest.main()
