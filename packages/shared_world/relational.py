"""Bounded empirical conditional joint-effect learner, not an ontology solver.

Operation identifiers are opaque schema keys. Programs are induced only from
observed transitions using KEEP, field COPY, and observed constants. Supplied
kind/size/equality/parent channels and a one-edge role grammar are inductive
biases, NOT autonomously invented predicates. Unchanged context is available to
the condition learner. Each branch applies one whole jointly learned program.

This module does not read native files, authenticate a Frame, infer persistent
identity from handles, or claim calibrated probabilities. Actual-vs-predicted
tags are a process API boundary; the supervisor must verify native provenance.
"""
from __future__ import annotations

import copy
from collections import Counter

import numpy as np

from packages.action_core.model import Forecast, HISTORY
from packages.action_core.schema import bind_schema
from packages.action_core.world import Action, Frame
from .contracts import JointForecast


FORMAT = 'conditional-joint-program-v3-partitioned'
MAX_NODES = 32


def _actual(frame):
    if type(frame) is not Frame:
        raise ValueError('learning requires actual Frame, not a forecast or caller envelope')
    # Frame is mutable: a valid tag is insufficient even for syntax validation.
    result = Frame.from_dict(frame.to_dict())
    if len(result.handles) > MAX_NODES:
        raise ValueError('referent budget exceeded')
    return result


def _view(frame):
    if type(frame) is Frame:
        frame = _actual(frame)
        return Forecast(np.eye(3)[frame.kinds].tolist(), list(frame.sizes),
                        copy.deepcopy(frame.equal), copy.deepcopy(frame.parent), frame.handles,
                        copy.deepcopy(frame.relations))
    if type(frame) is Forecast:
        result = Forecast.from_dict(frame.to_dict())
        if len(result.handles) > MAX_NODES:
            raise ValueError('referent budget exceeded')
        return result
    raise ValueError('prediction input must be Frame or Forecast')


def _action(action, frame, schema):
    if type(action) is not Action:
        raise ValueError('action must have the exact Action type')
    schema.index(action)
    if any(handle not in frame.handles for handle in action.args):
        raise ValueError('action is outside observation scope')


def _history(history, frame, schema):
    if type(history) not in (list, tuple):
        raise ValueError('history must be a sequence of prior observations')
    clean = []
    for item in history:
        if type(item) not in (list, tuple) or len(item) != 2:
            raise ValueError('invalid history item')
        past = _actual(item[0])
        _action(item[1], past, schema)
        if past.handles != frame.handles or past.relations.keys() != frame.relations.keys():
            raise ValueError('history observation scope changed')
        clean.append((past, item[1]))
    # Temporal authenticity is supervisor-owned, not inferable from Frame alone.
    return clean[-HISTORY:]


def _matrices(frame):
    return {'equal': frame.equal, **dict(sorted(frame.relations.items()))}


def _bindings(frame, action):
    """Argument roles + unique one-edge witnesses; never sort by native ID/value.

    All neighbours also enter aggregate context, including non-unique witnesses.
    Ambiguous neighbours are not arbitrarily chosen as effect destinations.
    """
    result = {f'a{p}': frame.handles.index(h) for p, h in enumerate(action.args)}
    for p, handle in enumerate(action.args):
        index = frame.handles.index(handle)
        for relation, matrix in {'parent': frame.parent, **_matrices(frame)}.items():
            for direction in ('out', 'in'):
                neighbours = [j for j in range(len(frame.handles)) if j != index and
                              (matrix[index][j] if direction == 'out' else matrix[j][index]) == 1]
                if len(neighbours) == 1:
                    result[f'{relation}_{direction}_a{p}'] = neighbours[0]
    # Aliases have a fixed name priority, invariant under handle permutation.
    unique = {}
    for name, index in result.items():
        if index not in unique.values():
            unique[name] = index
    return unique


def _groups(frame, binding, partitioned=False):
    reverse = {index: name for name, index in binding.items()}
    names = []
    anchors = [(name, index) for name, index in binding.items() if name in ('a0', 'a1')]
    matrices = {'parent': frame.parent, **_matrices(frame)}
    for i in range(len(frame.handles)):
        name = reverse.get(i, '*')
        if name == '*' and partitioned:
            # A quantified equivalence class of observed argument-relative roles.
            # No native IDs, operation semantics, arbitrary neighbour selection,
            # or group cardinality occurs in its name. KEEP still reads each
            # member's own old value; homogeneous effects may apply to any size.
            signature = [str(frame.kinds[i])]
            for _, anchor in anchors:
                for matrix in matrices.values():
                    signature.extend((str(int(matrix[i][anchor])), str(int(matrix[anchor][i]))))
            name += ':' + ','.join(signature)
        names.append(name)
    result = {}
    for i, name in enumerate(names):
        result.setdefault(('kind', name), []).append((i,))
        result.setdefault(('size', name), []).append((i,))
    for i, left in enumerate(names):
        for j, right in enumerate(names):
            for relation in _matrices(frame):
                result.setdefault((relation, left, right), []).append((i, j))
    return result


def _value(frame, field, address):
    if field == 'kind':
        return frame.kinds[address[0]]
    if field == 'size':
        return frame.sizes[address[0]]
    return _matrices(frame)[field][address[0]][address[1]]


def _expressions(field, binding, targets):
    # KEEP first is a declared simplicity bias, not an operator-specific effect.
    result = [('keep',)]
    if field in ('kind', 'size'):
        result.extend(('copy', name) for name in binding)
    else:
        result.extend(('row', name) for name in binding)
        result.extend(('column', name) for name in binding)
        result.extend(('pair', left, right) for left in binding for right in binding)
    if all(value == targets[0] for value in targets):
        result.append(('constant', targets[0]))
    return result


def _evaluate(expr, field, address, before, binding):
    op = expr[0]
    if op == 'keep':
        return _value(before, field, address)
    if op == 'constant':
        return expr[1]
    if op == 'copy':
        return _value(before, field, (binding[expr[1]],))
    if op == 'row':
        return _matrices(before)[field][binding[expr[1]]][address[1]]
    if op == 'column':
        return _matrices(before)[field][address[0]][binding[expr[1]]]
    if op == 'pair':
        return _matrices(before)[field][binding[expr[1]]][binding[expr[2]]]
    raise ValueError('unknown expression')


def _induce(before, action, after, partitioned=False):
    binding = _bindings(before, action)
    groups = _groups(before, binding, partitioned)
    program = {}
    for slot, addresses in groups.items():
        targets = [_value(after, slot[0], address) for address in addresses]
        candidates = [expr for expr in _expressions(slot[0], binding, targets)
                      if all(_evaluate(expr, slot[0], address, before, binding) == target
                             for address, target in zip(addresses, targets))]
        if not candidates:
            # Keep the actual record; do not invent an unexplained effect rule.
            return None
        program[slot] = candidates
    return program


def _intersect(left, right):
    if left.keys() != right.keys():
        return None
    result = {}
    for slot, expressions in left.items():
        allowed = set(right[slot])
        result[slot] = [expr for expr in expressions if expr in allowed]
        if not result[slot]:
            return None
    return result


def _apply(program, frame, action, partitioned=False):
    binding = _bindings(frame, action)
    groups = _groups(frame, binding, partitioned)
    if groups.keys() != program.keys():
        return None
    result = copy.deepcopy(frame)
    # All RHS values read the same before view: never partially updated outputs.
    for slot, addresses in groups.items():
        expr = program[slot][0]
        for address in addresses:
            value = _evaluate(expr, slot[0], address, frame, binding)
            if slot[0] == 'kind':
                result.kinds[address[0]] = int(value)
            elif slot[0] == 'size':
                result.sizes[address[0]] = float(value)
            else:
                _matrices(result)[slot[0]][address[0]][address[1]] = float(value)
    return _view(result)


def _features(frame, action):
    """Fixed observation grammar; all argument contexts can reach every output.

    Neighbour counts/kinds/sizes and argument-relative relations expose third
    entities even if they were unchanged by the action. No outcome is an input.
    """
    n = len(frame.handles)
    kinds = np.asarray(frame.kinds, dtype=float)
    if kinds.ndim == 1:
        kinds = np.eye(3)[kinds.astype(int)]
    sizes = np.asarray(frame.sizes, dtype=float)
    parent = np.asarray(frame.parent, dtype=float)
    equal = np.asarray(frame.equal, dtype=float)
    result = [n / MAX_NODES, *kinds.mean(0), float(sizes.mean())]
    indices = [frame.handles.index(h) for h in action.args]
    for pos in range(2):
        if pos >= len(indices):
            result.extend([0.] * 37)
            continue
        i = indices[pos]
        result.extend([1., *kinds[i], sizes[i]])
        for matrix in (parent, equal):
            for weights in (matrix[i], matrix[:, i]):
                count = weights.sum()
                norm = max(count, 1.)
                result.extend([count / MAX_NODES, *(weights @ kinds / norm),
                               float(weights @ sizes / norm)])
        for other in range(2):
            if other < len(indices):
                j = indices[other]
                result.extend([float(i == j), parent[i, j], parent[j, i], equal[i, j],
                               float(sizes[i] == sizes[j]), abs(sizes[i] - sizes[j])])
            else:
                result.extend([0.] * 6)
    # Generic additional channels: same context/role grammar for every name.
    # Future values are learned program effects, never recomputed using native IDs.
    for _, values in sorted(frame.relations.items()):
        matrix = np.asarray(values, dtype=float)
        result.append(float(matrix.mean()))
        for pos in range(2):
            if pos >= len(indices):
                result.extend([0.] * 14)
                continue
            i = indices[pos]
            for weights in (matrix[i], matrix[:, i]):
                count = weights.sum()
                norm = max(count, 1.)
                result.extend([count / MAX_NODES, *(weights @ kinds / norm),
                               float(weights @ sizes / norm)])
            for other in range(2):
                j = indices[other] if other < len(indices) else None
                result.extend([matrix[i, j], matrix[j, i]] if j is not None else [0., 0.])
    return np.asarray(result, dtype=float)


def _context(frame, action, history, schema):
    current = _features(frame, action)
    width = len(current) + len(schema.entries)
    past = [np.zeros(width, dtype=float)] * (HISTORY - len(history))
    for old, previous in history:
        indicator = np.eye(len(schema.entries))[schema.index(previous)]
        # Current roles read past context as well: prior caller roles need not
        # happen to have targeted the same third entity to retain its state.
        past.append(np.concatenate((_features(old, action), indicator)))
    return np.concatenate((current, *past))


def _gini(labels):
    counts = np.bincount(labels)
    return 1. - float(np.sum((counts / len(labels)) ** 2))


def _tree(x, y, indices, depth, max_depth):
    counts = Counter(int(y[i]) for i in indices)
    leaf = {'counts': counts, 'indices': indices}
    if len(counts) <= 1 or depth >= max_depth or len(indices) < 2:
        return leaf
    sub = x[indices]
    overall = sub.mean(0)
    # Rank input dimensions by between-label variance, using training rows only.
    between = np.zeros(x.shape[1])
    for label, count in counts.items():
        mean = sub[y[indices] == label].mean(0)
        between += count * (mean - overall) ** 2
    features = np.argsort(-between, kind='stable')[:32]
    baseline = _gini(y[indices])
    best = None
    for feature in features:
        unique = np.unique(sub[:, feature])
        if len(unique) <= 1:
            continue
        # At most two thresholds/feature and 64 split proposals per node.
        cuts = sorted(set((len(unique) // 3, 2 * len(unique) // 3)))
        for cut in cuts:
            cut = max(1, min(cut, len(unique) - 1))
            threshold = float((unique[cut - 1] + unique[cut]) / 2)
            mask = sub[:, feature] <= threshold
            left, right = indices[mask], indices[~mask]
            if not len(left) or not len(right):
                continue
            loss = (len(left) * _gini(y[left]) + len(right) * _gini(y[right])) / len(indices)
            if best is None or loss < best[0] - 1e-12:
                best = (loss, int(feature), threshold, left, right)
    if best is None or best[0] >= baseline - 1e-12:
        return leaf
    _, feature, threshold, left, right = best
    return {'feature': feature, 'threshold': threshold,
            'left': _tree(x, y, left, depth + 1, max_depth),
            'right': _tree(x, y, right, depth + 1, max_depth)}


def _leaf(tree, x):
    while 'feature' in tree:
        tree = tree['left' if x[tree['feature']] <= tree['threshold'] else 'right']
    return tree


class RelationalLearner:
    """Finite empirical mixture, with deterministic role program intersection.

    An incompatible observation creates another conditional branch; it does
    not erase the observation or prove a previous hypothesis universally false.
    Replay/rule bounds and one-edge grammar restrict expressivity. Greedy program
    merging is order-sensitive and no concept invention/capability is asserted.
    """
    def __init__(self, schema=None, *, max_records=512, max_rules=32, max_depth=6, updates=1, seed=1,
                 partitioned=False):
        del seed  # Deterministic algorithm, no semantic initialization.
        if (type(partitioned) is not bool or type(max_records) is not int or not 1 <= max_records <= 512 or
                type(max_rules) is not int or not 1 <= max_rules <= 32 or
                type(max_depth) is not int or not 0 <= max_depth <= 8 or
                type(updates) is not int or updates not in (0, 1)):
            raise ValueError('invalid bounded learner configuration')
        self.schema = bind_schema(schema)
        self.partitioned = partitioned
        self.max_records, self.max_rules, self.max_depth = max_records, max_rules, max_depth
        self.updates = updates
        self.rows, self.seen, self.revision = [], set(), 0
        self._derived = []  # Pure per-record computations, rebuilt on restore.
        self.cache = None

    def learn(self, event_id, before, action, after, history=()):
        if type(event_id) not in (str, int) or type(event_id) is bool:
            raise ValueError('event identity must be a string or integer')
        before, after = _actual(before), _actual(after)
        _action(action, before, self.schema)
        history = _history(history, before, self.schema)
        if (before.handles != after.handles or before.parent != after.parent or
                before.relations.keys() != after.relations.keys() or
                (self.rows and self.rows[0][0].relations.keys() != before.relations.keys())):
            raise ValueError('observation locator scope changed within transition')
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        self.revision += 1
        if self.updates:
            self.rows.append((before, action, after, history))
            self.rows = self.rows[-self.max_records:]
            self._derived.append((_induce(before, action, after, self.partitioned),
                                  _context(before, action, history, self.schema)))
            self._derived = self._derived[-self.max_records:]
            self.cache = None
        return True

    def _compile(self):
        result = {}
        for op, _ in self.schema.entries:
            rows = [(row, derived) for row, derived in zip(self.rows, self._derived)
                    if row[1].op == op]
            programs, inputs, labels, unsupported = [], [], [], 0
            for (before, action, after, history), (program, context) in rows:
                if program is None:
                    unsupported += 1
                    continue
                label = None
                for index, known in enumerate(programs):
                    common = _intersect(known, program)
                    if common is not None:
                        programs[index], label = common, index
                        break
                if label is None:
                    if len(programs) >= self.max_rules:
                        unsupported += 1
                        continue
                    programs.append(program)
                    label = len(programs) - 1
                inputs.append(context)
                labels.append(label)
            if inputs:
                x, y = np.stack(inputs), np.asarray(labels, dtype=int)
                result[op] = {'programs': programs, 'x': x,
                              'tree': _tree(x, y, np.arange(len(y)), 0, self.max_depth),
                              'unsupported': unsupported}
        self.cache = result

    def predict(self, frame, actions, history=()):
        view = _view(frame)
        if self.rows and self.rows[0][0].relations.keys() != view.relations.keys():
            raise ValueError('relation vocabulary changed; explicit retraining required')
        history = _history(history, view, self.schema)
        if type(actions) not in (list, tuple):
            raise ValueError('actions must be a sequence')
        for action in actions:
            _action(action, view, self.schema)
        if not actions:
            return []
        if self.cache is None:
            self._compile()
        # The symbolic program grammar only executes exact discrete branches.
        # A soft forecast is retained with maximal uncertainty, never argmaxed
        # into invented observation truth. The shared planner expands branches.
        discrete = all(sum(v == 1 for v in row) == 1 for row in view.kinds)
        discrete = discrete and all(v in (0, 1) for matrix in
            (view.equal, view.parent, *view.relations.values()) for row in matrix for v in row)
        actual_view = Frame([row.index(1) for row in view.kinds], list(view.sizes),
                            copy.deepcopy(view.equal), copy.deepcopy(view.parent), view.handles,
                            copy.deepcopy(view.relations)) if discrete else None
        outputs = []
        for action in actions:
            state = self.cache.get(action.op)
            if state is None or actual_view is None:
                outputs.append((JointForecast([(1., copy.deepcopy(view))]), 1.))
                continue
            x = _context(actual_view, action, history, self.schema)
            leaf = _leaf(state['tree'], x)
            branches, support = [], 0
            for label, count in sorted(leaf['counts'].items()):
                predicted = _apply(state['programs'][label], actual_view, action, self.partitioned)
                if predicted is not None:
                    branches.append((count, predicted))
                    support += count
            if not support:
                outputs.append((JointForecast([(1., copy.deepcopy(view))]), 1.))
                continue
            total = sum(leaf['counts'].values())
            uncertainty = 1. / (support + 1.) + (1. - support / total)
            uncertainty += 1. - max(count for count, _ in branches) / support
            distance = np.min(np.mean(np.abs(state['x'][leaf['indices']] - x), axis=1))
            uncertainty += min(1., float(distance))
            uncertainty += state['unsupported'] / max(1, len(state['x']) + state['unsupported'])
            outputs.append((JointForecast([(count / support, forecast) for count, forecast in branches]),
                            min(1., uncertainty)))
        return outputs

    def snapshot(self):
        return {'algorithm': 'relational', 'format': FORMAT, 'schema': self.schema.to_data(),
                'partitioned': self.partitioned,
                'max_records': self.max_records, 'max_rules': self.max_rules,
                'max_depth': self.max_depth, 'updates': self.updates, 'revision': self.revision,
                'seen': sorted(self.seen, key=lambda v: (type(v).__name__, str(v))),
                'rows': [{'before': b.to_dict(), 'action': a.to_dict(), 'after': f.to_dict(),
                          'history': [[x.to_dict(), y.to_dict()] for x, y in h]}
                         for b, a, f, h in self.rows]}

    @classmethod
    def restore(cls, value):
        fields = {'algorithm', 'format', 'schema', 'partitioned', 'max_records', 'max_rules', 'max_depth',
                  'updates', 'revision', 'seen', 'rows'}
        if type(value) is not dict or set(value) != fields or value['algorithm'] != 'relational' or value['format'] != FORMAT:
            raise ValueError('invalid relational checkpoint envelope')
        model = cls(value['schema'], max_records=value['max_records'], max_rules=value['max_rules'],
                    max_depth=value['max_depth'], updates=value['updates'], partitioned=value['partitioned'])
        if (type(value['revision']) is not int or value['revision'] < 0 or type(value['seen']) is not list or
                any(type(v) not in (str, int) for v in value['seen']) or
                len(set(value['seen'])) != len(value['seen']) or value['revision'] != len(value['seen']) or
                type(value['rows']) is not list or
                len(value['rows']) > min(model.max_records, value['revision'])):
            raise ValueError('invalid relational checkpoint metadata')
        for row in value['rows']:
            if type(row) is not dict or set(row) != {'before', 'action', 'after', 'history'}:
                raise ValueError('invalid transition checkpoint')
            before, after = _actual(Frame.from_dict(row['before'])), _actual(Frame.from_dict(row['after']))
            action = Action.from_dict(row['action'])
            _action(action, before, model.schema)
            history = _history([(Frame.from_dict(f), Action.from_dict(a)) for f, a in row['history']], before, model.schema)
            if (before.handles != after.handles or before.parent != after.parent or
                    before.relations.keys() != after.relations.keys() or
                    (model.rows and model.rows[0][0].relations.keys() != before.relations.keys())):
                raise ValueError('checkpoint scope mismatch')
            model.rows.append((before, action, after, history))
            model._derived.append((_induce(before, action, after, model.partitioned),
                                   _context(before, action, history, model.schema)))
        model.seen, model.revision = set(value['seen']), value['revision']
        return model


Learner = RelationalLearner
