import pathlib, sys
P = pathlib.Path(sys.argv[1])


def patch(rel, pairs):
    p = P / rel
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: anchor not found:\n{old[:200]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/eval/explore.py', [(
    "    explore.last_stats = {'targeted_steps': n_targeted, 'steps': len(exps)}\n",
    "    first = {}\n"
    "    for i, e in enumerate(exps):\n"
    "        if e.succeeded:\n"
    "            first.setdefault(e.tool, i)\n"
    "    explore.last_stats = {'targeted_steps': n_targeted, 'steps': len(exps), 'first_success': first}\n")])

patch('atanor_os/eval/run.py', [
    ('''def run_tests(out, marks):''', '''def compare_agreement(run_a, run_b, cond='C'):
    """H4 primary: per seed, the number of tools whose frozen `cond` model agrees exactly with the true
    semantics (rule_agreement 'exact'), run a vs run b, plus strict counts and first-success steps."""
    def per_seed(run):
        m = json.loads((Path(run) / 'metrics.json').read_text(encoding='utf-8'))
        out = {}
        for sd, cs in m['learn_cost_s'].items():
            ag = cs[cond]['agreement']
            out[int(sd)] = {'exact': ag['n_exact'], 'strict': ag.get('n_strict'), 'n_tools': ag['n_tools'],
                            'filled': ag['filled'], 'first_success': cs.get('explore', {}).get('first_success'),
                            'explore_s': cs.get('explore', {}).get('explore_s')}
        return out, m
    a, ma = per_seed(run_a)
    b, mb = per_seed(run_b)
    seeds = sorted(set(a) & set(b))
    d = {s: a[s]['exact'] - b[s]['exact'] for s in seeds}
    xs = lambda r: sum(r[s]['explore_s'] or 0 for s in seeds)
    return {'cond': cond, 'a': str(run_a), 'b': str(run_b), 'seeds': seeds,
            'exact_a': sum(a[s]['exact'] for s in seeds), 'exact_b': sum(b[s]['exact'] for s in seeds),
            'delta_exact': sum(d.values()), 'per_seed_delta': d, 'seeds_lower': sum(v < 0 for v in d.values()),
            'strict_a': sum(a[s]['strict'] or 0 for s in seeds), 'strict_b': sum(b[s]['strict'] or 0 for s in seeds),
            'all_filled': all(a[s]['filled'] and b[s]['filled'] for s in seeds),
            'explore_cost_ratio': xs(a) / max(xs(b), 1e-9),
            'completion_a': ma['conditions'][cond]['completion'], 'completion_b': mb['conditions'][cond]['completion'],
            'verdict_a': ma['verdict'], 'verdict_b': mb['verdict'],
            'first_success_a': {s: a[s]['first_success'] for s in seeds}, 'first_success_b': {s: b[s]['first_success'] for s in seeds}}


def run_tests(out, marks):'''),
    ('''def cmd_compare(a):''', '''def cmd_compare(a):
    if a.metric == 'agreement':
        print(json.dumps(compare_agreement(a.a, a.b or a.a, a.cond), indent=1, default=str))
        return
    _cmd_compare(a)


def _cmd_compare(a):'''),
    ("    c.add_argument('--metric', default=None, choices=(None, 'plan_predicted', 'actions', 'noops', 'wall_s', 'plan_expanded'))\n",
     "    c.add_argument('--metric', default=None, choices=(None, 'plan_predicted', 'actions', 'noops', 'wall_s', 'plan_expanded', 'agreement'))\n"),
])

p = P / 'atanor_os/tests/test_harness.py'; s = p.read_text(encoding='utf-8')
s += '''

def test_compare_agreement_pairs_seeds(tmp_path):
    from atanor_os.eval.run import compare_agreement

    def run(name, exact):
        d = tmp_path / name
        d.mkdir()
        lc = {str(sd): {'C': {'agreement': {'n_exact': e, 'n_strict': e, 'n_tools': 5, 'filled': True}},
                        'explore': {'explore_s': 1.0, 'first_success': {'convert': 10 * sd}}} for sd, e in exact.items()}
        (d / 'metrics.json').write_text(json.dumps({'learn_cost_s': lc, 'verdict': 'X', 'conditions': {'C': {'completion': 1.0}}}))
        return d
    r = compare_agreement(run('a', {1: 5, 2: 5, 3: 4}), run('b', {1: 4, 2: 5, 3: 5}))
    assert r['delta_exact'] == 0 and r['seeds_lower'] == 1 and r['per_seed_delta'] == {1: 1, 2: 0, 3: -1}, r
    assert r['explore_cost_ratio'] == 1.0 and r['all_filled']
'''
p.write_text(s, encoding='utf-8')
print('h4b patched')
