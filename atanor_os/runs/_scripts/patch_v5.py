import pathlib, sys
P = pathlib.Path(sys.argv[1])
p = P / 'atanor_os/agent/rule_learner.py'; s = p.read_text(encoding='utf-8')

old = '''Learner version 4 (2026-10-24). v1: repr order, strict spec agreement. v2: type-last order and
prediction-consistent effects. v3: per-type groups (disjunctions such as "panel or compare").
v4: effect language widened from copies of hash/value to copies of any attribute (the view body's
compare inherits filter/sort from its source panel). For the filesystem body v2-v4 behave identically
(checked against recorded runs; see DECISIONS.md).'''
new = '''Generalization is not resolved by order: after the greedy pass, a dropped literal that COMPETES with a
kept one (either could have been dropped, not both) is restored, to a fixed point, so the rule keeps both
and leaves the question to further contrast instead of to the iteration order.

Learner version 5 (2026-10-24). v1: repr order, strict spec agreement. v2: type-last order and
prediction-consistent effects. v3: per-type groups (disjunctions such as "panel or compare").
v4: effect language widened from copies of hash/value to copies of any attribute (the view body's
compare inherits filter/sort from its source panel). v5: competing literals are both kept (found when
the scarce re-execution learned convert without parent_kind(1)=dir where v1 had kept it; see DECISIONS.md).'''
assert old in s; s = s.replace(old, new)
s = s.replace('LEARNER_VERSION = 4', 'LEARNER_VERSION = 5')

old = '''        pre = set(frozenset.intersection(*(lifted_pre(e.pre, e.args) for e in es)))
        unexplained = {i for i, s in fsigs if pre <= s}
        for lit in sorted(pre, key=_order):
            trial = pre - {lit}
            if not any(trial <= s for i, s in fsigs if i not in unexplained):
                pre = trial
                dropped.append(lit)
        counter |= unexplained
'''
new = '''        pre, drops, unexplained = _generalize(frozenset.intersection(*(lifted_pre(e.pre, e.args) for e in es)), fsigs)
        dropped += drops
        counter |= unexplained
'''
assert old in s; s = s.replace(old, new)

old = '''def _type_key(e):
'''
new = '''def _generalize(common, fsigs):
    """Most general conjunction of `common` that still excludes every failure it can exclude.
    Greedy drop in a fixed order (type literals last); then any dropped literal d that competes with a
    kept literal k (with d restored, k could be dropped instead) is restored, to a fixed point. Returns
    (conjunction, dropped literals, ids of failures the full conjunction already admits)."""
    pre = set(common)
    unexplained = {i for i, s in fsigs if pre <= s}
    fails = [s for i, s in fsigs if i not in unexplained]
    excludes = lambda conj: not any(conj <= s for s in fails)
    dropped = []
    for lit in sorted(pre, key=_order):
        if excludes(pre - {lit}):
            pre.remove(lit)
            dropped.append(lit)
    restored = True
    while restored:
        restored = False
        for d in sorted(dropped, key=_order):
            if any(excludes((pre | {d}) - {k}) for k in pre):
                pre.add(d)
                dropped.remove(d)
                restored = True
    return frozenset(pre), dropped, unexplained


def _type_key(e):
'''
assert old in s; s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('v5 patched')
