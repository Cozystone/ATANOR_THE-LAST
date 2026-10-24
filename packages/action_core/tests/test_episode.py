import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from packages.action_core.episode import Episode, canonical, verify_episode
from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Sandbox


class FakeClient:
    def __init__(self, script, malicious=None):
        self.script, self.malicious, self.revision, self.calls = list(script), malicious, 0, 0

    def choose(self, frame, goal, actions, history):
        self.calls += 1
        # Deliberately predicts success everywhere, including when the action fails.
        n = len(frame.handles)
        forecast = Forecast([[0., 1., 0.] for _ in range(n)], [0.] * n,
                            [[1.] * n for _ in range(n)], frame.parent, frame.handles)
        if self.malicious == 'authority':
            original = forecast.to_dict
            forecast.to_dict = lambda: dict(original(), verified=True)
        action = self.script.pop(0) if self.script else Action('empty', ('n2',))
        return action, forecast, 1

    def learn(self, event_id, before, action, after, history):
        self.revision += 1
        return True

    def snapshot(self):
        return {'revision': self.revision}

    def restore(self, snapshot):
        self.revision = snapshot['revision']


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atanor_episode_test_')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.config = {'paths': ['ref', 'folder', 'folder/output'],
                       'initial': {'ref': b'genuine'}, 'protected': {'n0'}}
        self.goal = Goal('g0', kinds=(('n2', 1),), equal=(('n0', 'n2'),))
        self.body = Sandbox(self.base / 'body', **self.config)
        self.path = self.base / 'events.sqlite'

    def episode(self, client, budget=2):
        ep = Episode(self.path, self.body, self.goal, client, config=self.config, budget=budget)
        self.addCleanup(ep.close)
        return ep

    def verify(self, budget=2, **kw):
        return verify_episode(self.path, expected_config=kw.get('config', self.config),
                              expected_goal=self.goal, expected_budget=budget)

    def test_actual_success_replays_and_durable_resume(self):
        client = FakeClient([Action('mkdir', ('n1',)), Action('copy', ('n0', 'n2'))])
        ep = self.episode(client)
        ep.step()
        ep.close()
        ep = self.episode(client)
        result = ep.run()
        self.assertTrue(result['completed'])
        self.assertEqual(result['steps'], 2)
        self.assertEqual(result['reason'], 'goal_reached')
        self.assertTrue(self.verify()['green'], self.verify())

    def test_false_predicted_success_not_adopted_and_budget_prevents_mutation(self):
        client = FakeClient([Action('copy', ('n0', 'n2'))])
        result = self.episode(client, 1).run()
        self.assertFalse(result['completed'])
        self.assertEqual(result['reason'], 'step_budget_exceeded')
        self.assertEqual(client.calls, 1)
        self.assertEqual(self.body.evidence()['n2']['kind'], 0)
        self.assertTrue(self.verify(1)['green'], self.verify(1))

    def test_zero_budget_does_not_ask_or_mutate(self):
        client = FakeClient([Action('mkdir', ('n1',))])
        result = self.episode(client, 0).run()
        self.assertEqual(client.calls, 0)
        self.assertFalse(result['completed'])
        self.assertTrue(self.verify(0)['green'])

    def test_extra_authority_and_invalid_action_are_rejected(self):
        for label, action, malicious in [('authority', Action('mkdir', ('n1',)), 'authority'),
                                          ('handle', Action('empty', ('../bad',)), None),
                                          ('protected', Action('empty', ('n0',)), None)]:
            with self.subTest(label=label):
                path = self.base / (label + '.sqlite')
                ep = Episode(path, self.body, self.goal, FakeClient([action], malicious),
                             config=self.config, budget=2)
                result = ep.run()
                ep.close()
                self.assertEqual(result['reason'], 'invalid_proposal')
                self.assertEqual(result['steps'], 0)
                self.assertEqual(self.body.evidence()['n0']['size_bytes'], 7)
                self.assertEqual(self.body.evidence()['n1']['kind'], 0)

    def test_pending_restart_reobserves_without_blind_retry(self):
        client = FakeClient([Action('mkdir', ('n1',))])
        ep = self.episode(client)
        ep._record('FORECAST', {'interrupted_test': True}, pending={'phase': 'proposed'})
        ep.close()
        resumed = self.episode(client)
        result = resumed.run()
        self.assertEqual(result['reason'], 'interrupted')
        self.assertEqual(client.calls, 0)
        self.assertEqual(self.body.evidence()['n1']['kind'], 0)
        self.assertFalse(self.verify()['green'])

    def test_crash_after_native_mutation_never_repeats_dispatch(self):
        client = FakeClient([Action('mkdir', ('n1',))])
        ep = self.episode(client)
        native_step = self.body.step
        def interrupted(action):
            native_step(action)
            raise KeyboardInterrupt('synthetic crash after mutation')
        with patch.object(self.body, 'step', interrupted):
            with self.assertRaises(KeyboardInterrupt):
                ep.step()
        ep.close()
        self.assertEqual(self.body.evidence()['n1']['kind'], 2)
        resumed = self.episode(client)
        result = resumed.run()
        self.assertEqual(result['reason'], 'interrupted')
        self.assertEqual(result['steps'], 1)
        self.assertEqual(client.calls, 1)
        self.assertFalse(self.verify()['green'])

    def test_trace_self_seal_does_not_override_external_body_or_native_replay(self):
        ep = self.episode(FakeClient([Action('copy', ('n0', 'n2'))]), 1)
        ep.run()
        ep.close()
        db = sqlite3.connect(self.path)
        rows = list(db.execute('SELECT seq,kind,payload FROM events ORDER BY seq'))
        previous = ''
        for seq, kind, text in rows:
            payload = json.loads(text)
            if kind == 'RESULT':
                payload['completed'] = True
            text = canonical(payload)
            sha = hashlib.sha256((previous + kind + text).encode()).hexdigest()
            db.execute('UPDATE events SET payload=?,digest=? WHERE seq=?', (text, sha, seq))
            previous = sha
        db.commit()
        db.close()
        result = self.verify(1)
        self.assertFalse(result['green'])
        self.assertIn('actual_result_mismatch', result['errors'])
        changed = dict(self.config, initial={'ref': b'other'})
        self.assertFalse(self.verify(1, config=changed)['green'])

    def test_raw_chain_corruption_rejected(self):
        self.episode(FakeClient([]), 0).run()
        db = sqlite3.connect(self.path)
        db.execute("UPDATE events SET digest='forged' WHERE seq=1")
        db.commit()
        db.close()
        self.assertIn('chain', self.verify(0)['errors'])


if __name__ == '__main__':
    unittest.main()
