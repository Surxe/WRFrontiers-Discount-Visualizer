import json
import os
import sys
import unittest

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from build_predictions import (
    _rank_pool,
    _calibrate,
    period_actuals,
    _grade_pool,
    BOTS_HEADLINE_MIN_HITS,
)

DATA_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'frontend', 'public', 'data'
)
PREDICTIONS_JSON = os.path.join(DATA_DIR, 'predictions.json')
HISTORY_INDEX_JSON = os.path.join(DATA_DIR, 'predictions_history', 'index.json')


class TestRankPool(unittest.TestCase):
    def test_ranks_by_wsd_and_excludes_thin_history(self):
        pool = {
            'a': [0, 3],      # 2 priors -> wsd 5-3 = 2
            'b': [1],         # only 1 prior -> excluded (no established cadence)
            'c': [2, 4],      # 2 priors -> wsd 5-4 = 1
        }
        ranking = _rank_pool(pool, as_of_week=5)
        self.assertEqual(ranking, ['a', 'c'])
        self.assertNotIn('b', ranking)

    def test_only_counts_discounts_strictly_before(self):
        # A discount exactly at as_of_week must not count as prior history, so
        # 'b' has only one qualifying prior and is excluded.
        pool = {'a': [0, 3], 'b': [0, 5]}
        self.assertEqual(_rank_pool(pool, as_of_week=5), ['a'])

    def test_min_history_is_configurable(self):
        pool = {'a': [1], 'b': [0, 2]}
        self.assertEqual(_rank_pool(pool, as_of_week=3, min_history=1), ['a', 'b'])


class TestCalibrate(unittest.TestCase):
    def test_matches_hand_computed_scenario(self):
        pool = {
            'a': [0, 2, 4, 6],
            'b': [0, 3, 6],
            'c': [1],
        }
        # (week_number, discounted set) chronologically ascending.
        period_actuals = [
            (0, {'a', 'b'}),
            (1, {'c'}),
            (2, {'a'}),
            (3, {'b'}),
            (4, {'a'}),
            (6, {'a', 'b'}),
        ]
        # With MIN_HISTORY=2, only weeks 4 and 6 are scorable (two eligible bots):
        #   wk4: rank [a(wsd2), b(wsd1)], actual {a} -> pos1 hit
        #   wk6: rank [b(wsd3), a(wsd2)], actual {a,b} -> both slots hit
        result = _calibrate(pool, period_actuals, top_n=2)

        self.assertEqual(result['scored_weeks'], 2)
        self.assertEqual(result['per_position'], [1.0, 0.5])
        self.assertEqual(result['precision'], 0.75)
        self.assertEqual(result['at_least_one'], {'1': 1.0, '2': 1.0})

    def test_at_least_one_is_non_decreasing_in_k(self):
        pool = {
            'a': [0, 2, 4, 6, 8],
            'b': [0, 3, 6],
            'c': [1, 5],
            'd': [2, 7],
        }
        period_actuals = []
        by_week = {}
        for bot, weeks in pool.items():
            for w in weeks:
                by_week.setdefault(w, set()).add(bot)
        period_actuals = sorted(by_week.items())

        result = _calibrate(pool, period_actuals, top_n=3)
        vals = [result['at_least_one'][str(k)] for k in (1, 2, 3)]
        self.assertTrue(all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)))


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
            self.assertGreaterEqual(bot['weeks_since_discount'], 0)

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
            {'id': 'x', 'overdue_rank': 2},  # display order != rank order
            {'id': 'y', 'overdue_rank': 1},
            {'id': 'z', 'overdue_rank': 4},
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
            {'id': 'y', 'overdue_rank': 1},
            {'id': 'z', 'overdue_rank': 5},
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
