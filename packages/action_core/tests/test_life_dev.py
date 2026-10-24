import json
from pathlib import Path
import tempfile
import unittest

from packages.action_core.life_dev import load_base, LocalClient
from packages.action_core.model import Learner


class LifeDevTests(unittest.TestCase):
    def test_legacy_dispatch_tag_only_and_exact_restore(self):
        modern = json.loads(json.dumps(Learner(seed=12).snapshot()))
        legacy = {k: v for k, v in modern.items() if k != 'algorithm'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'base.json'
            path.write_text(json.dumps(legacy), encoding='utf-8')
            original = path.read_bytes()
            restored = load_base(path)
            self.assertEqual(restored, modern)
            self.assertEqual(path.read_bytes(), original)
            client = LocalClient()
            client.restore(restored)
            self.assertEqual(json.loads(json.dumps(client.snapshot())), restored)

    def test_explicit_other_algorithm_not_silently_relabelled(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'base.json'
            path.write_text('{"algorithm":"retrieval"}', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_base(path)


if __name__ == '__main__':
    unittest.main()
