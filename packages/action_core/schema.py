"""Public operation identifiers and arities, not preconditions or effect rules.

Names are opaque lookup keys to the learner. The native body alone dispatches
them. This is schema-bound learning in one body, not vocabulary discovery.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationSchema:
    entries: tuple[tuple[str, int], ...]

    def __post_init__(self):
        if (type(self.entries) is not tuple or not self.entries or
                any(type(row) is not tuple or len(row) != 2 or
                    type(row[0]) is not str or not row[0] or len(row[0]) > 64 or
                    any(not (c.isascii() and (c.isalnum() or c == '_')) for c in row[0]) or
                    type(row[1]) is not int or row[1] not in (1, 2) for row in self.entries) or
                len({row[0] for row in self.entries}) != len(self.entries)):
            raise ValueError('invalid operation identifier/arity schema')

    def to_data(self):
        return [{'id': name, 'arity': arity} for name, arity in self.entries]

    @classmethod
    def from_data(cls, value):
        if type(value) is not list or any(type(row) is not dict or set(row) != {'id', 'arity'} for row in value):
            raise ValueError('schema only accepts identifier and arity')
        return cls(tuple((row['id'], row['arity']) for row in value))

    def index(self, action):
        if type(action.op) is not str or type(action.args) is not tuple or any(type(h) is not str for h in action.args):
            raise ValueError('invalid action value')
        for i, (name, arity) in enumerate(self.entries):
            if name == action.op:
                if len(action.args) != arity:
                    raise ValueError('action arity mismatch')
                return i
        raise ValueError('unknown action in bound schema')


BASE_SCHEMA = OperationSchema((('mkdir', 1), ('empty', 1), ('copy', 2), ('unlink', 1)))
TRANSFER_SCHEMA = OperationSchema(BASE_SCHEMA.entries + (('rename', 2),))


def bind_schema(value=None):
    if value is None:
        return BASE_SCHEMA
    if type(value) is OperationSchema:
        return value
    return OperationSchema.from_data(value)
