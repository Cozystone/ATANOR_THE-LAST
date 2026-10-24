"""Same-observation nearest-neighbour predictor for DEV comparison.

No filesystem success rules, tool-name dispatch or task-specific solution programs.
Uses role/reference features and the same three-event history as the neural arm.
Nearest nodes/pairs are retrieved, not a whole-world ID lookup. Search cost counts.
"""
from __future__ import annotations

import copy
import numpy as np

from .model import ROLE_DIM, HISTORY, Forecast, features
from .schema import bind_schema
from .world import Frame, Action


def context(frame, action, history, schema=None):
    schema = bind_schema(schema)
    n = len(frame.handles)
    past = [features(f, a, schema) for f, a in history[-HISTORY:]]
    past = [np.zeros((n, ROLE_DIM + len(schema.entries)), np.float32)] * (HISTORY - len(past)) + past
    return np.concatenate(past + [features(frame, action, schema)], axis=1)


def pair_features(x, equal):
    n = len(x)
    left = np.broadcast_to(x[:, None], (n, n, x.shape[1]))
    right = np.broadcast_to(x[None, :], left.shape)
    return np.concatenate((left, right, np.asarray(equal, np.float32)[..., None]), axis=-1).reshape(n*n, -1)


def nearest(query, keys):
    outputs = []
    norm = (keys * keys).sum(axis=1)
    for start in range(0, len(query), 64):
        q = query[start:start+64]
        distances = (q*q).sum(axis=1)[:, None] + norm[None] - 2 * q @ keys.T
        outputs.append(distances.argmin(axis=1))
    return np.concatenate(outputs)


class Retrieval:
    def __init__(self, schema=None):
        self.schema = bind_schema(schema)
        self.rows, self.seen, self.revision = [], set(), 0
        self.cache = None

    def learn(self, event_id, before, action, after, history):
        if type(before) is not Frame or type(after) is not Frame or any(type(f) is not Frame for f, _ in history):
            raise ValueError('retrieval learns observations, not forecasts')
        self.schema.index(action)
        for _, previous_action in history:
            self.schema.index(previous_action)
        if event_id in self.seen:
            return False
        self.rows.append(copy.deepcopy((before, action, after, history[-HISTORY:])))
        self.rows = self.rows[-512:]
        self.seen.add(event_id)
        self.revision += 1
        self.cache = None
        return True

    def snapshot(self):
        return {'algorithm': 'retrieval', 'schema': self.schema.to_data(),
                'revision': self.revision, 'seen': sorted(self.seen),
                'rows': [{'before': b.to_dict(), 'action': a.to_dict(), 'after': f.to_dict(),
                          'history': [[x.to_dict(), y.to_dict()] for x, y in h]}
                         for b, a, f, h in self.rows]}

    @classmethod
    def restore(cls, value):
        result = cls(schema=value['schema'])
        result.revision = value['revision']
        result.seen = set(value['seen'])
        result.rows = [(Frame.from_dict(r['before']), Action.from_dict(r['action']), Frame.from_dict(r['after']),
                        [(Frame.from_dict(f), Action.from_dict(a)) for f, a in r['history']]) for r in value['rows']]
        for _, action, _, history in result.rows:
            result.schema.index(action)
            for _, previous_action in history:
                result.schema.index(previous_action)
        return result

    def _compile(self):
        node_x, node_y, pair_x, pair_y = [], [], [], []
        for before, action, after, history in self.rows:
            x = context(before, action, history, self.schema)
            node_x.append(x)
            node_y.append(np.concatenate((np.eye(3)[after.kinds], np.asarray(after.sizes)[:, None]), axis=1))
            pair_x.append(pair_features(x, before.equal))
            pair_y.append(np.asarray(after.equal).reshape(-1))
        self.cache = tuple(np.concatenate(v).astype(np.float32) for v in (node_x, node_y, pair_x, pair_y))

    def predict(self, frame, actions, history=()):
        if not actions:
            return []
        if not self.rows:
            raise ValueError('retrieval needs experience')
        if self.cache is None:
            self._compile()
        nx, ny, px, py = self.cache
        n = len(frame.handles)
        xs = [context(frame, a, history, self.schema) for a in actions]
        node = ny[nearest(np.concatenate(xs), nx)].reshape(len(actions), n, 4)
        pair = py[nearest(np.concatenate([pair_features(x, frame.equal) for x in xs]), px)]
        pair = pair.reshape(len(actions), n, n)
        pair = (pair + pair.transpose(0, 2, 1)) / 2
        return [(Forecast(node[i, :, :3].tolist(), node[i, :, 3].tolist(), pair[i].tolist(),
                          copy.deepcopy(frame.parent), frame.handles), 0.) for i in range(len(actions))]
