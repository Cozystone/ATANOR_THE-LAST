import pathlib, sys
P = pathlib.Path(sys.argv[1])


def patch(rel, pairs):
    p = P / rel
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: anchor not found:\n{old[:200]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


# learner: expose each group's untested generalizations (literals common to its successes that were
# dropped without a contrasting success). Bookkeeping only: predictions are unchanged.
patch('atanor_os/agent/rule_learner.py', [
    ('''        pre = set(frozenset.intersection(*(lifted_pre(e.pre, e.args) for e in es)))
        unexplained = {i for i, s in fsigs if pre <= s}
        for lit in sorted(pre, key=_order):
            trial = pre - {lit}
            if not any(trial <= s for i, s in fsigs if i not in unexplained):
                pre = trial
                dropped.append(lit)
''', '''        pre = set(frozenset.intersection(*(lifted_pre(e.pre, e.args) for e in es)))
        unexplained = {i for i, s in fsigs if pre <= s}
        gdrop = []
        for lit in sorted(pre, key=_order):
            trial = pre - {lit}
            if not any(trial <= s for i, s in fsigs if i not in unexplained):
                pre = trial
                gdrop.append(lit)
        dropped += gdrop
'''),
    ('''        groups.append({'kinds': key, 'pre': frozenset(pre), 'effects': effects, 'support': len(es)})
''', '''        groups.append({'kinds': key, 'pre': frozenset(pre), 'effects': effects, 'support': len(es),
                       'open': frozenset(gdrop)})      # untested generalizations: every success had them
'''),
    ('''        if same:
            same['support'] += g['support']
''', '''        if same:
            same['support'] += g['support']
            same['open'] = same['open'] & g['open']             # common to the merged successes only
'''),
])

# explore: contrast-target
patch('atanor_os/eval/explore.py', [
    ("from ..agent.lift import lifted_pre\n", "from ..agent.lift import lifted_pre\nfrom ..agent.rule_learner import learn_operator\n"),
    ("POLICIES = ('novelty', 'scarce', 'contrast', 'contrast-role', 'contrast-kind')",
     "POLICIES = ('novelty', 'scarce', 'contrast', 'contrast-role', 'contrast-kind', 'contrast-target')"),
    ('''def explore(seed, steps, root, policy='novelty', block=fs_block):''',
     '''def targets_of(op, sigs, novel):
    """H4 targeted contrasts: novel actions that the learner's current rule predicts to succeed (some type
    group's conjunction holds) while flipping one of that group's UNTESTED generalizations (a literal every
    success so far had, dropped without contrast). Success removes the literal from the generalization
    question; failure becomes the counterexample that keeps it. Fewest flipped literals first."""
    if op is None or not op.groups:
        return []
    best, out = None, []
    for a in novel:
        s = sigs[a]
        flips = min((sum(1 for d in g['open'] if d not in s) for g in op.groups
                     if g['open'] and g['pre'] <= s and any(d not in s for d in g['open'])), default=None)
        if flips is None:
            continue
        if best is None or flips < best:
            best, out = flips, [a]
        elif flips == best:
            out.append(a)
    return out


def explore(seed, steps, root, policy='novelty', block=fs_block, type_attrs=('kind',)):'''),
    ('''    searched over types (e.g. panel x grp) instead of over instances.
    """''', '''    searched over types (e.g. panel x grp) instead of over instances.
    'contrast-target' (H4): as 'contrast-kind', but first prefer `targets_of` — the only policy that reads
    the learner's current rules (relearned for the chosen tool from the explorer's own log; never the
    evaluator's truth). `type_attrs` is the body's type declaration, as given to the learner.
    """'''),
    ('''    exps, seen, kind_seen, succ, succ_sigs, tools = [], {}, {}, {}, {}, None
''', '''    exps, seen, kind_seen, succ, succ_sigs, tools = [], {}, {}, {}, {}, None
    by_tool, ops, n_targeted = {}, {}, 0
'''),
    ("            if policy in ('scarce', 'contrast', 'contrast-role', 'contrast-kind'):\n",
     "            if policy in ('scarce', 'contrast', 'contrast-role', 'contrast-kind', 'contrast-target'):\n"),
    ('''            if policy in ('contrast', 'contrast-role', 'contrast-kind') and novel:
                near_fn = _near if policy == 'contrast' else _near_role
                near = [a for a in novel if near_fn(sigs[a], succ_sigs[tool])]
                pool = near or novel
                if policy == 'contrast-kind' and not near:
''', '''            targeted = False
            if policy in ('contrast', 'contrast-role', 'contrast-kind', 'contrast-target') and novel:
                near_fn = _near if policy == 'contrast' else _near_role
                near = [a for a in novel if near_fn(sigs[a], succ_sigs[tool])]
                pool = near or novel
                tg = targets_of(ops.get(tool), sigs, novel) if policy == 'contrast-target' else []
                if tg:
                    pool, targeted = tg, True
                elif policy in ('contrast-kind', 'contrast-target') and not near:
'''),
    ('''            exps.append(Experience(f'x{seed}-{b}-{s}', tool, tuple(args), pre, post, res['ok'], res['blocked'],
                                   res['ms'], False, f'explore-{seed}'))
    return exps''', '''            exps.append(Experience(f'x{seed}-{b}-{s}', tool, tuple(args), pre, post, res['ok'], res['blocked'],
                                   res['ms'], False, f'explore-{seed}'))
            n_targeted += int(targeted)
            if policy == 'contrast-target':
                by_tool.setdefault(tool, []).append(exps[-1])
                ops[tool] = learn_operator(tool, ws.TOOLS[tool], by_tool[tool], type_attrs)
    explore.last_stats = {'targeted_steps': n_targeted, 'steps': len(exps)}
    return exps'''),
])

# harness: pass the body's type declaration to the explorer
patch('atanor_os/eval/run.py', [
    ("    exps = explore(a.seed, a.steps, Path(a.out) / 'ws', policy=a.policy, block=BODIES[a.body]['block'])\n",
     "    exps = explore(a.seed, a.steps, Path(a.out) / 'ws', policy=a.policy, block=BODIES[a.body]['block'],\n"
     "                   type_attrs=BODIES[a.body]['spec'].get('type_attrs', ('kind',)))\n"),
    ("        exps = explore(seed, a.steps, out / 'explore' / f's{seed}', policy=a.policy, block=BODIES[a.body]['block'])\n",
     "        t_x = time.perf_counter()\n"
     "        exps = explore(seed, a.steps, out / 'explore' / f's{seed}', policy=a.policy, block=BODIES[a.body]['block'],\n"
     "                       type_attrs=BODIES[a.body]['spec'].get('type_attrs', ('kind',)))\n"
     "        explore_cost = {'explore_s': time.perf_counter() - t_x, **getattr(explore, 'last_stats', {})}\n"),
])
p = P / 'atanor_os/eval/run.py'; s = p.read_text(encoding='utf-8')
old = "        learn_costs[seed], sizes[seed] = lc, sz\n"
assert old in s
s = s.replace(old, "        lc['explore'] = explore_cost\n        learn_costs[seed], sizes[seed] = lc, sz\n", 1)
p.write_text(s, encoding='utf-8')

# tests
p = P / 'atanor_os/tests/test_learning.py'; s = p.read_text(encoding='utf-8')
s += '''

@pytest.mark.fs
def test_targeted_contrast_picks_untested_generalizations():
    """H4 machinery: with two convert successes (both into an existing directory) and failures that never
    isolate the parent, the rule drops one parent literal; targets_of proposes exactly the actions that
    keep the rule's conjunction and flip a dropped literal."""
    from atanor_os.agent.lift import lifted_pre
    from atanor_os.agent.rule_learner import learn_operator
    from atanor_os.core.types import Experience
    from atanor_os.eval.explore import targets_of
    F = lambda ext, par='dir': {'kind': 'file', 'ext': ext, 'hash': 'h' + ext, 'parent_kind': par}
    A = lambda ext, par='dir': {'kind': 'absent', 'ext': ext, 'hash': '-', 'parent_kind': par}
    st = {'a.txt': F('txt'), 'b.md': A('md'), 'c.csv': F('csv'), 'd.md': A('md')}
    post = {**st, 'b.md': {**F('md'), 'hash': 'x'}}
    exps = [Experience('1', 'convert', ('a.txt', 'b.md'), st, post, True),
            Experience('2', 'convert', ('a.txt', 'd.md'), st, {**st, 'd.md': {**F('md'), 'hash': 'y'}}, True),
            Experience('3', 'convert', ('c.csv', 'b.md'), st, st, False)]
    op = learn_operator('convert', 2, exps)
    assert op.groups[0]['open'], op.groups
    st2 = {**st, 'q/e.md': A('md', 'absent'), 'q': A('-')}
    cands = [('convert', ('a.txt', 'q/e.md')), ('convert', ('a.txt', 'b.md')), ('convert', ('c.csv', 'q/e.md'))]
    sigs = {a: lifted_pre(st2, a[1]) for a in cands}
    tg = targets_of(op, sigs, cands)
    assert ('convert', ('a.txt', 'q/e.md')) in tg and ('convert', ('a.txt', 'b.md')) not in tg, (tg, op.to_json())
'''
if 'import pytest' not in s:
    s = 'import pytest\n' + s
p.write_text(s, encoding='utf-8')
print('h4 patched')
