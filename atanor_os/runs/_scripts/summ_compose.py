import json, sys
from collections import Counter
run = sys.argv[1]
for c in sys.argv[2].split(','):
    try:
        rows = [json.loads(l) for l in open(f'{run}/{c}/days.jsonl', encoding='utf-8')]
    except FileNotFoundError:
        continue
    comp = [r for r in rows if isinstance(r['ext'], list)]
    half = len(comp) // 2
    def s(R): return f"{sum(r['success'] for r in R)}/{len(R)} help {sum(r['help_score'] for r in R)} wrong {sum(r['outcome'] == 'wrong' for r in R)}"
    print(c, 'compose tasks: first half', s(comp[:half]), '| second half', s(comp[half:]),
          '| alone', s([r for r in comp if not r['user']]), '| all tasks', s(rows))
