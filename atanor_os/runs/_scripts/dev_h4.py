"""H4 dev check — exploration seeds 11-15 and agreement seeds 2000+s (the test run uses seeds 1-5 and 1000+s).
No test task is run. Usage: dev_h4.py <body> <policy> <steps>"""
import json, sys, time
from pathlib import Path
from atanor_os.agent.models import RuleModel
from atanor_os.eval.explore import explore
from atanor_os.eval.oracle import rule_agreement
from atanor_os.eval.run import BODIES

body, policy, steps = sys.argv[1], sys.argv[2], int(sys.argv[3])
B = BODIES[body]
rows = []
for seed in (11, 12, 13, 14, 15):
    root = Path(f'atanor_os/runs/dev_h4/{body}-{policy}-{seed}')
    t0 = time.perf_counter()
    ex = explore(seed, steps, root / 'x', policy=policy, block=B['block'], type_attrs=B['spec'].get('type_attrs', ('kind',)))
    xs = time.perf_counter() - t0
    m = RuleModel(ex, spec=B['spec'])
    ag = rule_agreement(m, k=20, seed=2000 + seed, root=root / 'ag', block=B['sem_block'], pre_fn=B['pre'])
    open_n = sum(len(g.get('open', ())) for op in m.ops.values() if op for g in op.groups)
    bad = {t: {k: v[k] for k in ('fp', 'fn', 'eff', 'near_fp') if v[k]} for t, v in ag['per_tool'].items() if t not in ag['exact_tools']}
    first = {}
    for i, e in enumerate(ex):
        if e.succeeded: first.setdefault(e.tool, i)
    rows.append({'seed': seed, 'first_success': first, 'exact': ag['n_exact'], 'strict': ag['n_strict'], 'n_tools': ag['n_tools'], 'open': open_n,
                 'successes': sum(e.succeeded for e in ex), 'targeted': getattr(explore, 'last_stats', {}).get('targeted_steps'),
                 'explore_s': round(xs, 1), 'non_exact': bad})
    print(json.dumps(rows[-1]), flush=True)
s = {'body': body, 'policy': policy, 'steps': steps, 'exact_sum': sum(r['exact'] for r in rows),
     'perfect_seeds': sum(r['exact'] == r['n_tools'] for r in rows), 'strict_sum': sum(r['strict'] for r in rows),
     'open_sum': sum(r['open'] for r in rows), 'first_success_max': {t: max(r['first_success'].get(t, steps) for r in rows) for t in B['spec']['tools']}, 'explore_s': sum(r['explore_s'] for r in rows)}
print('SUMMARY', json.dumps(s), flush=True)
Path(f'atanor_os/runs/dev_h4/summary-{body}-{policy}.json').write_text(json.dumps({'summary': s, 'rows': rows}, indent=1))
