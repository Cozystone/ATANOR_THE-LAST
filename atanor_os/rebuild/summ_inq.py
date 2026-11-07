"""REBUILD_PLAN.md stage 3 summary: python -m atanor_os.rebuild.summ_inq <inq_dir> (sums every <body>-s<seed>.json in it)."""
import json,glob,collections,sys
T=collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for f in sorted(glob.glob(sys.argv[1]+'/*.json')):
    r=json.load(open(f)); b=r['body']
    T[(b,'NONE')]['here'].update(r['no_checks'])
    for p,v in r['policies'].items():
        T[(b,p)]['here'].update(v['here']); T[(b,p)]['later'].update(v['later']); T[(b,p)]['cost'].update(v['cost'])
for (b,p),v in sorted(T.items()):
    h,l=v['here'],v['later']; n=sum(h.values()); ln=sum(l.values()) or 1
    print(f"{b:6} {p:6} here right {h['right']/n:.3f} wrong {h['wrong']:3} | later right {l['right']/ln:.3f} wrong {l['wrong']:3} | cost {dict(v['cost'])}")
