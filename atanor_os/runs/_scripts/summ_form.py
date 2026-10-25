"""Per form of composed command: uses, success, help, help on the first use, alone, wrong."""
import json, sys
from collections import defaultdict
sys.path.insert(0, '.')
from atanor_os.eval.life_gen import life
run, seed, compose, conds = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4].split(',')
compose = True if compose == 'True' else compose
L = life(seed, 30, compose)
form = {(d['day'], k): t.get('form') for d in L for k, t in enumerate(d['tasks'])}
for c in conds:
    try:
        rows = [json.loads(l) for l in open(f'{run}/{c}/days.jsonl', encoding='utf-8')]
    except FileNotFoundError:
        continue
    by = defaultdict(list)
    for r in rows:
        f = form[(r['day'], r['task'])]
        if f:
            by[f].append(r)
    print(c, 'all', f"{sum(r['success'] for r in rows)}/{len(rows)}", 'help', sum(r['help_score'] for r in rows), 'wrong', sum(r['outcome'] == 'wrong' for r in rows))
    for f, R in sorted(by.items()):
        alone = [r for r in R if not r['user']]
        print(f"  {f:11s} n {len(R):2d} ok {sum(r['success'] for r in R):2d} help {sum(r['help_score'] for r in R):3d} first-use help {R[0]['help_score']} "
              f"later help/use {sum(r['help_score'] for r in R[1:]) / max(1, len(R) - 1):.1f} alone {sum(r['success'] for r in alone)}/{len(alone)} wrong {sum(r['outcome'] == 'wrong' for r in R)}")
