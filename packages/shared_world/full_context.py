"""Sufficient-action-context neural *baseline*, not an invented world ontology.

Each node receives its legacy role features plus the full observed role/context
features of both action arguments. Operation identifiers are opaque schema keys;
no effect, precondition, goal, native result, path or filesystem is consulted.
The legacy recurrent width, output heads, SGD, replay sampling and loss are kept.

This repairs an information pathway, not a measured capability. It still uses the
supplied fixed Frame vocabulary and copies the supplied parent view in forecasts.
Reindexing all nodes, relations, action references and histories together is
permutation-equivariant (up to floating-point arithmetic). Argument order remains
part of the public action signature, not an interchangeable object ordering.

Snapshots require fresh training and have a distinct format. Input checks reject
extra fields; they cannot authenticate that a caller's Frame was really observed
or temporally prior. That independent obligation belongs to the execution loop.
"""
from __future__ import annotations

import random

import numpy as np
import torch
from torch import nn

from packages.action_core.model import (
    HEADS, HISTORY, OP_DIM, ROLE_DIM, WIDTH, Forecast,
    Learner as LegacyLearner, Predictor as LegacyPredictor,
    Transition, role_features,
)
from packages.action_core.schema import bind_schema
from packages.action_core.world import Action, Frame


ARGUMENT_SLOTS = 2  # The supplied schema supports unary and binary operations.
CONTEXT_ROLE_DIM = ROLE_DIM * (1 + ARGUMENT_SLOTS)
CONTEXT_INPUT_DIM = CONTEXT_ROLE_DIM + OP_DIM
MODEL_FORMAT = 'full-action-context-v1'
_FRAME_FIELDS = {'kinds', 'sizes', 'equal', 'parent', 'handles', 'relations'}
_SNAPSHOT_FIELDS = {
    'algorithm', 'format', 'schema', 'weights', 'revision', 'updates',
    'change_balanced', 'latest_update', 'rng', 'seen', 'replay',
}


def _validate_frame(frame, *, observed=False):
    permitted = (Frame,) if observed else (Frame, Forecast)
    if type(frame) not in permitted or set(vars(frame)) != _FRAME_FIELDS:
        raise ValueError('only exact Frame/Forecast fields are supported')
    if frame.relations:
        raise ValueError('full-context v1 does not support additional relation channels')
    if (type(frame.handles) is not tuple or
            any(type(getattr(frame, key)) is not list for key in ('kinds', 'sizes', 'equal', 'parent')) or
            any(type(row) is not list for key in ('equal', 'parent') for row in getattr(frame, key)) or
            (type(frame) is Forecast and any(type(row) is not list for row in frame.kinds))):
        raise ValueError('unsupported frame containers')
    # Recheck mutable dataclass values without accepting subclass validation.
    (Frame if type(frame) is Frame else Forecast).__post_init__(frame)


def _validate_action(action, frame, schema):
    if type(action) is not Action or set(vars(action)) != {'op', 'args'}:
        raise ValueError('only exact action identifier/arguments are supported')
    schema.index(action)
    if any(handle not in frame.handles for handle in action.args):
        raise ValueError('action references an unobserved handle')


def _validate_history(history, handles, schema):
    if type(history) not in (list, tuple):
        raise ValueError('history must be an explicit sequence of prior observations')
    for row in history:
        if type(row) not in (list, tuple) or len(row) != 2:
            raise ValueError('history only accepts (observed Frame, Action) pairs')
        previous, action = row
        _validate_frame(previous, observed=True)
        if previous.handles != handles:
            raise ValueError('history and current frame must share a binding')
        _validate_action(action, previous, schema)


def _context_features(frame, action):
    """Pure feature construction after validation; order-independent node lookup."""
    roles = role_features(frame, action)
    n = len(frame.handles)
    if roles.shape != (n, ROLE_DIM):
        raise ValueError('unsupported legacy role feature width')
    chunks = [roles]
    for position in range(ARGUMENT_SLOTS):
        if position < len(action.args):
            index = frame.handles.index(action.args[position])
            chunks.append(np.broadcast_to(roles[index], (n, ROLE_DIM)))
        else:
            chunks.append(np.zeros((n, ROLE_DIM), dtype=np.float32))
    return np.concatenate(chunks, axis=1)


def full_context_role_features(frame, action, schema=None):
    """75 public features; accepts observed Frames or hypothetical Forecasts."""
    schema = bind_schema(schema)
    _validate_frame(frame)
    _validate_action(action, frame, schema)
    return _context_features(frame, action)


class FullContextPredictor(LegacyPredictor):
    def __init__(self, schema=None):
        # Do not instantiate/discard a legacy predictor or imply weight reuse.
        nn.Module.__init__(self)
        self.schema = bind_schema(schema)
        self.operation = nn.Embedding(len(self.schema.entries), OP_DIM)
        self.cell = nn.GRUCell(CONTEXT_INPUT_DIM, WIDTH)
        self.node = nn.Linear(WIDTH, 4)
        self.edge = nn.Sequential(nn.Linear(WIDTH * 3 + 1, WIDTH),
                                  nn.Tanh(), nn.Linear(WIDTH, 1))

    def inputs(self, frame, actions):
        _validate_frame(frame)
        if type(actions) not in (list, tuple) or not actions:
            raise ValueError('predictor inputs require a nonempty action sequence')
        for action in actions:
            _validate_action(action, frame, self.schema)
        contexts = torch.from_numpy(np.stack([_context_features(frame, a) for a in actions]))
        ids = torch.tensor([self.schema.index(a) for a in actions], dtype=torch.long)
        operation = self.operation(ids)[:, None, :].expand(-1, len(frame.handles), -1)
        return torch.cat((contexts, operation), dim=-1)

    def history(self, events, n):
        _validate_history(events, tuple(f'n{i}' for i in range(n)), self.schema)
        return super().history(events, n)

    def forward(self, inputs, hidden, equal):
        batch, n, width = inputs.shape
        if width != CONTEXT_INPUT_DIM:
            raise ValueError('incompatible full-context predictor input width')
        h = self.cell(inputs.reshape(-1, CONTEXT_INPUT_DIM),
                      hidden.expand(batch, n, WIDTH).reshape(-1, WIDTH))
        h = h.reshape(batch, n, WIDTH)
        node = self.node(h)
        left = h[:, :, None, :].expand(-1, -1, n, -1)
        right = h[:, None, :, :].expand(-1, n, -1, -1)
        pair = torch.cat((left, right, left * right, equal[..., None]), dim=-1)
        edge = self.edge(pair).squeeze(-1)
        return node[..., :3], node[..., 3].sigmoid(), (edge + edge.transpose(1, 2)) / 2


class FullContextLearner(LegacyLearner):
    """Legacy learner protocol with an explicitly incompatible predictor format."""
    def __init__(self, seed=1, updates=3, change_balanced=False, latest_update=False, schema=None):
        if type(seed) is not int or type(updates) is not int or updates < 0:
            raise ValueError('seed/updates must be integers and updates nonnegative')
        if type(change_balanced) is not bool or type(latest_update) is not bool:
            raise ValueError('learner mode flags must be booleans')
        torch.set_num_threads(1)
        torch.manual_seed(seed)
        self.rng = random.Random(seed)
        self.schema = bind_schema(schema)
        self.members = nn.ModuleList([FullContextPredictor(self.schema) for _ in range(HEADS)])
        self.optimizers = [torch.optim.SGD(m.parameters(), lr=0.04) for m in self.members]
        self.replay = []
        self.revision = 0
        self.updates = updates
        self.change_balanced = change_balanced
        self.latest_update = latest_update
        self.seen = set()

    def predict(self, frame, actions, history=()):
        _validate_frame(frame)
        if type(actions) not in (list, tuple):
            raise ValueError('actions must be an explicit sequence')
        for action in actions:
            _validate_action(action, frame, self.schema)
        _validate_history(history, frame.handles, self.schema)
        return super().predict(frame, actions, history)

    def learn(self, event_id, before, action, after, history):
        if type(event_id) is not str or not event_id:
            raise ValueError('event identifier must be a nonempty string')
        _validate_frame(before, observed=True)
        _validate_frame(after, observed=True)
        _validate_action(action, before, self.schema)
        _validate_history(history, before.handles, self.schema)
        if before.handles != after.handles:
            raise ValueError('observation identity changed within transition')
        return super().learn(event_id, before, action, after, history)

    def snapshot(self):
        value = super().snapshot()
        value['format'] = MODEL_FORMAT
        return value

    @classmethod
    def restore(cls, value):
        """Restore only this exact architecture; no filesystem or legacy migration."""
        if (type(value) is not dict or set(value) != _SNAPSHOT_FIELDS or
                value['format'] != MODEL_FORMAT or value['algorithm'] != 'neural'):
            raise ValueError('incompatible full-context checkpoint fields/format')
        if (type(value['revision']) is not int or value['revision'] < 0 or
                type(value['seen']) is not list or
                any(type(x) is not str or not x for x in value['seen']) or
                len(value['seen']) != len(set(value['seen'])) or
                value['revision'] != len(value['seen']) or
                type(value['replay']) is not list or
                len(value['replay']) != min(value['revision'], 512)):
            raise ValueError('invalid checkpoint event/replay counts')
        result = cls(updates=value['updates'], change_balanced=value['change_balanced'],
                     latest_update=value['latest_update'], schema=value['schema'])
        expected = result.members.state_dict()
        if type(value['weights']) is not dict or set(value['weights']) != set(expected):
            raise ValueError('incompatible checkpoint parameter names')
        tensors = {}
        for name, template in expected.items():
            try:
                tensor = torch.tensor(value['weights'][name], dtype=template.dtype)
            except (TypeError, ValueError, RuntimeError) as error:
                raise ValueError('invalid checkpoint parameter values') from error
            if tensor.shape != template.shape or not bool(torch.isfinite(tensor).all()):
                raise ValueError('incompatible checkpoint parameter shape/value')
            tensors[name] = tensor

        def tuples(item):
            return tuple(tuples(x) for x in item) if isinstance(item, list) else item

        try:
            result.rng.setstate(tuples(value['rng']))
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError('invalid checkpoint random state') from error
        for row in value['replay']:
            if type(row) is not dict or set(row) != {'before', 'action', 'after', 'history'}:
                raise ValueError('invalid checkpoint replay fields')
            if (type(row['history']) is not list or len(row['history']) > HISTORY or
                    any(type(h) is not list or len(h) != 2 for h in row['history'])):
                raise ValueError('invalid checkpoint history structure')
            before = Frame.from_dict(row['before'])
            action = Action.from_dict(row['action'])
            after = Frame.from_dict(row['after'])
            history = [(Frame.from_dict(f), Action.from_dict(a)) for f, a in row['history']]
            if before.handles != after.handles:
                raise ValueError('checkpoint observation binding changed')
            _validate_action(action, before, result.schema)
            _validate_history(history, before.handles, result.schema)
            result.replay.append(Transition(before, action, after, history))
        result.members.load_state_dict(tensors)
        result.revision = value['revision']
        result.seen = set(value['seen'])
        return result


# Familiar imports while keeping descriptive class names available to callers.
Predictor = FullContextPredictor
Learner = FullContextLearner
