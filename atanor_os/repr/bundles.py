"""GEN3_BUNDLE_PROTOCOL.md: experience bundles read from world logs only, and a case comparison over them.

A bundle keeps one act as it was observed: the object's attributes before (and the context objects seen with it), the
action (tool and constant arguments), the actor, the attributes right after, the first later observation of the object
after an outside change (before anything else acted on it), and the numbers of other bundles that started the same way
but ended differently (counter-examples). Bundles are never merged into a rule.

No world is run and no body rule is used: constant arguments are the objects the log never shows changing; the object
acted on is the first argument that is not a constant.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ATTRS = ('kind', 'heat', 'air', 'wing', 'value', 'place', 'status', 'tag')     # whatever five a body's log carries


def read(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def _freeze(d):
    return tuple(sorted((k, v) for k, v in (d or {}).items()))


def change(pre, post):
    """What the act changed, as attribute -> new value (relative to the state before)."""
    return tuple(sorted((k, post[k]) for k in post if pre.get(k) != post.get(k)))


def build(rows, source=''):
    changed_ever = set()
    for r in rows:
        if r.get('event') in ('act', 'tick') and r.get('obs_before'):
            for o, a in r['obs_before'].items():
                if a != (r.get('obs_after') or {}).get(o):
                    changed_ever.add(o)
    bundles, open_, t = [], {}, 0                          # object -> bundle waiting for its later observation; t: ticks so far
    for i, r in enumerate(rows):
        if r.get('event') == 'tick':
            t += 1
        if r.get('event') == 'act' and r.get('obs_before') is not None:
            args = r['args']
            consts = [a for a in args if a not in changed_ever]
            obj = next((a for a in args if a in changed_ever), args[0])
            context = {o: a for o, a in r['obs_before'].items() if o not in args}
            for o in args:                                  # an act on the object closes any bundle waiting on it
                open_.pop(o, None)
            b = {'id': f'{source}#{i}', 't': t, 'tool': r['tool'], 'consts': consts, 'actor': r.get('actor'), 'object': obj,
                 'pre': r['obs_before'][obj], 'context': context, 'post': r['obs_after'][obj], 'ok': bool(r.get('ok')),
                 'blocked': r.get('error') == 'blocked', 'later': None, 'later_actor': None, 'counter': []}
            bundles.append(b)
            if b['ok']:
                open_[obj] = b
        elif r.get('event') == 'tick' and r.get('obs_before'):
            for o in r['obs_before']:
                if o in open_:
                    b = open_.pop(o)
                    b['later'], b['later_actor'] = r['obs_after'][o], r.get('actor')
    return bundles


def controls(rows):
    """Moves made in outside changes by objects no act had touched yet: change -> count."""
    out, acted = Counter(), set()
    for r in rows:
        if r.get('event') == 'act':
            acted |= set(r.get('args') or [])
        elif r.get('event') == 'tick' and r.get('obs_before'):
            for o, a in r['obs_before'].items():
                if o not in acted:
                    out[change(a, r['obs_after'][o])] += 1
    return out


def mark_counters(bundles):
    by = defaultdict(list)
    for b in bundles:
        by[(b['tool'], tuple(b['consts']), _freeze(b['pre']))].append(b)
    for group in by.values():
        for b in group:
            b['counter'] = [c['id'] for c in group if change(c['pre'], c['post']) != change(b['pre'], b['post'])]
    return bundles


class Memory:
    """Bundles kept whole; questions answered by comparing cases (BUNDLE) or by one result value per action (SINGLE)."""

    def __init__(self, bundles, control_moves):
        self.bundles = mark_counters(list(bundles))
        self.controls = control_moves
        self.by_action = defaultdict(list)
        for b in self.bundles:
            self.by_action[(b['tool'], tuple(b['consts']))].append(b)
        self.irrelevant = {k: self._irrelevant(v) for k, v in self.by_action.items()}

    @staticmethod
    def _irrelevant(cases):
        """Attributes seen to differ, alone, between two cases of the action that changed the same way."""
        out = set()
        for i, a in enumerate(cases):
            for b in cases[i + 1:]:
                diff = [k for k in a['pre'] if a['pre'].get(k) != b['pre'].get(k)]
                same = change(a['pre'], a['post'])
                if len(diff) == 1 and same and same == change(b['pre'], b['post']):   # nothing changing is no evidence
                    out.add(diff[0])
        return out

    def ask(self, pre, tool, consts):
        """BUNDLE: the change expected, with the cases used and the attributes matched or allowed; or a hold with the
        evidence needed."""
        key = (tool, tuple(consts))
        cases = self.by_action.get(key, [])
        if not cases:
            return {'answer': None, 'need': f'a case of {tool} {consts}'}
        allowed = self.irrelevant[key]
        usable = [c for c in cases if all(pre.get(k) == c['pre'].get(k) or k in allowed for k in set(pre) | set(c['pre']))]
        exact = [c for c in usable if c['pre'] == pre]
        use = exact or usable
        if not use:
            return {'answer': None, 'need': f'a case of {tool} {consts} starting from {_freeze(pre)}'}
        moves = Counter(change(c['pre'], c['post']) for c in use)
        if len(moves) > 1:
            return {'answer': None, 'need': f'cases that tell apart {sorted(moves)}', 'disagree': [c['id'] for c in use]}
        mv = next(iter(moves))
        return {'answer': mv, 'used': [c['id'] for c in use][:20], 'exact': bool(exact), 'since': min(c['t'] for c in use),
                'allowed': sorted(k for k in allowed if any(pre.get(k) != c['pre'].get(k) for c in use))}

    def ask_later(self, post, tool, consts):
        """The first change after an outside step, for an object left in state post by the act, and who did it: the
        outside when objects nobody acted on made the same move, the act (delayed) when they never did."""
        cases = [c for c in self.by_action.get((tool, tuple(consts)), []) if c['later'] is not None and c['post'] == post]
        if not cases:
            return {'answer': None, 'need': f'a later observation after {tool} from {_freeze(post)}'}
        moves = Counter(change(c['post'], c['later']) for c in cases)
        if len(moves) > 1:
            return {'answer': None, 'need': f'cases that tell apart {sorted(moves)}'}
        mv = next(iter(moves))
        who = 'outside' if self.controls.get(mv) else 'action'
        return {'answer': mv, 'who': who}

    def single(self, pre, tool, consts):
        """SINGLE (the current representation): the result value of the first case, whatever the start."""
        cases = self.by_action.get((tool, tuple(consts)), [])
        if not cases:
            return {'answer': None}
        first = cases[0]
        values = dict(change(first['pre'], first['post']))
        return {'answer': tuple(sorted((k, v) for k, v in values.items() if pre.get(k) != v))}


class ChainMemory(Memory):
    """GEN3_BUNDLE5_PROTOCOL.md: an attribute does not matter to an action when two cases differ in it and otherwise only
    in attributes already shown not to matter, and changed the same non-empty way; repeated to a fixed point. Not when a
    pair so placed changed differently (both non-empty). The pair that showed each attribute is kept as its evidence."""

    def __init__(self, bundles, control_moves):
        self.evidence = {}
        super().__init__(bundles, control_moves)

    def _irrelevant(self, cases):
        allowed, evidence = set(), {}
        for _ in range(10):
            support, against = {}, set()
            for i, a in enumerate(cases):
                ca = change(a['pre'], a['post'])
                for b in cases[i + 1:]:
                    diff = [k for k in set(a['pre']) | set(b['pre']) if a['pre'].get(k) != b['pre'].get(k)]
                    extra = [k for k in diff if k not in allowed]
                    if len(extra) != 1:
                        continue
                    cb = change(b['pre'], b['post'])
                    if ca and cb and ca != cb:
                        against.add(extra[0])
                    elif ca and ca == cb:
                        support.setdefault(extra[0], (a['id'], b['id']))
            new = {k for k in support if k not in against} | (allowed - against)
            if new == allowed:
                break
            allowed = new
            evidence = {k: support.get(k, evidence.get(k)) for k in allowed}
        if cases:
            self.evidence[(cases[0]['tool'], tuple(cases[0]['consts']))] = evidence
        return allowed
