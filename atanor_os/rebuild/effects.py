"""REBUILD_PLAN.md B: what an action will change, predicted from the start state, with its uncertainty.

An action is identified by its body, its tool and the arguments that stay the same objects from call to call (a tray, a
wing: an argument used with several others and never changed, in any position); two bodies never share an action, even
with the same tool and object names;
the result is a separate thing, predicted per output: the body's answer ('ok' / 'failed' / 'blocked') and each
argument's attribute right after. One action can have different results from different starts; cases are never merged
just because the tool is the same, and an action is never split into nodes just because results differ.

For every output, explanations are kept as long as no case contradicts them:
  CONST          always the same value                       (complexity 0)
  COPY(v)        equals the start value of input v           (complexity 1; v = the output's own attribute: unchanged)
  TABLE(S)       a lookup on the start values of inputs S    (complexity |S|, |S| <= 2; + 0.5 if a cell is a copy)
A cell of a TABLE (or the whole of CONST) is either a constant or a copy of one input's start value, and both may
sit in one table; a cell that fits both is ambiguous and both stay candidates until a case tells them apart. When no
explanation fits but this very start was seen with one result, that result is the prediction.
A prediction is given only when every explanation of the lowest complexity has seen this start (covers it), they all
agree, and no explanation of one more complexity is left uncovered by a start value of an input that never varied in
the cases (an untried condition); otherwise the answer is 'unknown' with the competing values. (Dev seeds 1-5: requiring
every explanation of one more complexity to cover too lost a third of the new combinations without removing any error;
requiring nothing of them made errors on untried conditions only.) When a later case
contradicts an earlier one with exactly the same start, the world (not the evidence) changed: the earlier cases are
kept as counter-examples but no longer fitted.
Baselines on the same cases: EXACT (an identical start, else unknown), LAST (identical start, else the latest case of
the action), CORE (the first demonstration's change applied to any start, as the baseline core's effect claim does).
"""
import hashlib
import itertools
import json
import math
from collections import defaultdict

MAX_S = 2
NO = object()                                          # a cell with no single constant


def freeze(d):
    return json.dumps(d, sort_keys=True, default=str)


def flat(objs):
    """Arguments' observations -> {(position, attribute): value}."""
    return {(i, a): v for i, o in enumerate(objs) for a, v in sorted((o or {}).items())}


class Case:
    __slots__ = ('x', 'y', 't', 'actor')

    def __init__(self, x, y, t, actor):
        self.x, self.y, self.t, self.actor = x, y, t, actor


def outputs(before, after, resp):
    y = {} if resp is None else {('r',): resp}
    for i, (b, a) in enumerate(zip(before, after)):
        for k in sorted(set(b or {}) | set(a or {})):
            y[(i, k)] = (a or {}).get(k, '-')
    return y


class ActionModel:
    """All cases of one action (tool + its constant arguments)."""

    def __init__(self, key):
        self.key = key
        self.cases, self.superseded = [], []
        self._h = {}

    def add(self, case):
        same = [c for c in self.cases if c.x == case.x and any(c.y[k] != case.y[k] for k in c.y.keys() & case.y.keys())]
        if same:                                           # identical start, different result: the world changed (only
                                                           # what both observed counts: a demonstration has no answer)
            cut = max(c.t for c in same)
            self.superseded += [c for c in self.cases if c.t <= cut]
            self.cases = [c for c in self.cases if c.t > cut]
        self.cases.append(case)
        self._h = {}

    tiered = True

    def values(self, v):
        if ('vals', v) not in self._h:
            self._h[('vals', v)] = {c.x.get(v) for c in self.cases}
        return self._h[('vals', v)]

    def untried(self, v, val):
        """A start value is an untried condition when the input never varied in the cases, or when it is absent where
        it was always present (or present where always absent): '-' is the observation interface's 'no value' in
        every body."""
        seen = self.values(v)
        if val in seen:
            return False
        return len(seen) < 2 or (val == '-') != any(s == '-' for s in seen) and all((s == '-') == (next(iter(seen)) == '-') for s in seen)

    def inputs(self):
        return sorted({k for c in self.cases for k in c.x})

    def hypotheses(self, out):
        """Consistent explanations of one output: [(complexity, kind, arg, table)]."""
        if out not in self._h:
            self._h[out] = self._hypotheses(out)
        return self._h[out]

    def _hypotheses(self, out):
        """A TABLE cell holds the cases whose start has the same values on S; it is consistent when they all end in one
        value (a constant) or all end in the start value of one input (a copy: unchanged, or taken from an argument).
        Both kinds of cell may sit in one table: 'sealing a bay makes it sealed; on a wing nothing changes'."""
        ins = self.inputs()
        hs = []
        whole = self._cell(self.cases, out, ins)
        if whole is not None:
            const, copies = whole
            if const is not NO:
                hs.append((0, 'CONST', None, {(): whole}))
            for v in sorted(copies, key=str):
                hs.append((1, 'COPY', v, None))
        for k in range(1, MAX_S + 1):
            for S in itertools.combinations(ins, k):
                groups = {}
                for c in self.cases:
                    groups.setdefault(tuple(c.x.get(s) for s in S), []).append(c)
                tab = {}
                for key, cs in groups.items():
                    cell = self._cell(cs, out, ins)
                    if cell is None:
                        tab = None
                        break
                    tab[key] = cell
                if tab is not None:                        # a cell that can only be a copy makes the table half a step
                    mixed = any(c[0] is NO for c in tab.values())   # more complex than one of constants
                    hs.append((k + (0.5 if mixed else 0), 'TABLE', S, tab))
        return hs

    @staticmethod
    def _cell(cases, out, ins):
        ys = {freeze(c.y.get(out)) for c in cases}
        const = json.loads(next(iter(ys))) if len(ys) == 1 else NO
        copies = set(ins)
        for c in cases:
            copies &= {v for v in copies if c.x.get(v) == c.y.get(out)}
            if not copies:
                break
        if const is NO and not copies:
            return None
        return const, frozenset(copies)

    @staticmethod
    def _candidates(cell, x):
        """A cell's possible values for this start: its constant, and this start's own value of every input it copied."""
        const, copies = cell
        out = {freeze(const)} if const is not NO else set()
        return out | {freeze(x[v]) for v in copies if v in x}

    def predict_out(self, out, x, slack=1):
        same = [c for c in self.cases if c.x == x]
        exact = {freeze(c.y.get(out)) for c in same}
        hs = self.hypotheses(out)
        if not hs:
            if len(exact) == 1:                            # nothing simple explains it, but this very start was seen
                return {'known': True, 'value': json.loads(next(iter(exact))), 'conditions': ['identical start'], 'support': len(same)}
            return {'known': False, 'why': 'no consistent explanation', 'competing': sorted({freeze(c.y.get(out)) for c in self.cases})}
        low = min(h[0] for h in hs)
        use = [h for h in hs if h[0] <= low + slack]
        preds, uncovered = set(), []
        for cx, kind, arg, tab in use:
            if kind == 'CONST':
                preds |= self._candidates(tab[()], x)
            elif kind == 'COPY':
                if arg in x:
                    preds.add(freeze(x[arg]))
                else:
                    uncovered.append((kind, arg))
            else:
                key = tuple(x.get(s) for s in arg)
                if key in tab:
                    preds |= self._candidates(tab[key], x)
                elif cx == low or self.tiered is False or any(self.untried(s, x.get(s)) for s in arg):
                    uncovered.append((kind, arg))          # a simplest explanation, or a condition that never varied: unknown
                # else: a more complex explanation, and only a new combination or a new value of an input that varied
                # in the cases without the simplest explanations needing it: not counted
        conds = sorted({str(h[2]) for h in hs if h[0] == low})
        if uncovered or len(preds) != 1:
            if len(exact) == 1:
                return {'known': True, 'value': json.loads(next(iter(exact))), 'conditions': ['identical start'], 'support': len(same)}
            return {'known': False, 'why': 'unseen start for a simple explanation' if uncovered else 'explanations disagree',
                    'competing': sorted(preds), 'uncovered': [str(u) for u in uncovered][:6], 'conditions': conds}
        return {'known': True, 'value': json.loads(next(iter(preds))), 'conditions': conds, 'support': len(self.cases)}


def action_key(body, tool, args, constants):
    """constants: (body, argument) pairs."""
    if len(args) < 2:
        return (body, tool, len(args), ())
    return (body, tool, len(args), tuple((i, a) for i, a in enumerate(args) if (body, a) in constants))


def _digest(d):
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')).hexdigest()


def model_digest(models):
    """A fingerprint of every model's cases, in the order learned."""
    case = lambda c: [sorted(c.x.items(), key=str), sorted(c.y.items(), key=str), c.t, c.actor]
    return _digest([[str(k), [case(c) for c in m.cases], [case(c) for c in m.superseded]]
                    for k, m in sorted(models.items(), key=lambda kv: str(kv[0]))])


class Effects:
    """The conditional effect model over all actions, plus the baselines, fed the same cases."""

    def __init__(self, slack=1, tiered=True):
        self._models, self.slack, self.tiered = {}, slack, tiered
        self.body = None                                   # the body queries are about (a mind may live in several)
        self.bodies = set()
        self.seen_with = defaultdict(set)                  # (body, argument), the other arguments it was called with, and
        self.changed = set()                               # whether it ever changed: one used with several others and
                                                           # never changed is a constant of the action (a tray, a folder)
        self.raw, self._grouped_by = [], None              # every case as observed; grouped into actions on demand
        self.first_demo = {}

    def scope(self, body=None):
        """Which body a query is about: as said, else self.body, else the only one seen (a single-body run says nothing)."""
        body = body if body is not None else self.body
        if body is not None or len(self.bodies) <= 1:
            return body if body is not None else next(iter(self.bodies), None)
        raise ValueError(f'this mind has lived in {sorted(map(str, self.bodies))}: say which body')

    def _qualified(self):
        return frozenset(a for a, w in self.seen_with.items() if len(w) >= 2 and a not in self.changed)

    def constants(self, body=None):
        body = self.scope(body)
        return frozenset(a for b, a in self._qualified() if b == body)

    @property
    def models(self):
        """Cases grouped by action. When what counts as a constant argument changes, every case is grouped again, so
        early cases of an action are never left under another identity."""
        cs = self._qualified()
        if self._grouped_by != cs:
            self._models, self.first_demo = {}, {}
            for r in self.raw:
                self._group(r, cs)
            self._grouped_by = cs
        return self._models

    def _group(self, r, cs):
        body, tool, args, before, after, resp, t, actor = r
        key = action_key(body, tool, args, cs)
        m = self._models.setdefault(key, ActionModel(key))
        m.tiered = self.tiered
        x = flat(before)
        y = outputs(before, after, resp)
        m.add(Case(x, y, t, actor))
        if actor in ('person', 'teacher', 'unknown') and key not in self.first_demo and resp in ('ok', None):
            self.first_demo[key] = {k: v for k, v in y.items() if k != ('r',) and x.get(k) != v}

    def observe(self, e):
        """Learn from one experience (an act with before and after observed)."""
        act = e.get('action')
        if not act or e.get('before') is None or e.get('after') is None:   # nothing guessed for what was not observed
            return False
        args = act['args']
        body = e.get('body') or self.scope()               # a trial that does not name its body is in the one this is about
        self.bodies.add(body)
        before = [e['before'].get(a) for a in args]
        after = [(e.get('after') or {}).get(a) for a in args]
        for i, a in enumerate(args if e.get('actor') not in ('self', 'other') else ()):   # (another Self's watched trials are probes too)   # an action's identity comes from the
            if len(args) > 1:                                                 # course; own trials probe it (explore.py)
                self.seen_with[(body, a)].add(tuple(args[:i] + args[i + 1:]))
            if before[i] != after[i]:
                self.changed.add((body, a))
        r = e.get('response')
        resp = None if r is None else ('blocked' if r.get('guard') else ('ok' if r.get('ok') else 'failed'))   # not observed: no case for it
        row = (body, act['tool'], list(args), before, after, resp, e['t'], e.get('actor'))
        self.raw.append(row)
        if self._grouped_by == self._qualified():
            self._group(row, self._grouped_by)
        else:                                              # what counts as a constant changed: group everything again
            self._grouped_by = None                        # (it may change back before the next look; no case may be lost)
        return True

    def digest(self):
        """A fingerprint of everything learned (equal for models learned live and rebuilt from the same experiences)."""
        models = self.models
        return _digest([model_digest(models), sorted((str(k), sorted(v)) for k, v in self.seen_with.items()),
                        sorted(map(str, self.changed)), sorted((str(k), sorted(v.items(), key=str)) for k, v in self.first_demo.items())])

    def model(self, tool, args, body=None):
        return self.models.get(action_key(self.scope(body), tool, args, self._qualified()))

    def predict(self, tool, args, before, reader='NEW', body=None):
        """A BAYES reader name ending in 'G' (W_GUARD_PLAN.md) holds a confident answer when this start has a value never met
        on an attribute that had one single value in every case with that answer: nothing ever showed that the attribute
        does not matter."""
        if reader.startswith('BAYES') and reader.endswith('G'):
            p = self._predict(tool, args, before, reader[:-1], body)
            y = p.get('outcome')
            if y is not None:
                m, x, seen = self.model(tool, args, body), flat(before), {}
                for c in m.cases:
                    if c.y.get(('r',)) == y.get(('r',)):
                        for k, v in c.x.items():
                            seen.setdefault(k, set()).add(v)
                if any(v not in seen.get(k, ()) and len(seen.get(k, ())) == 1 for k, v in x.items()):
                    return {'outcome': None, 'why': 'a new value on an attribute never seen to vary'}
            return p
        return self._predict(tool, args, before, reader, body)

    def _predict(self, tool, args, before, reader='NEW', body=None):
        """before: the arguments' observations now. -> {'outcome': {output: value} or None, 'why', 'unknown': [...]}"""
        m = self.model(tool, args, body)
        x = flat(before)
        outs = sorted({k for c in m.cases for k in c.y}, key=str) if m else []
        if not m or not m.cases:
            return {'outcome': None, 'why': 'action never seen'}
        if reader in ('EXACT', 'LAST'):
            same = [c for c in m.cases if c.x == x]
            if same:
                return {'outcome': same[-1].y, 'seen': True}
            if reader == 'EXACT':
                return {'outcome': None, 'why': 'no identical start'}
            last = max(m.cases, key=lambda c: c.t)
            return {'outcome': {k: (x.get(k, v) if k != ('r',) and last.x.get(k) == v else v) for k, v in last.y.items()}, 'seen': False}
        if reader == 'CORE':
            ch = self.first_demo.get(m.key)
            if ch is None:
                return {'outcome': None, 'why': 'no demonstration'}
            y = {('r',): 'ok'}
            for k in outs:
                if k != ('r',):
                    y[k] = ch.get(k, x.get(k, '-'))
            return {'outcome': y}
        if reader.startswith('BAYES'):
            tau = float(reader[5:] or 0.95)
            if getattr(m, '_bayes_n', None) != (len(m.cases), tau):
                m._bayes, m._bayes_n = BayesAction(m, tau), (len(m.cases), tau)
            pm = m._bayes
        y, unknown, detail = {}, [], {}
        for o in outs:
            p = pm.predict_out(o, x) if reader.startswith('BAYES') else m.predict_out(o, x, self.slack)
            if not p['known']:
                unknown.append(o)
                detail[str(o)] = p
            else:
                y[o] = p['value']
        if unknown:
            return {'outcome': None, 'why': 'uncertain', 'unknown': [str(u) for u in unknown], 'detail': detail, 'partial': {str(k): v for k, v in y.items()}}
        return {'outcome': y}


class BayesAction:
    """REBUILD_PLAN.md B, second form (one principle in place of the rule above): average over explanations.
    An explanation is a set S of at most three inputs; the cases are split into cells by their start values on S, and
    every cell is a constant or a copy of one input's start value. Inputs are each argument's attributes and, for
    each, whether it has a value at all ('-' is the observation interface's 'no value').
      prior     P(S) = 1/4 for each size 0-3, shared evenly within the size
      evidence  per cell: 1/2 * [one value] * 1/V  +  1/2 * (#inputs it copied) / n     (V = values seen + 1)
      predict   per S: a seen cell's posterior over constant / copy; an unseen cell's prior (spread over the V values
                and the n copies); summed over S by posterior weight. Answer when one value reaches tau.
    Inputs that never varied keep their share of the prior, so a start that differs from all cases in such an input is
    uncertain without any special rule; an input that varied with no effect costs its explanations evidence."""

    max_s = 3                                          # dev: two inputs could not explain the climate bays' heat (kind, level, sealed)

    def __init__(self, model, tau):
        self.m, self.tau = model, tau
        self._cache = {}

    @staticmethod
    def feats(x):
        f = dict(x)
        for k, v in x.items():
            f[('has',) + k] = v != '-'
        return f

    def _fit(self, out):
        """Explanations are enumerated over the inputs that varied in the cases only. An input that never varied (one
        value in every case) splits no cell, so a set S = R + K (K such inputs) has the evidence of R, and for a query
        it either matches K (then it predicts as R) or puts the query in an unseen cell. Those sets are counted in
        closed form (the same posterior as enumerating them, at a fraction of the cost)."""
        if out in self._cache:
            return self._cache[out]
        cases = [(self.feats(c.x), c.y.get(out)) for c in self.m.cases if out in c.y]
        ins = sorted({k for f, _ in cases for k in f}, key=str)
        n = max(len(ins), 1)
        V = len({freeze(y) for _, y in cases}) + 1
        vals = {v: {freeze(f.get(v)) for f, _ in cases} for v in ins}
        fixed = {v: json.loads(next(iter(vals[v]))) for v in ins if len(vals[v]) == 1}
        vary = [v for v in ins if v not in fixed]
        memo, hyps = {}, []
        for k in range(0, self.max_s + 1):
            for R in itertools.combinations(vary, k):
                groups = defaultdict(list)
                for i, (f, _) in enumerate(cases):
                    groups[tuple(f.get(s) for s in R)].append(i)
                logp, tab = 0.0, {}
                for key, idx in groups.items():
                    t = tuple(idx)
                    if t not in memo:
                        cs = [cases[i] for i in idx]
                        ys = {freeze(y) for _, y in cs}
                        const = 0.5 / V if len(ys) == 1 else 0.0
                        cop = [v for v in ins if all(f.get(v) == y for f, y in cs)]
                        ev = const + 0.5 * len(cop) / n
                        memo[t] = None if ev == 0 else (next(iter(ys)) if len(ys) == 1 else None, const, cop, math.log(ev))
                    cell = memo[t]
                    if cell is None:
                        logp = None
                        break
                    logp += cell[3]
                    tab[key] = cell[:3]
                if logp is not None:
                    hyps.append((logp, R, tab))
        P = self.max_s + 1
        prior = lambda s: 1 / P / math.comb(n, s) if s <= n else 0.0
        nc = len(fixed)
        if hyps:
            top = max(h[0] for h in hyps)
            hyps = [(math.exp(h[0] - top), R, tab) for h in hyps for R, tab in [(h[1], h[2])]]
            z = sum(w * sum(math.comb(nc, j) * prior(len(R) + j) for j in range(0, self.max_s - len(R) + 1)) for w, R, _ in hyps)
            hyps = [(w / z, R, tab) for w, R, tab in hyps]
        self._cache[out] = (hyps, ins, n, V, {freeze(y) for _, y in cases}, fixed, prior)
        return self._cache[out]

    def predict_out(self, out, x):
        hyps, ins, n, V, seen_vals, fixed, prior = self._fit(out)
        if not hyps:
            return {'known': False, 'why': 'no consistent explanation'}
        f = self.feats(x)
        nc = len(fixed)
        miss = sum(f.get(v) != c for v, c in fixed.items())     # never-varied inputs this start differs in
        dist = defaultdict(float)

        def spread(mass):                                      # an unseen cell: anything it could be
            for val in seen_vals:
                dist[val] += mass * 0.5 / V
            dist['<other>'] += mass * 0.5 / V
            for v in ins:
                dist[freeze(f.get(v))] += mass * 0.5 / n
        for w, R, tab in hyps:
            js = range(0, self.max_s - len(R) + 1)
            match = w * sum(math.comb(nc - miss, j) * prior(len(R) + j) for j in js)
            other = w * sum((math.comb(nc, j) - math.comb(nc - miss, j)) * prior(len(R) + j) for j in js)
            key = tuple(f.get(s) for s in R)
            if key in tab:
                val, const, cop = tab[key]
                tot = const + 0.5 * len(cop) / n
                if val is not None:
                    dist[val] += match * const / tot
                for v in cop:
                    dist[freeze(f.get(v))] += match * (0.5 / n) / tot
            else:
                spread(match)
            if other:
                spread(other)
        best = max(dist, key=dist.get)
        p = dist[best]
        if p >= self.tau and best != '<other>':
            return {'known': True, 'value': json.loads(best), 'p': round(p, 4)}
        return {'known': False, 'why': 'uncertain', 'p': round(p, 4), 'competing': sorted(dist, key=dist.get, reverse=True)[:3]}
