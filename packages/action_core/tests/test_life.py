"""Supervisor/continuity unit tests; scripted client is not a capability learner."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from packages.action_core.life import Life
from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Sandbox


class ScriptedClient:
    def __init__(self):
        self.state = {'revision': 0, 'updates': 1, 'weights': {'value': 0}, 'replay': [], 'seen': []}
        self.calls = 0
        self.forge = False

    def snapshot(self):
        return copy.deepcopy(self.state)

    def restore(self, snapshot):
        self.state = copy.deepcopy(snapshot)

    def choose(self, frame, goal, actions, history):
        self.calls += 1
        # Unit-test controller only: production Life never contains action effects.
        action = Action('mkdir', ('n1',)) if frame.kinds[1] == 0 else Action('copy', ('n0', 'n2'))
        n = len(frame.handles)
        predicted = Forecast([[0., 1., 0.] for _ in range(n)], [0.] * n,
                             [[1.] * n for _ in range(n)], frame.parent, frame.handles)
        if self.forge:
            old = predicted.to_dict
            predicted.to_dict = lambda: dict(old(), verified=True, success=True)
        return action, predicted, 1

    def learn(self, event_id, before, action, after, history):
        if event_id in self.state['seen']:
            return False
        self.state['seen'].append(event_id)
        self.state['replay'].append(event_id)
        self.state['revision'] += 1
        self.state['weights']['value'] += self.state['updates']
        return True


class LifeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atanor_life_test_')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.client = ScriptedClient()
        self.base = self.client.snapshot()
        self.agenda = [{'config': {'paths': ['reference', 'folder', 'folder/out'],
                                  'initial': {'reference': f'bytes-{i}'.encode()}, 'protected': {'n0'}},
                        'goal': Goal(f'g{i}', (('n2', 1),), (('n0', 'n2'),)), 'budget': 4}
                       for i in range(2)]

    def life(self, client=None, *, mode='carry', budget=8, suffix='main', agenda=None):
        life = Life(self.folder / ('artifacts-' + suffix), self.folder / ('bodies-' + suffix),
                    self.agenda if agenda is None else agenda, client or self.client,
                    initial_checkpoint=self.base, overall_budget=budget, mode=mode)
        self.addCleanup(life.close)
        return life

    def test_two_episodes_carry_native_lineage_weights_replay_and_unique_ids(self):
        life = self.life()
        result = life.run()
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(result['steps_used'], 4)
        self.assertEqual([r['steps'] for r in result['episodes']], [2, 2])
        self.assertTrue(all(r['stop']['completed'] for r in result['episodes']))
        final = life.checkpoint()
        self.assertEqual(final['weights']['value'], 4)
        self.assertEqual(len(set(final['seen'])), 4)
        self.assertEqual(len({event.split(':')[0] for event in final['seen']}), 2)
        self.assertTrue(all(Path(r['db_path']).is_file() for r in result['episodes']))

    def test_mode_controls_distinguish_carry_reset_and_frozen(self):
        for mode, expected_weight, expected_revision in [('carry', 4, 4), ('reset', 2, 2), ('frozen', 0, 4)]:
            with self.subTest(mode=mode):
                life = self.life(ScriptedClient(), mode=mode, suffix=mode)
                self.assertEqual(life.run()['status'], 'COMPLETE')
                checkpoint = life.checkpoint()
                self.assertEqual(checkpoint['weights']['value'], expected_weight)
                self.assertEqual(checkpoint['revision'], expected_revision)

    def test_mid_episode_new_client_reopens_existing_body(self):
        life = self.life()
        self.assertEqual(life.step()['steps_used'], 1)
        life.close()
        replacement_client = ScriptedClient()
        resumed = self.life(replacement_client)
        boundary = resumed.run(max_episodes=1)
        self.assertEqual(boundary['status'], 'PAUSED')
        self.assertEqual(boundary['steps_used'], 2)
        self.assertEqual(replacement_client.calls, 1)
        self.assertEqual(resumed.checkpoint()['revision'], 2)
        resumed.close()
        resumed_again = self.life(ScriptedClient())
        self.assertEqual(resumed_again.run()['status'], 'COMPLETE')
        self.assertEqual(resumed_again.checkpoint()['weights']['value'], 4)

    def test_stop_committed_before_life_phase_crash_does_not_replay_action(self):
        life = self.life()
        life.step()
        life.step()
        with patch('packages.action_core.life.verify_episode', side_effect=KeyboardInterrupt('after native STOP')):
            with self.assertRaises(KeyboardInterrupt):
                life.step()
        self.assertEqual(life._active.state['stop']['reason'], 'goal_reached')
        self.assertEqual(life.db.execute('SELECT phase FROM episodes WHERE idx=0').fetchone()[0], 'active')
        life.close()
        replacement = ScriptedClient()
        resumed = self.life(replacement)
        boundary = resumed.run(max_episodes=1)
        self.assertEqual(boundary['status'], 'PAUSED')
        self.assertEqual(boundary['steps_used'], 2)
        self.assertEqual(replacement.calls, 0)
        self.assertEqual(resumed.checkpoint()['weights']['value'], 2)
        final = resumed.run()
        self.assertEqual(final['status'], 'COMPLETE')
        self.assertEqual(final['steps_used'], 4)
        self.assertEqual(replacement.calls, 2)
        self.assertEqual(resumed.checkpoint()['weights']['value'], 4)

    def test_global_budget_comes_from_dispatches_and_survives_restart(self):
        life = self.life(budget=3)
        result = life.run(max_episodes=1)
        self.assertEqual(result['steps_used'], 2)
        life.close()
        resumed = self.life(ScriptedClient(), budget=3)
        result = resumed.run()
        self.assertEqual(result['steps_used'], 3)
        self.assertEqual(result['remaining_budget'], 0)
        self.assertFalse(result['episodes'][1]['stop']['completed'])
        self.assertEqual(result['episodes'][1]['stop']['reason'], 'step_budget_exceeded')
        resumed.close()
        with self.assertRaises(ValueError):
            self.life(ScriptedClient(), budget=4)

    def test_pending_native_mutation_is_not_repeated_after_restart(self):
        life = self.life()
        native_step = Sandbox.step
        def crash(body, action):
            native_step(body, action)
            raise KeyboardInterrupt('crash after native mutation before receipt')
        with patch.object(Sandbox, 'step', crash), self.assertRaises(KeyboardInterrupt):
            life.step()
        life.close()
        client = ScriptedClient()
        resumed = self.life(client)
        result = resumed.run()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['steps_used'], 1)
        self.assertEqual(client.calls, 0)
        with self.assertRaises(ValueError):
            resumed.checkpoint()

    def test_ambiguous_creation_never_reinitializes_existing_body(self):
        life = self.life()
        original = Sandbox.__init__
        def crash(body, *args, **kwargs):
            original(body, *args, **kwargs)
            raise KeyboardInterrupt('crash between body creation and episode BEGIN')
        with patch.object(Sandbox, '__init__', crash), self.assertRaises(KeyboardInterrupt):
            life.step()
        body_file = self.folder / 'bodies-main/episode-0000/reference'
        self.assertEqual(body_file.read_bytes(), b'bytes-0')
        life.close()
        result = self.life(ScriptedClient()).run()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(body_file.read_bytes(), b'bytes-0')

    def test_caller_authority_and_life_side_done_flag_cannot_certify_success(self):
        self.client.forge = True
        life = self.life()
        self.assertEqual(life.run()['status'], 'BLOCKED')
        life.close()
        other = self.life(ScriptedClient(), suffix='metadata')
        other.step()
        other.close()
        db = sqlite3.connect(self.folder / 'artifacts-metadata/life.sqlite')
        db.execute("UPDATE episodes SET phase='done' WHERE idx=0")
        db.commit()
        db.close()
        result = self.life(ScriptedClient(), suffix='metadata').run()
        self.assertEqual(result['status'], 'BLOCKED')

    def test_tampered_episode_step_counter_does_not_reset_overall_budget(self):
        life = self.life()
        life.step()
        life.close()
        db = sqlite3.connect(self.folder / 'artifacts-main/episode-0000.sqlite')
        state = json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        state['steps'] = 0
        db.execute('UPDATE state SET payload=? WHERE id=1', (json.dumps(state),))
        db.commit()
        db.close()
        client = ScriptedClient()
        self.assertEqual(self.life(client).run()['status'], 'BLOCKED')
        self.assertEqual(client.calls, 0)

    def test_external_manifest_changes_and_concurrent_runner_rejected(self):
        life = self.life()
        with self.assertRaises(ValueError):
            self.life(ScriptedClient())
        life.close()
        changed = copy.deepcopy(self.agenda)
        changed[0]['config']['initial']['reference'] = b'changed'
        with self.assertRaises(ValueError):
            self.life(ScriptedClient(), agenda=changed)


if __name__ == '__main__':
    unittest.main()
