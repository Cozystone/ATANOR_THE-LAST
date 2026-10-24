"""Random-initialized, shared recurrent action predictor.

No language model, pretrained weights, filesystem access or action effect rules.
Object/reference features are observations; predicted outcomes are hypotheses.
The fixed generic feature bias is disclosed, not autonomous representation discovery.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field
from .relations import validate_relations

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .world import Action, Frame
from .schema import BASE_SCHEMA, bind_schema

OPS = tuple(name for name, _ in BASE_SCHEMA.entries)  # legacy DEV imports only
HISTORY = 3
WIDTH = 24
HEADS = 3


@dataclass
class Forecast:
    """Model hypothesis. Deliberately NOT an observed Frame or evidence receipt."""
    kinds: list
    sizes: list
    equal: list
    parent: list
    handles: tuple
    relations: dict = field(default_factory=dict)

    def __post_init__(self):
        n = len(self.handles)
        validate_relations(self.relations, n, predicted=True)
        if not n or self.handles != tuple(f'n{i}' for i in range(n)):
            raise ValueError('invalid forecast vocabulary')
        if len(self.kinds) != n or any(len(r) != 3 for r in self.kinds):
            raise ValueError('invalid kind distribution shape')
        if len(self.sizes) != n or any(len(m) != n or any(len(r) != n for r in m)
                                      for m in (self.equal, self.parent)):
            raise ValueError('invalid forecast dimensions')
        values = self.sizes + [x for m in (self.kinds, self.equal, self.parent) for r in m for x in r]
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in values):
            raise ValueError('invalid forecast probability')
        if any(abs(sum(r) - 1) > 1e-5 for r in self.kinds):
            raise ValueError('kind probabilities must sum to one')

    def to_dict(self):
        result = {'type': 'forecast', 'kinds': self.kinds, 'sizes': self.sizes,
                'equal': self.equal, 'parent': self.parent, 'handles': list(self.handles)}
        if self.relations:
            result.update(view_version=2, relations=copy.deepcopy(self.relations))
        return result

    @classmethod
    def from_dict(cls, obj):
        legacy = {'type', 'kinds', 'sizes', 'equal', 'parent', 'handles'}
        if (type(obj) is not dict or set(obj) not in (legacy, legacy | {'view_version', 'relations'}) or
                obj['type'] != 'forecast' or ('view_version' in obj and
                (obj['view_version'] != 2 or not obj['relations']))):
            raise ValueError('invalid forecast fields')
        return cls(obj['kinds'], obj['sizes'], obj['equal'], obj['parent'], tuple(obj['handles']),
                   obj.get('relations', {}))


def role_features(frame: Frame, action: Action) -> np.ndarray:
    """Shared role/reference features; no operator-specific semantics."""
    if frame.relations:
        raise ValueError('legacy feature encoder cannot silently discard relation channels')
    kinds = np.asarray(frame.kinds, dtype=np.float32)
    if kinds.ndim == 1:
        kinds = np.eye(3, dtype=np.float32)[kinds.astype(int)]
    n = len(kinds)
    size = np.asarray(frame.sizes, dtype=np.float32).reshape(n, 1)
    eq = np.asarray(frame.equal, dtype=np.float32)
    parent = np.asarray(frame.parent, dtype=np.float32)
    chunks = [kinds, size, parent @ kinds, parent.T @ kinds, eq.mean(axis=1, keepdims=True)]
    for pos in range(2):
        role = np.zeros((n, 1), np.float32)
        if pos < len(action.args):
            idx = list(frame.handles).index(action.args[pos])
            role[idx] = 1
            chunks += [role, np.tile(kinds[idx], (n, 1)),
                       eq[:, idx:idx + 1], parent[:, idx:idx + 1],
                       parent[idx:idx + 1, :].T]
        else:
            chunks.append(np.zeros((n, 7), np.float32))
    return np.concatenate(chunks, axis=1)


def features(frame: Frame, action: Action, schema=None) -> np.ndarray:
    """Public reference features plus opaque schema one-hot for direct retrieval."""
    schema = bind_schema(schema)
    op = np.eye(len(schema.entries), dtype=np.float32)[schema.index(action)]
    return np.concatenate((role_features(frame, action),
                           np.tile(op, (len(frame.handles), 1))), axis=1)


ROLE_DIM = 25
OP_DIM = 4
DIM = 29
MODEL_FORMAT = 'schema-embedding-v1'


def balanced_loss(losses, changed):
    """Equal weight to present change/no-change strata, from observed outcomes only."""
    parts = [losses[mask].mean() for mask in (changed, ~changed) if mask.any()]
    return torch.stack(parts).mean()


class Predictor(nn.Module):
    def __init__(self, schema=None):
        super().__init__()
        self.schema = bind_schema(schema)
        # Random identifiers, not language/name embeddings or supplied effects.
        self.operation = nn.Embedding(len(self.schema.entries), OP_DIM)
        self.cell = nn.GRUCell(DIM, WIDTH)
        self.node = nn.Linear(WIDTH, 4)
        self.edge = nn.Sequential(nn.Linear(WIDTH * 3 + 1, WIDTH),
                                  nn.Tanh(), nn.Linear(WIDTH, 1))

    def inputs(self, frame, actions):
        roles = torch.from_numpy(np.stack([role_features(frame, a) for a in actions]))
        ids = torch.tensor([self.schema.index(a) for a in actions], dtype=torch.long)
        op = self.operation(ids)[:, None, :].expand(-1, len(frame.handles), -1)
        return torch.cat((roles, op), dim=-1)

    def history(self, events, n):
        hidden = torch.zeros(n, WIDTH)
        for frame, action in events[-HISTORY:]:
            hidden = self.cell(self.inputs(frame, [action])[0], hidden)
        return hidden

    def forward(self, inputs, hidden, equal):
        batch, n, _ = inputs.shape
        h = self.cell(inputs.reshape(-1, DIM),
                      hidden.expand(batch, n, WIDTH).reshape(-1, WIDTH))
        h = h.reshape(batch, n, WIDTH)
        node = self.node(h)
        left = h[:, :, None, :].expand(-1, -1, n, -1)
        right = h[:, None, :, :].expand(-1, n, -1, -1)
        pair = torch.cat((left, right, left * right, equal[..., None]), dim=-1)
        edge = self.edge(pair).squeeze(-1)
        return node[..., :3], node[..., 3].sigmoid(), (edge + edge.transpose(1, 2)) / 2


@dataclass
class Transition:
    before: Frame
    action: Action
    after: Frame
    history: list


class Learner:
    """Bounded development learner; replay limit is not a lifetime-memory claim."""
    def __init__(self, seed=1, updates=3, change_balanced=False, latest_update=False, schema=None):
        torch.set_num_threads(1)
        torch.manual_seed(seed)
        self.rng = random.Random(seed)
        self.schema = bind_schema(schema)
        self.members = nn.ModuleList([Predictor(self.schema) for _ in range(HEADS)])
        self.optimizers = [torch.optim.SGD(m.parameters(), lr=0.04) for m in self.members]
        self.replay = []
        self.revision = 0
        self.updates = updates
        self.change_balanced = change_balanced
        self.latest_update = latest_update
        self.seen = set()

    def learn(self, event_id, before, action, after, history):
        if type(before) is not Frame or type(after) is not Frame or any(type(f) is not Frame for f, _ in history):
            raise ValueError('learning requires actual observations, not forecasts')
        self.schema.index(action)
        for _, previous_action in history:
            self.schema.index(previous_action)
        if event_id in self.seen:
            return False
        if before.handles != after.handles:
            raise ValueError("observation identity changed within transition")
        self.seen.add(event_id)
        self.replay.append(Transition(copy.deepcopy(before), action, copy.deepcopy(after),
                                      copy.deepcopy(history[-HISTORY:])))
        self.replay = self.replay[-512:]
        self.revision += 1
        changed_records = [t for t in self.replay if t.before != t.after] if self.change_balanced else []
        for model, optimizer in zip(self.members, self.optimizers):
            for update_index in range(self.updates):
                item = self._sample_update(update_index, changed_records)
                n = len(item.before.handles)
                hidden = model.history(item.history, n)
                x = model.inputs(item.before, [item.action])
                eq = torch.tensor(item.before.equal, dtype=torch.float32)[None]
                k, sz, e = model(x, hidden, eq)
                target_k = torch.tensor(item.after.kinds, dtype=torch.long)
                target_s = torch.tensor(item.after.sizes, dtype=torch.float32)
                target_e = torch.tensor(item.after.equal, dtype=torch.float32)[None]
                kl = F.cross_entropy(k[0], target_k, reduction='none')
                sl = F.mse_loss(sz[0], target_s, reduction='none')
                el = F.binary_cross_entropy_with_logits(e, target_e, reduction='none')
                if self.change_balanced:
                    loss = balanced_loss(kl, target_k != torch.tensor(item.before.kinds))
                    loss += balanced_loss(sl, target_s != torch.tensor(item.before.sizes))
                    loss += balanced_loss(el, target_e != eq)
                else:
                    loss = kl.mean() + sl.mean() + el.mean()
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
        return True

    def _sample_update(self, update_index, changed_records):
        # Budget unchanged: reserve one existing slot per head for new experience.
        # Saving an event is not equivalent to having updated on it.
        if self.latest_update and update_index == 0:
            return self.replay[-1]
        pool = changed_records if changed_records and self.rng.random() < .5 else self.replay
        return self.rng.choice(pool)

    def predict(self, frame, actions, history=()):
        if not actions:
            return []
        eq = torch.tensor(frame.equal, dtype=torch.float32)[None].expand(len(actions), -1, -1)
        predictions = []
        with torch.no_grad():
            for model in self.members:
                hidden = model.history(history, len(frame.handles))
                x = model.inputs(frame, actions)
                k, sz, e = model(x, hidden, eq)
                predictions.append((k.softmax(-1), sz, e.sigmoid()))
            kinds = torch.stack([p[0] for p in predictions])
            sizes = torch.stack([p[1] for p in predictions])
            edges = torch.stack([p[2] for p in predictions])
            uncertainty = kinds.var(0, unbiased=False).mean((1, 2))
            uncertainty += edges.var(0, unbiased=False).mean((1, 2))
            mk, ms, me = kinds.mean(0), sizes.mean(0), edges.mean(0)
            return [(Forecast(kinds=mk[i].tolist(), sizes=ms[i].tolist(),
                           equal=me[i].tolist(), parent=copy.deepcopy(frame.parent),
                           handles=tuple(frame.handles)), float(uncertainty[i]))
                    for i in range(len(actions))]

    def snapshot(self):
        def encode_history(history):
            return [[f.to_dict(), {"op": a.op, "args": list(a.args)}] for f, a in history]
        return {"algorithm": "neural", "format": MODEL_FORMAT, "schema": self.schema.to_data(),
                "weights": {k: v.tolist() for k, v in self.members.state_dict().items()},
                "revision": self.revision, "updates": self.updates, "change_balanced": self.change_balanced,
                "latest_update": self.latest_update,
                "rng": self.rng.getstate(), "seen": sorted(self.seen),
                "replay": [{"before": t.before.to_dict(), "action": {"op": t.action.op, "args": list(t.action.args)},
                            "after": t.after.to_dict(), "history": encode_history(t.history)}
                           for t in self.replay]}

    @classmethod
    def restore(cls, value):
        def tuples(x):
            return tuple(tuples(v) for v in x) if isinstance(x, list) else x
        if value.get('format') != MODEL_FORMAT:
            raise ValueError('incompatible checkpoint: explicit schema-embedding retraining required')
        m = cls(updates=value["updates"], change_balanced=value.get('change_balanced', False),
                latest_update=value.get('latest_update', False), schema=value['schema'])
        m.members.load_state_dict({k: torch.tensor(v) for k, v in value["weights"].items()})
        m.revision = value["revision"]
        m.rng.setstate(tuples(value["rng"]))
        m.seen = set(value["seen"])
        for row in value["replay"]:
            m.replay.append(Transition(Frame.from_dict(row["before"]),
                Action.from_dict(row["action"]),
                Frame.from_dict(row["after"]),
                [(Frame.from_dict(f), Action.from_dict(a))
                 for f, a in row["history"]]))
        for item in m.replay:
            m.schema.index(item.action)
            for _, action in item.history:
                m.schema.index(action)
        return m
