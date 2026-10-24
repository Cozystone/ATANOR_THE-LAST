import pathlib, sys
P = pathlib.Path(sys.argv[1])
p = P / 'atanor_os/agent/rule_learner.py'; s = p.read_text(encoding='utf-8')

old = s[s.index('def _generalize(common, fsigs):'):s.index('def _type_key(e):')]
new = '''def _generalize(common, fsigs):
    """Order-independent generalization. A conjunction excludes a failure iff it holds a literal the failure
    lacks, so the most general consistent conjunctions are the minimal hitting sets of the per-failure
    "excluding literal" sets. When several exist the data cannot say which condition matters, so the rule
    keeps their UNION (every literal that is necessary in some minimal explanation) and leaves the choice to
    further contrast, not to an iteration order. Literals in no minimal explanation are dropped.
    Returns (conjunction, dropped literals, ids of failures the full conjunction already admits)."""
    pre = frozenset(common)
    unexplained = {i for i, s in fsigs if pre <= s}
    lits = sorted(pre, key=_order)
    covers = {frozenset(l for l in lits if l not in s) for i, s in fsigs if i not in unexplained}
    covers = [c for c in covers if not any(o < c for o in covers)]          # a subset's hit implies the superset's
    if not covers:
        return frozenset(), lits, unexplained
    minimal = []
    for size in range(1, len(lits) + 1):
        for cand in combinations(lits, size):
            cs = frozenset(cand)
            if any(m <= cs for m in minimal):
                continue
            if all(cs & c for c in covers):
                minimal.append(cs)
        if minimal and size >= max(len(m) for m in minimal) + 0 and all(
                any(m <= frozenset(c) for m in minimal) for c in combinations(lits, min(size + 1, len(lits)))):
            break                                                           # every larger set contains a minimal one
    kept = frozenset().union(*minimal)
    return kept, [l for l in lits if l not in kept], unexplained


'''
s = s.replace(old, new)
s = s.replace('from dataclasses import dataclass, field\n', 'from dataclasses import dataclass, field\nfrom itertools import combinations\n')
old = '''Generalization is not resolved by order: after the greedy pass, a dropped literal that COMPETES with a
kept one (either could have been dropped, not both) is restored, to a fixed point, so the rule keeps both
and leaves the question to further contrast instead of to the iteration order.'''
new = '''Generalization is order-independent: the most general consistent conjunctions are the minimal hitting
sets of the failures' excluding literals; when several exist the rule keeps their union (the data cannot
tell which condition matters) and leaves the choice to further contrast.'''
assert old in s; s = s.replace(old, new)
old = '''v5: competing literals are both kept (found when
the scarce re-execution learned convert without parent_kind(1)=dir where v1 had kept it; see DECISIONS.md).'''
new = '''v5: order-independent generalization (union of minimal
explanations; found when the scarce re-execution learned convert without parent_kind(1)=dir where v1 had
kept it — both are true conditions; see DECISIONS.md).'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

c = P / 'atanor_os/runs/_scripts/check_v5.py'; t = c.read_text(encoding='utf-8')
t = t.replace("f\" | convert pre {sorted(f'{l[0]}{l[1][0]}={l[2]}' for l in conv.pre)}\")",
              "f\" | convert pre {None if conv is None or conv.pre is None else sorted(f'{l[0]}{l[1][0]}={l[2]}' for l in conv.pre)}\")")
c.write_text(t, encoding='utf-8')
print('v5b patched')
