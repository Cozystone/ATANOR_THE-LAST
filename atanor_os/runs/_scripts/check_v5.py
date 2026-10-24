"""Learner v5 regression: recorded C episodes on all available fs exploration logs, rule agreement per log,
and the view body dev run + coverage (must not regress from v4)."""
import collections, shutil, io, contextlib, json
from pathlib import Path
from atanor_os.core.types import Experience
from atanor_os.eval.run import evaluate, read_jsonl, BODIES
from atanor_os.eval.explore import explore
from atanor_os.eval.oracle import rule_agreement
from atanor_os.eval.view_tasks import view_block
from atanor_os.agent.models import RuleModel
from atanor_os.agent.bootstrap import VIEW_DOCS
from atanor_os.world.view_world import TOOLS

print('== fs: recorded C episodes vs learner v5 (identical action sequences) + rule agreement of the v5 model')
for res, seed in (('p1-test-02', 1), ('p1-test-02', 2), ('p1-test-03-contrast', 1), ('p1-test-03-contrast', 3),
                  ('p1-test-03-scarce-rerun', 1), ('p1-test-03-scarce-rerun', 3)):
    exps = [Experience.from_json(j) for j in read_jsonl(f'atanor_os/results/{res}/explore/experiences_s{seed}.jsonl')]
    out = Path(f'atanor_os/runs/regress5_{res}_s{seed}'); shutil.rmtree(out, ignore_errors=True)
    with contextlib.redirect_stdout(io.StringIO()):
        recs, _, _ = evaluate('test', seed, exps, ['C'], 20, out)
    ref = {r['task']: r for r in read_jsonl(f'atanor_os/results/{res}/records.jsonl') if r['condition'] == 'C' and r['seed'] == seed}
    same = sum([(s['tool'], s['args'], s['ok']) for s in r['steps']] == [(s['tool'], s['args'], s['ok']) for s in ref[r['task']]['steps']] for r in recs)
    done = sum(r['judge']['completed'] for r in recs)
    ag = json.load(open(out / 'agreement_C.json', encoding='utf-8'))
    ag_rec = json.load(open(f'atanor_os/results/{res}/eval_s{seed}/agreement_C.json', encoding='utf-8')) if Path(f'atanor_os/results/{res}/eval_s{seed}/agreement_C.json').exists() else None
    m = RuleModel(exps)
    conv = m.ops['convert']
    print(f"  {res} s{seed}: identical {same}/20 done {done}/20 | v5 exact {ag['n_exact']}/5 {ag['exact_tools']}" +
          (f" | recorded exact {ag_rec['n_exact']}/5" if ag_rec else '') +
          f" | convert pre {None if conv is None or conv.pre is None else sorted(f'{l[0]}{l[1][0]}={l[2]}' for l in conv.pre)}")

print('== view: dev run seed 1 (contrast-kind 600) and coverage seeds 1-3 under v5')
ex = explore(1, 600, Path('atanor_os/runs/vcov5/x1'), policy='contrast-kind', block=view_block)
out2 = Path('atanor_os/runs/view_dev5'); shutil.rmtree(out2, ignore_errors=True)
with contextlib.redirect_stdout(io.StringIO()):
    recs, learn, sizes = evaluate('dev', 1, ex, ['C'], 12, out2, body='view')
print('  dev C completion', sum(r['judge']['completed'] for r in recs), '/ 12, noops', sum(r['noops'] for r in recs))
for seed in (1, 2, 3):
    ex = explore(seed, 600, Path(f'atanor_os/runs/vcov5/x{seed}'), policy='contrast-kind', block=view_block)
    m = RuleModel(ex, spec={'tools': TOOLS, 'docs': VIEW_DOCS})
    ag = rule_agreement(m, k=20, seed=1000 + seed, root=Path(f'atanor_os/runs/vcov5/ag{seed}'), block=BODIES['view']['sem_block'], pre_fn=BODIES['view']['pre'])
    print(f"  seed {seed}: exact {ag['n_exact']}/6 {ag['exact_tools']}  non-exact: { {t: v for t, v in ag['per_tool'].items() if v['fp'] or v['fn'] or v['eff']} }")
    for t in ('open', 'close', 'group', 'compare'):
        op = m.ops[t]
        print(f"     {t}: " + ' || '.join(','.join(f"{l[0][:3]}{l[1][0]}={l[2]}" for l in sorted(g['pre'], key=repr)) for g in op.groups))
