import unittest
from collections import Counter
import copy
from pathlib import Path
import tempfile

from packages.action_core.continuity_fresh import make_dataset, native_row, PLANNING
from packages.action_core.episode import Episode, encode_config
from packages.action_core.planner import Goal
from packages.action_core.world import Sandbox
from packages.action_core.tests.test_life import ScriptedClient


class ScheduleTests(unittest.TestCase):
    def test_schedule_reconstructs_balances_and_has_disjoint_halves(self):
        data = make_dataset(4123)
        self.assertEqual(data, make_dataset(4123))
        self.assertNotEqual(data, make_dataset(4124))
        self.assertEqual({x['life'] for x in data['lives']}, set(range(16)))
        self.assertEqual(Counter(x['arm_order'][0] for x in data['lives']), {'carry': 8, 'reset': 8})
        balance = Counter()
        names = set()
        for life in data['lives']:
            self.assertEqual(set(life['arm_order']), {'carry', 'reset'})
            self.assertEqual([c['index'] for c in life['cases']], list(range(8)))
            self.assertEqual(len({c['case'] for c in life['cases']}), 8)
            for half in range(2):
                cases = life['cases'][half * 4:(half + 1) * 4]
                self.assertEqual({c['stratum'] for c in cases}, set(range(4)))
                self.assertEqual(sum(c['missing_parent'] for c in cases), 2)
                for case in cases:
                    balance[half, case['stratum'], case['missing_parent']] += 1
                    self.assertNotIn(case['goal']['id'], names)
                    names.add(case['goal']['id'])
        self.assertEqual(set(balance.values()), {8})
        self.assertEqual(len(balance), 16)
        self.assertEqual(PLANNING['revisit_weight'], 0)


class NativeRowTests(unittest.TestCase):
    def test_native_result_accepted_but_forged_caller_stop_rejected(self):
        config = {'paths': ['reference', 'folder', 'folder/out'],
                  'initial': {'reference': b'actual-evidence'}, 'protected': {'n0'}}
        goal = Goal('native', (('n2', 1),), (('n0', 'n2'),))
        case = {'index': 0, 'stratum': 0, 'missing_parent': True,
                'config': encode_config(config), 'goal': goal.to_dict()}
        with tempfile.TemporaryDirectory(prefix='atanor-native-row-') as temp:
            root = Path(temp)
            body = Sandbox(root / 'body', **config)
            db = root / 'episode.sqlite'
            episode = Episode(db, body, goal, ScriptedClient(), config=config, budget=8)
            try:
                stop = episode.run()
            finally:
                episode.close()
            entry = {'phase': 'done', 'index': 0, 'db_path': str(db), 'stop': stop}
            row = native_row(entry, case, 0, 'carry')
            self.assertTrue(row['success'])
            self.assertEqual(row['charged_steps'], 2)
            forged = copy.deepcopy(entry)
            forged['stop']['completed'] = False
            with self.assertRaisesRegex(ValueError, 'native completion/dispatch disagreement'):
                native_row(forged, case, 0, 'carry')
            forged = copy.deepcopy(entry)
            forged['stop']['steps'] = 1
            with self.assertRaisesRegex(ValueError, 'native completion/dispatch disagreement'):
                native_row(forged, case, 0, 'carry')


if __name__ == '__main__':
    unittest.main()
