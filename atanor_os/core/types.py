"""Data contracts for P1 (charter §4). Plain records; no learning logic here."""
from __future__ import annotations

from dataclasses import asdict, dataclass

ATTRS = ('kind', 'ext', 'hash', 'parent_kind')   # per-object observables; parent_kind is derived structure
KINDS = ('absent', 'file', 'dir')


@dataclass(frozen=True)
class Literal:
    """Ground literal over concrete object ids (paths). Unobserved objects never satisfy anything."""
    pred: str      # one of ATTRS or 'same_content'
    args: tuple
    value: object

    def holds(self, state):
        if self.pred == 'same_content':
            a, b = state.get(self.args[0]), state.get(self.args[1])
            if a is None or b is None:
                return False
            return (a['hash'] != '-' and a['hash'] == b['hash']) == self.value
        o = state.get(self.args[0])
        return o is not None and o.get(self.pred) == self.value

    def to_json(self):
        return [self.pred, list(self.args), self.value]

    @staticmethod
    def from_json(j):
        return Literal(j[0], tuple(j[1]), j[2])


@dataclass
class Goal:
    id: str
    must: list        # Literals required at the end
    keep: list        # Literals required at the end and never to be violated on the way
    capabilities: dict
    budget: dict      # actions, nodes, depth, seconds
    universe: list    # paths the goal refers to; observable even when absent

    def satisfied(self, state):
        return all(l.holds(state) for l in self.must) and all(l.holds(state) for l in self.keep)

    def to_json(self):
        return {'id': self.id, 'must': [l.to_json() for l in self.must], 'keep': [l.to_json() for l in self.keep],
                'capabilities': self.capabilities, 'budget': self.budget, 'universe': self.universe}

    @staticmethod
    def from_json(j):
        return Goal(j['id'], [Literal.from_json(x) for x in j['must']], [Literal.from_json(x) for x in j['keep']],
                    dict(j['capabilities']), dict(j['budget']), list(j['universe']))


@dataclass
class Experience:
    id: str
    tool: str
    args: tuple
    pre: dict          # {path: attrs} observed before the action
    post: dict         # {path: attrs} observed after the action
    succeeded: bool
    blocked: bool = False
    cost_ms: float = 0.0
    external: bool = False
    source: str = ''

    def to_json(self):
        d = asdict(self)
        d['args'] = list(self.args)
        return d

    @staticmethod
    def from_json(j):
        j = dict(j)
        j['args'] = tuple(j['args'])
        return Experience(**j)
