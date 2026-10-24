import json
import unittest

from packages.action_core.schema import BASE_SCHEMA, TRANSFER_SCHEMA, OperationSchema
from packages.action_core.world import Action


class SchemaTests(unittest.TestCase):
    def test_roundtrip_only_identifier_and_arity(self):
        value = json.loads(json.dumps(TRANSFER_SCHEMA.to_data()))
        self.assertEqual(OperationSchema.from_data(value), TRANSFER_SCHEMA)
        self.assertEqual(TRANSFER_SCHEMA.index(Action('rename', ('n0', 'n1'))), 4)
        with self.assertRaises(ValueError):
            OperationSchema.from_data([{'id': 'rename', 'arity': 2, 'effect': 'source_absent'}])

    def test_unknown_or_wrong_arity_has_no_authority(self):
        # Syntax deserialization does not grant permission in a body's schema.
        unknown = Action.from_dict({'op': 'rename', 'args': ['n0', 'n1']})
        with self.assertRaises(ValueError):
            BASE_SCHEMA.index(unknown)
        for action in [Action('rename', ('n0',)), Action('rename', ('n0', 'n1', 'n2')),
                       Action('rename', ['n0', 'n1']), Action('other', ('n0',))]:
            with self.assertRaises(ValueError):
                TRANSFER_SCHEMA.index(action)
        for value in [[{'id': 'rename', 'arity': True}],
                      [{'id': 'rename', 'arity': 2}] * 2,
                      [{'id': '../rename', 'arity': 2}]]:
            with self.assertRaises(ValueError):
                OperationSchema.from_data(value)

