"""After magi-review-02: (A) replay every recorded fs C episode under the current learner (which logs/episodes
differ, and how); (B) rebuilt models vs recorded model_C.json for the v4 runs (semantic identity: pre/effects/
support/status per operator; the 'kinds' field changed shape with type_attrs); (C) re-analysis of rule agreement
with the stricter measure (near-miss cell, unknown effects, filled) for the recorded models."""
import collections, contextlib, io, json, shutil, sqlite3
from pathlib import Path
from atanor_os.core.types import Experience
from atanor_os.eval.run import BODIES, evaluate, read_jsonl
from atanor_os.eval.oracle import rule_agreement
from atanor_os.agent.models import DocModel, RetrievalModel, RuleModel

OUT = Path('atanor_os/results/review02-reanalysis'); OUT.mkdir(parents=True, exist_ok=True)
report = {'replay': {}, 'model_identity': {}, 'agreement': {}}


def exps_of(res, seed, with_train=False):
    ex = [Experience.from_json(j) for j in read_jsonl(f'atanor_os/results/{res}/explore/experiences_s{seed}.jsonl')]
    if with_train:
        db = sqlite3.connect(f'atanor_os/results/{res}/eval_s{seed}/journal_train.sqlite')
        ex += [Experience.from_json(json.loads(r[0])) for r in db.execute('SELECT data FROM experiences ORDER BY rowid')]
        db.close()
    return ex


print('== A. replay of recorded fs C episodes under the current learner (identical action sequences / completion)')
for res in ('p1-test-02', 'p1-test-03-contrast', 'p1-test-03-scarce'):
    for seed in (1, 2, 3, 4, 5):
        ex = exps_of(res, seed)
        out = Path(f'atanor_os/runs/replay/{res}_s{seed}'); shutil.rmtree(out, ignore_errors=True)
        with contextlib.redirect_stdout(io.StringIO()):
            recs, _, _ = evaluate('test', seed, ex, ['C'], 20, out)
        ref = {r['task']: r for r in read_jsonl(f'atanor_os/results/{res}/records.jsonl') if r['condition'] == 'C' and r['seed'] == seed}
        same = [r['task'] for r in recs if [(s['tool'], s['args'], s['ok']) for s in r['steps']] == [(s['tool'], s['args'], s['ok']) for s in ref[r['task']]['steps']]]
        done_now = sum(r['judge']['completed'] for r in recs); done_rec = sum(ref[t]['judge']['completed'] for t in ref)
        acts_now = sum(r['actions'] for r in recs); acts_rec = sum(ref[t]['actions'] for t in ref)
        report['replay'][f'{res}/s{seed}'] = {'identical': len(same), 'completed_now': done_now, 'completed_recorded': done_rec,
                                              'actions_now': acts_now, 'actions_recorded': acts_rec,
                                              'differing_tasks': sorted(set(ref) - set(same))}
        print(f"  {res} s{seed}: identical {len(same)}/20 | completed {done_now} vs recorded {done_rec} | actions {acts_now} vs {acts_rec} | differ {sorted(set(ref) - set(same))}")

print('== B. rebuilt models vs recorded model_C.json (v4 runs): per-operator pre/effects/support/status')
def sem(opjson):
    return None if opjson is None else {k: opjson[k] for k in ('pre', 'effects', 'support', 'status', 'counter')}
for res, body, conds in (('p1-test-03-scarce-rerun', 'fs', ('C',)), ('p2-h2-01', 'fs', ('C', 'CT')), ('p3-view-01', 'view', ('C',))):
    for seed in (1, 2, 3, 4, 5):
        for cond in conds:
            ex = exps_of(res, seed, with_train=(cond == 'CT'))
            m = RuleModel(ex, spec=BODIES[body]['spec']).describe()
            rec = json.load(open(f'atanor_os/results/{res}/eval_s{seed}/model_{cond}.json', encoding='utf-8'))
            same = all(sem(m['operators'][t]) == sem(rec['operators'][t]) for t in m['operators'])
            byte_same = json.dumps(m, default=str, indent=1) == json.dumps(rec, default=str, indent=1)
            report['model_identity'][f'{res}/s{seed}/{cond}'] = {'semantic_identical': same, 'byte_identical': byte_same}
            print(f"  {res} s{seed} {cond}: semantic identical {same} | byte identical {byte_same}")

print('== C. stricter rule agreement (near-miss cell, unknown effects) for recorded models')
def agree(model, body, seed, tag):
    B = BODIES[body]
    r = rule_agreement(model, k=20, seed=1000 + seed, root=Path(f'atanor_os/runs/agree2/{tag}'), block=B['sem_block'], pre_fn=B['pre'])
    tot = {k: sum(v[k] for v in r['per_tool'].values()) for k in ('checks', 'fp', 'fn', 'eff', 'unk', 'near_checks', 'near_fp')}
    bad = {t: {k: v[k] for k in ('fp', 'fn', 'eff', 'unk', 'near_checks', 'near_fp') if v[k]} for t, v in r['per_tool'].items() if t not in r['strict_tools']}
    report['agreement'][tag] = {'exact': r['n_exact'], 'strict': r['n_strict'], 'n_tools': r['n_tools'], 'filled': r['filled'],
                                'near_cells': r['near_cells'], 'totals': tot, 'non_strict': bad}
    print(f"  {tag}: exact {r['n_exact']}/{r['n_tools']} strict {r['n_strict']}/{r['n_tools']} filled {r['filled']} near {r['near_cells']} | {tot} | non-strict {bad}")
for seed in (1, 2, 3, 4, 5):
    ex = exps_of('p3-view-01', seed)
    spec = BODIES['view']['spec']
    for cond, cls in (('A', DocModel), ('B', RetrievalModel), ('C', RuleModel)):
        agree(cls(ex, spec=spec), 'view', seed, f'p3-view-01/s{seed}/{cond}')
for res in ('p1-test-03-contrast', 'p1-test-03-scarce-rerun'):
    for seed in (1, 2, 3, 4, 5):
        agree(RuleModel(exps_of(res, seed), spec=BODIES['fs']['spec']), 'fs', seed, f'{res}/s{seed}/C')
for seed in (1, 2, 3, 4, 5):
    agree(RuleModel(exps_of('p2-h2-01', seed, with_train=True), spec=BODIES['fs']['spec']), 'fs', seed, f'p2-h2-01/s{seed}/CT')
(OUT / 'reanalysis.json').write_text(json.dumps(report, indent=1, default=str), encoding='utf-8')
print('saved', OUT / 'reanalysis.json')
