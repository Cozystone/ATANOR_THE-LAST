import os
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from packages.action_core.episode import Episode, verify_episode
from packages.action_core.model import Forecast
from packages.action_core.planner import Goal
from packages.action_core.schema import TRANSFER_SCHEMA
from packages.action_core.world import Action, Sandbox


class ScriptedClient:
    """Supervisor test only: not a candidate, learner, or scored solver."""
    def __init__(self, actions):
        self.actions = iter(actions)
        self.revision = 0

    def choose(self, frame, goal, actions, history):
        pred = Forecast([[float(i == k) for i in range(3)] for k in frame.kinds],
                        frame.sizes, frame.equal, frame.parent, frame.handles)
        return next(self.actions), pred, 1

    def snapshot(self):
        return {'revision': self.revision, 'scripted_mechanism_test_only': True}

    def learn(self, *_):
        self.revision += 1
        return True


class NativeMoveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='atanor-native-move-test-')
        self.addCleanup(self.tmp.cleanup)
        self.config = {'paths': ['ref', 'src', 'p', 'p/dst'],
                       'initial': {'ref': b'actual payload', 'src': b'actual payload'},
                       'protected': {'n0'}, 'operations': TRANSFER_SCHEMA.to_data()}
        self.body = Sandbox(Path(self.tmp.name) / 'body', **self.config)

    def test_native_missing_parent_then_rename_actual_bytes_source_disappears(self):
        before = self.body.evidence()
        permissions = self.body.actions()
        self.assertFalse(self.body.step(Action('rename', ('n1', 'n3'))))
        self.assertEqual(before, self.body.evidence())
        self.assertTrue(self.body.step(Action('mkdir', ('n2',))))
        self.assertTrue(self.body.step(Action('rename', ('n1', 'n3'))))
        after = self.body.evidence()
        self.assertEqual(after['n1']['kind'], 0)
        self.assertEqual(after['n3']['sha256'], before['n1']['sha256'])
        self.assertEqual(after['n0'], before['n0'])
        self.assertEqual(permissions, self.body.actions())
        self.assertIn(Action('copy', ('n1', 'n3')), permissions)
        self.assertIn(Action('unlink', ('n1',)), permissions)
        attached = Sandbox.attach(self.body.root, self.config['paths'], {'n0'},
                                  operations=TRANSFER_SCHEMA.to_data())
        self.assertEqual(after, attached.evidence())

    def test_forged_source_or_destination_permission_rejected_before_dispatch(self):
        before = self.body.evidence()
        with patch.object(Path, 'rename', side_effect=AssertionError('must not dispatch')):
            for action in [Action('rename', ('n0', 'n1')), Action('rename', ('n1', 'n0')),
                           Action('rename', ('n1', 'outside')), Action('rename', ('n1', 'n1')),
                           Action('unknown', ('n1',)), Action('rename', ('n1',))]:
                with self.assertRaises(ValueError):
                    self.body.step(action)
        self.assertEqual(before, self.body.evidence())
        base = Sandbox(Path(self.tmp.name) / 'base', ['a', 'b'], {'a': b'x'})
        with self.assertRaises(ValueError):
            base.step(Action('rename', ('n0', 'n1')))

    def test_protected_descendant_cannot_be_moved_via_parent(self):
        config = {'paths': ['p', 'p/ref', 'dest'], 'initial': {'p': None, 'p/ref': b'keep'},
                  'protected': {'n1'}, 'operations': TRANSFER_SCHEMA.to_data()}
        body = Sandbox(Path(self.tmp.name) / 'nested', **config)
        before = body.evidence()
        self.assertNotIn(Action('rename', ('n0', 'n2')), body.actions())
        for action in [Action('rename', ('n0', 'n2')), Action('rename', ('n2', 'n0'))]:
            with self.assertRaises(ValueError):
                body.step(action)
        self.assertEqual(before, body.evidence())

    def test_unprotected_native_directory_rename_is_observed_not_predicted(self):
        body = Sandbox(Path(self.tmp.name) / 'dir', ['p', 'p/a', 'q', 'q/a'],
                       {'p': None, 'p/a': b'x'}, operations=TRANSFER_SCHEMA.to_data())
        self.assertTrue(body.step(Action('rename', ('n0', 'n2'))))
        self.assertEqual(body.observe().kinds, [0, 0, 2, 1])

    def test_symlink_source_or_destination_and_nested_link_forbidden(self):
        body = Sandbox(Path(self.tmp.name) / 'links', ['p', 'dst'], {'p': None},
                       operations=TRANSFER_SCHEMA.to_data())
        outside = Path(self.tmp.name) / 'outside'
        outside.mkdir()
        (outside / 'valuable').write_bytes(b'keep')
        link = body.root / 'p' / 'hidden_link'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('native symlink creation not permitted on host')
        try:
            with self.assertRaises(ValueError):
                body.step(Action('rename', ('n0', 'n1')))
            self.assertEqual((outside / 'valuable').read_bytes(), b'keep')
        finally:
            link.unlink()

    def test_invalid_schema_or_root_does_not_materialize(self):
        bad = Path(self.tmp.name) / 'bad'
        with self.assertRaises(ValueError):
            Sandbox(bad, ['a'], {}, operations=[{'id': 'rename', 'arity': 2, 'verified': True}])
        self.assertFalse(bad.exists())
        with self.assertRaises(ValueError):
            Sandbox(Path(tempfile.gettempdir()), ['a'], {}, operations=TRANSFER_SCHEMA.to_data())

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_real_junction_source_destination_and_unlisted_subtree_rejected(self):
        for case in ('source', 'destination', 'nested'):
            body = Sandbox(Path(self.tmp.name) / ('junction-' + case), ['src', 'dst'],
                           {'src': None} if case == 'nested' else {},
                           operations=TRANSFER_SCHEMA.to_data())
            outside = Path(self.tmp.name) / ('outside-' + case)
            outside.mkdir()
            (outside / 'valuable').write_bytes(b'keep')
            link = body.root / ('src/hidden' if case == 'nested' else 'src' if case == 'source' else 'dst')
            # Explicit new test-owned link and target; no deletion shell involved.
            made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                  capture_output=True, check=False,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if made.returncode:
                self.skipTest('host cannot create junctions')
            try:
                with self.assertRaises(ValueError):
                    body.step(Action('rename', ('n0', 'n1')))
                self.assertEqual((outside / 'valuable').read_bytes(), b'keep')
            finally:
                if not link.absolute().is_relative_to(body.root):
                    raise AssertionError('test link escaped owned body')
                os.rmdir(link)  # Link itself only, never the target or a tree.

    def test_scripted_new_operation_episode_native_replay_and_schema_binding(self):
        goal = Goal('mechanism-only', (('n1', 0), ('n3', 1)), (('n0', 'n3'),))
        client = ScriptedClient([Action('mkdir', ('n2',)), Action('rename', ('n1', 'n3'))])
        path = Path(self.tmp.name) / 'episode.sqlite'
        episode = Episode(path, self.body, goal, client, config=self.config, budget=2)
        self.assertTrue(episode.run()['completed'])
        episode.close()
        verdict = verify_episode(path, expected_config=self.config, expected_goal=goal, expected_budget=2)
        self.assertTrue(verdict['green'], verdict)
        forged_config = {k: v for k, v in self.config.items() if k != 'operations'}
        self.assertFalse(verify_episode(path, expected_config=forged_config,
                                       expected_goal=goal, expected_budget=2)['green'])
