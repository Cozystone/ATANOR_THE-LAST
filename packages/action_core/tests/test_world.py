import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from packages.action_core.world import Action, Frame, Sandbox


class BodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='atanor_action_body_')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def body(self, **kw):
        return Sandbox(self.base / 'owned', **kw)

    def test_real_copy_requires_parent_and_observation_comes_from_disk(self):
        body = self.body(paths=['reference', 'folder', 'folder/item'],
                         initial={'reference': b'actual bytes'}, protected={'n0'})
        actions = body.actions()
        self.assertIn(Action('copy', ('n0', 'n2')), actions)
        self.assertFalse(body.step(Action('copy', ('n0', 'n2'))))
        self.assertTrue(body.step(Action('mkdir', ('n1',))))
        self.assertTrue(body.step(Action('copy', ('n0', 'n2'))))
        self.assertEqual(actions, body.actions())
        frame = body.observe()
        self.assertEqual(frame.kinds, [1, 2, 1])
        self.assertEqual(frame.equal[0][2], 1.)
        self.assertEqual(frame.parent[1][2], 1.)
        evidence = body.evidence()
        self.assertEqual(evidence['n0']['sha256'], evidence['n2']['sha256'])
        self.assertEqual(evidence['n2']['size_bytes'], len(b'actual bytes'))
        (body.root / 'folder/item').write_bytes(b'different')
        self.assertEqual(body.observe().equal[0][2], 0.)
        self.assertNotEqual(body.evidence()['n2']['sha256'], evidence['n2']['sha256'])
        self.assertEqual(Frame.from_dict(frame.to_dict()).to_dict(), frame.to_dict())
        self.assertEqual(Action.from_dict(actions[0].to_dict()), actions[0])

    def test_variable_node_counts_and_all_state_independent_actions(self):
        for n in (1, 4):
            body = Sandbox(self.base / f'body{n}', [f'f{i}' for i in range(n)], {})
            self.assertEqual(len(body.actions()), 3*n + n*(n-1))
            self.assertEqual(len(body.observe().equal), n)
            before = body.actions()
            self.assertTrue(body.step(Action('empty', ('n0',))))
            self.assertEqual(before, body.actions())
            self.assertTrue(body.step(Action('unlink', ('n0',))))

    def test_invalid_metadata_protection_and_traversal_never_mutate(self):
        for path in ('../escape', '/absolute', 'a/../b', 'C:escape', 'a\\b', 'NUL'):
            with self.assertRaises(ValueError):
                self.body(paths=[path], initial={})
            self.assertFalse((self.base / 'owned').exists())
        with self.assertRaises(ValueError):
            self.body(paths=['x'], initial={'x': 'not bytes'})
        body = self.body(paths=['ref', 'x'], initial={'ref': b'keep'}, protected={'n0'})
        for action in (Action('empty', ('n0',)), Action('copy', ('n1', 'n0')),
                       Action('empty', ('../escape',)), Action('fake', ('n1',)),
                       Action('empty', ['n1'])):
            with self.assertRaises(ValueError):
                body.step(action)
        self.assertEqual((body.root / 'ref').read_bytes(), b'keep')
        self.assertFalse((body.root / 'x').exists())
        malformed = body.observe().to_dict()
        malformed['sizes'][0] = float('nan')
        with self.assertRaises(ValueError):
            Frame.from_dict(malformed)
        with self.assertRaises(ValueError):
            Action.from_dict({'op': 'empty', 'args': ['n1'], 'verified': True})

    def test_reparse_metadata_denied_before_mutation(self):
        body = self.body(paths=['x'], initial={'x': b'keep'})
        original = Path.lstat
        target = body.root / 'x'
        def injected(path):
            if path == target:
                return SimpleNamespace(st_mode=0, st_file_attributes=1024)
            return original(path)
        with patch.object(Path, 'lstat', injected):
            with self.assertRaises(ValueError):
                body.step(Action('empty', ('n0',)))
        self.assertEqual(target.read_bytes(), b'keep')

    def test_existing_root_is_not_owned_or_modified(self):
        with self.assertRaises(ValueError):
            Sandbox(self.base, ['x'], {})

    def test_symlink_escape_rejected_before_mutation(self):
        body = self.body(paths=['link', 'link/victim'], initial={})
        outside = self.base / 'outside'
        outside.mkdir()
        victim = outside / 'victim'
        victim.write_bytes(b'keep')
        try:
            os.symlink(outside, body.root / 'link', target_is_directory=True)
        except OSError as exc:
            self.skipTest(f'host cannot create symlinks: {exc}')
        with self.assertRaises(ValueError):
            body.step(Action('empty', ('n1',)))
        with self.assertRaises(ValueError):
            body.observe()
        self.assertEqual(victim.read_bytes(), b'keep')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_real_windows_junction_escape_rejected(self):
        body = self.body(paths=['link', 'link/victim'], initial={})
        outside = self.base / 'outside'
        outside.mkdir()
        victim = outside / 'victim'
        victim.write_bytes(b'keep')
        link = body.root / 'link'
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                              capture_output=True, check=False)
        if made.returncode:
            self.skipTest('host cannot create junctions')
        try:
            with self.assertRaises(ValueError):
                body.step(Action('empty', ('n1',)))
            with self.assertRaises(ValueError):
                body.evidence()
            self.assertEqual(victim.read_bytes(), b'keep')
        finally:
            os.rmdir(link)  # Remove only this test-owned junction, never its target.


if __name__ == '__main__':
    unittest.main()
