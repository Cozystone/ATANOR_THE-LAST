import copy
import json
from pathlib import Path
import tempfile
import unittest

import torch

from packages.action_core.model import Learner
from packages.action_core.retrieval import Retrieval
from packages.action_core.schema import TRANSFER_SCHEMA, OperationSchema
from packages.action_core.world import Action, Sandbox


class TransferModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='atanor-transfer-model-test-')
        self.addCleanup(self.tmp.cleanup)
        self.body = Sandbox(Path(self.tmp.name) / 'body', ['a', 'b', 'p'], {'a': b'x'},
                            operations=TRANSFER_SCHEMA.to_data())

    def test_new_operation_row_random_untrained_after_only_old_experience(self):
        model = Learner(seed=22, updates=1, schema=TRANSFER_SCHEMA)
        initial = [m.operation.weight[4].detach().clone() for m in model.members]
        before = self.body.observe()
        action = Action('copy', ('n0', 'n1'))
        self.body.step(action)
        model.learn('old-only', before, action, self.body.observe(), [])
        for old, member in zip(initial, model.members):
            self.assertTrue(torch.equal(old, member.operation.weight[4]))
        self.assertEqual(len(model.replay), 1)
        restored = Learner.restore(json.loads(json.dumps(model.snapshot())))
        self.assertEqual(model.snapshot(), restored.snapshot())
        # Shape/restore only, no new-operation accuracy or online learning result.
        action = Action('rename', ('n0', 'n1'))
        one = model.predict(before, [action])[0][0].to_dict()
        self.assertEqual(one, restored.predict(before, [action])[0][0].to_dict())

    def test_names_cannot_supply_pretrained_semantics(self):
        names = OperationSchema(tuple((f'op_{i}', arity) for i, (_, arity) in enumerate(TRANSFER_SCHEMA.entries)))
        a = Learner(seed=13, updates=1, schema=TRANSFER_SCHEMA)
        b = Learner(seed=13, updates=1, schema=names)
        frame = self.body.observe()
        x = a.predict(frame, [Action('rename', ('n0', 'n1'))])[0]
        y = b.predict(frame, [Action('op_4', ('n0', 'n1'))])[0]
        self.assertEqual(x[0].to_dict(), y[0].to_dict())
        self.assertEqual(x[1], y[1])

    def test_checkpoint_schema_forgery_and_old_format_rejected(self):
        model = Learner(seed=2, updates=1, schema=TRANSFER_SCHEMA)
        snap = model.snapshot()
        old = copy.deepcopy(snap)
        del old['format']
        with self.assertRaises(ValueError):
            Learner.restore(old)
        forged = copy.deepcopy(snap)
        forged['schema'][4]['effect'] = 'source_absent'
        with self.assertRaises(ValueError):
            Learner.restore(forged)
        before = self.body.observe()
        with self.assertRaises(ValueError):
            model.learn('forgery', before, Action('pretend', ('n0',)), before, [])
        self.assertEqual(model.revision, 0)

    def test_retrieval_uses_identical_public_schema_and_old_actual_events(self):
        model = Retrieval(TRANSFER_SCHEMA)
        before = self.body.observe()
        action = Action('copy', ('n0', 'n1'))
        self.body.step(action)
        model.learn('old-only', before, action, self.body.observe(), [])
        restored = Retrieval.restore(json.loads(json.dumps(model.snapshot())))
        self.assertEqual(restored.snapshot(), model.snapshot())
        x = model.predict(before, [Action('rename', ('n0', 'n1'))])[0][0]
        y = restored.predict(before, [Action('rename', ('n0', 'n1'))])[0][0]
        self.assertEqual(x.to_dict(), y.to_dict())

