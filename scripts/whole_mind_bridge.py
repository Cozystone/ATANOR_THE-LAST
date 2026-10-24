"""Opt-in H planner / R authoritative world bridge. No new planning algorithm.

Explicit semantic scope: independent filesystem locators, unary operations,
kind-only goals. Unsupported semantics fail closed, never approximate a task.
H receives only a read-only view and a derived memory table. Its first proposed
dispatch is intercepted; ONLY WorldSession may perform it and record reality.
"""
import copy
import json
from pathlib import Path
import numpy as np

from packages.action_core.world import Action, Frame
from packages.shared_world.contracts import ScopedPartialForecast
from packages.shared_world.historical_goal_world import DictStore, plan_agent


class Proposed(Exception):
    def __init__(self, action):
        self.action = action


class MemoryView(DictStore):
    def __init__(self):
        super().__init__()
        self.queries = []

    def get(self, key):
        value = super().get(key)
        self.queries.append([list(key), value])
        return value

    def belief_query(self, *args, **kwargs):
        # The optional H decay learner is NOT selected. No invented certainty.
        return None


class ObservationView:
    def __init__(self, frame, operations):
        if any(any(row) for row in frame.parent) or frame.relations:
            raise ValueError('bridge supports flat independent locators only')
        self.frame = frame
        self.parents = (-1,) * len(frame.handles)
        self.actions = tuple(operations)

    def config(self):
        return tuple(self.frame.kinds)

    def do(self, operation, index):
        raise Proposed(Action(operation, (self.frame.handles[index],)))


class WholeMindClient:
    def __init__(self, records, schema, arm='full', trace=None):
        if arm not in ('full', 'no_memory', 'no_planning'):
            raise ValueError('unknown ablation')
        if any(r['arity'] != 1 for r in schema):
            raise ValueError('only unary schema supported by H bridge')
        self.ops = tuple(r['id'] for r in schema)
        self.arm, self.trace = arm, trace
        self.state = dict(revision=0, records=copy.deepcopy(records), events={}, arm=arm)

    def snapshot(self):
        return copy.deepcopy(self.state)

    def restore(self, state):
        if (set(state) != {'revision', 'records', 'events', 'arm'} or
                state['arm'] != self.arm or state['revision'] != len(state['events'])):
            raise ValueError('checkpoint mismatch')
        self.state = copy.deepcopy(state)

    def memory(self):
        store = MemoryView()
        if self.arm == 'no_memory':
            return store
        for r in self.state['records']:
            a = Action.from_dict(r['action'])
            b, e = Frame.from_dict(r['before']), Frame.from_dict(r['after'])
            if a.op not in self.ops or len(a.args) != 1:
                continue
            if any(any(row) for row in b.parent) or b.relations:
                continue
            i = b.handles.index(a.args[0])
            if b.handles != e.handles or any(b.kinds[j] != e.kinds[j] for j in range(len(b.handles)) if j != i):
                continue
            # H root context DIR=2 and R kind vocabulary both explicitly mean
            # absent/file/directory. No operation outcome is encoded here.
            store.put((2, b.kinds[i], a.op), e.kinds[i])
        return store

    def choose(self, frame, goal, actions, history, *, failed_attempts=()):
        if goal.equal or goal.sizes or goal.relations:
            raise ValueError('kind-only goal contract')
        view = ObservationView(frame, self.ops)
        wanted = dict(goal.kinds)
        target = tuple(wanted.get(h) for h in frame.handles)
        store = self.memory()
        rng = np.random.default_rng(410927 + self.state['revision'])
        if self.arm == 'no_planning':
            action = actions[int(rng.integers(len(actions)))]
        else:
            try:
                plan_agent(view, target, 1, rng, store=store)
            except Proposed as p:
                action = p.action
            else:
                return None
        if action not in actions:
            raise ValueError('historical proposal outside authorized action surface')
        i = frame.handles.index(action.args[0])
        predicted = store.get((2, frame.kinds[i], action.op))
        forecast = ScopedPartialForecast(frame.handles, copy.deepcopy(frame.parent), [],
            [('kind', [i], [] if predicted is None else [predicted])])
        row = dict(kind='THINK', epistemic_type='PREDICTION', authority=False,
                   revision=self.state['revision'], before=frame.to_dict(),
                   goal=goal.to_dict(), chosen=action.to_dict(), prediction=forecast.to_dict(),
                   retrieved_edges=store.queries, derived_memory_edges=len(store.d))
        if self.trace:
            with Path(self.trace).open('a', encoding='utf-8') as f:
                f.write(json.dumps(row)+'\n')
        return action, forecast, max(1, len(store.queries))

    def learn(self, event_id, before, action, after, history):
        row = dict(before=before.to_dict(), action=action.to_dict(), after=after.to_dict())
        if event_id in self.state['events']:
            raise ValueError('duplicate event')
        self.state['events'][event_id] = row
        self.state['records'].append(row)
        self.state['revision'] += 1
        return True
