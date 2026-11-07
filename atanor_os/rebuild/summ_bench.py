"""REBUILD_PLAN.md stage 2 summary: python -m atanor_os.rebuild.summ_bench <bench_dir> (sums every <body>-s<seed>.json in it)."""
import json,glob,collections,sys
tot=collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for f in sorted(glob.glob(sys.argv[1]+'/*.json')):
    r=json.load(open(f)); b=r['body']
    for rd,v in r['readers'].items():
        for p,c in v.items():
            for k in ('n','right','wrong','unknown'): tot[(b,rd)][p][k]+=c[k]
for (b,rd),v in sorted(tot.items()):
    a=v['all']; g=lambda p: f"{v[p]['right']}/{v[p]['n']} w{v[p]['wrong']}"
    print(f"{b:6} {rd:5} n={a['n']:5} right={a['right']/a['n']:.3f} wrong={a['wrong']:4} unk={a['unknown']:5} | seen {g('seen')} | newcomb {g('new_combination')} | newval {g('new_value')} | blocked {g('blocked')}")
