import json
import os
import sys
import unittest

# Add src/backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))

from build_predictions import _rank_pool, _calibrate

PREDICTIONS_JSON = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'frontend', 'public', 'data', 'predictions.json'
)


class TestRankPool(unittest.TestCase):
    def test_ranks_by_weeks_since_discount_and_excludes_no_history(self):
        pool = {
            'a': [0, 2],   # last prior discount at week 2 -> wsd 1
            'b': [1],      # last prior discount at week 1 -> wsd 2 (more overdue)
            'c': [5],      # first discount not before as_of -> excluded
        }
        ranking = _rank_pool(pool, as_of_week=3)
        self.assertEqual(ranking, ['b', 'a'])

    def test_only_counts_discounts_strictly_before(self):
        # A discount exactly at as_of_week must not count as prior history.
        pool = {'a': [3], 'b': [0]}
        self.assertEqual(_rank_pool(pool, as_of_week=3), ['b'])


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
        result = _calibrate(pool, period_actuals, top_n=2)

        self.assertEqual(result['scored_weeks'], 5)
        self.assertEqual(result['per_position'], [0.2, 0.6])
        self.assertEqual(result['precision'], 0.4)
        self.assertEqual(result['at_least_one'], {'1': 0.2, '2': 0.8})

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


if __name__ == '__main__':
    unittest.main()
