"""P8b harness (evaluator side): stable and drift scenarios for evidence-preserving revision.

Drift (world rules really change): fs 'move_dirs' (move accepts directories), view 'compare_replace'
(compare may replace an existing comparison view; amendment 1.1). E3 = 600 new exploration steps per body in the changed world.
Learning and testing run in separate processes; internal-representation conditions are tested in an
empty directory holding only their representation files (audit hook as in P8).
"""
import json
import random
import shutil
import sys
import time
from pathlib import Path

from ..agent.concepts import (FAMILIES_ALL, FAMILIES_FLAT, CaseModel, ConceptModelB, Representation, atoms, build, revise,
                              revise_b, uncertain_atoms)
from ..agent.lift import apply_effects
from ..agent.loop import run_episode
from ..agent.models import FS_SPEC, RuleModel
from ..core.journal import Journal
from ..core.types import Experience, Goal, Literal
from .explore import explore, fs_block as fs_explore_block
from .generator import BUDGET, layout, make_task, materialize
from .oracle import TRUE_EFFECTS, true_pre
from .p8 import LogAudit, _Fixed, _accuracy, fs_block as fs_test_block, halves, load_experience, novel_agreement, training_keys, view_block as view_test_block
from ..world.view_world import ViewWorkspace
from .view_tasks import TRUE_EFFECTS as VIEW_TRUE_EFFECTS, make_view_task, view_block as view_explore_block, view_true_pre
from ..world.view_world import PANELS

PKG = Path(__file__).resolve().parents[1]
OUT = PKG / 'results' / 'p8b'
DRIFT = {'fs': frozenset({'move_dirs'}), 'view': frozenset({'compare_replace'})}
CHANGED_TOOL = {'fs': 'move', 'view': 'compare'}
INTERNAL = ('R1_KEEP', 'R2_P8', 'P8B', 'P8B_NOVERIFY')
OTHERS = ('FULL_RAW', 'FULL_STRUCT', 'CASE', 'FIXED')
BUDGET_BYTES = 8192


# ---------------- worlds ----------------
def _set_drift(ws, drift):
    ws.drift = drift
    if hasattr(ws, 'data'):
        ws.data.drift = drift
    return ws


def explore_block(body, drift):
    base = fs_explore_block if body == 'fs' else view_explore_block

    def block(rng, root):
        ws, t = base(rng, root)
        return _set_drift(ws, drift), t
    return block


def test_block(body, drift):
    base = fs_test_block if body == 'fs' else view_test_block

    def block(rng, root):
        ws, t = base(rng, root)
        return _set_drift(ws, drift), t
    return block


def pre_fn(body, drift):
    if body == 'fs':
        def f(state, tool, args):
            if tool == 'move' and 'move_dirs' in drift:
                o = [state.get(a) for a in args]
                return (all(o) and o[0]['kind'] in ('file', 'dir') and o[1]['kind'] == 'absent' and o[1]['parent_kind'] == 'dir'
                        and not args[1].startswith(args[0] + '/'))
            return true_pre(state, tool, args)
        return f

    def g(state, tool, args):
        if tool == 'compare' and 'compare_replace' in drift:
            o = [state.get(a) for a in args]
            return all(o) and args[0] in PANELS and o[0]['kind'] in ('absent', 'compare') and o[1]['kind'] == 'panel'
        return view_true_pre(state, tool, args)
    return g


class DriftOracle:
    """Evaluator truth for a (possibly changed) world; validates the tasks."""
    name = 'ORACLE'

    def __init__(self, body, drift):
        self.body, self.pre = body, pre_fn(body, drift)
        self.effects = dict(TRUE_EFFECTS if body == 'fs' else VIEW_TRUE_EFFECTS)
        if body == 'fs' and 'move_dirs' in drift:
            self.effects['move'] = [(0, 'kind', ('const', 'absent')), (0, 'hash', ('const', '-')), (1, 'kind', ('copy', 0)), (1, 'hash', ('copy', 0))]

    def predict(self, state, tool, args, sig=None):
        if not self.pre(state, tool, args):
            return None, 'oracle_fail'
        return apply_effects(state, args, self.effects[tool]), 'oracle'

    def update(self, exp):
        pass


def drift_task(body, index, root):
    """Tasks that need the changed capability (fs: move a whole folder into archive/; view: point the open comparison
    view at another list without ever closing it)."""
    rng = random.Random(f'p8b-drift-{body}-{index}')
    if body == 'fs':
        files, ddir, dfile = layout(rng, 'test')
        ws = _set_drift(materialize(root, files, ddir, dfile), DRIFT['fs'])
        dest = f'archive/{ddir}'
        must = [Literal('kind', (dest,), 'dir'), Literal('kind', (ddir,), 'absent')]
        keep = [Literal('kind', (f,), 'file') for f in sorted(files)]
        return ws, Goal(f'p8b-drift-fs-{index}', must, keep, {}, dict(BUDGET), [ddir, dfile, 'archive', dest] + sorted(files)), {'template': 'move_folder'}
    files, ddir, dfile = layout(rng, 'test')
    data = materialize(root / 'data', files, ddir, dfile)
    e = rng.choice(('md', 'log', 'json'))
    k = rng.choice(('ext', 'size'))
    spec = {'p1': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'},
            'p3': {'kind': 'panel', 'filter': e, 'sort': k, 'group': 'none'},
            'cmp': {'kind': 'compare', 'filter': 'all', 'sort': 'name', 'group': 'none'}}     # cmp currently compares p1
    ws = _set_drift(ViewWorkspace(root / 'view', data, spec=spec), DRIFT['view'])
    must = [Literal('filter', ('cmp',), e), Literal('sort', ('cmp',), k)]
    keep = [Literal('kind', ('cmp',), 'compare'), Literal('kind', ('p1',), 'panel'), Literal('kind', ('p3',), 'panel'),
            Literal('filter', ('p3',), e)]                                    # the comparison view is never closed
    return ws, Goal(f'p8b-drift-view-{index}', must, keep, {'close_panels': False}, dict(BUDGET), []), {'template': 'compare_replace'}


# ---------------- changed-tool sampler (amendment 1.1) ----------------
def drift_block(body, drift):
    """Workspaces shaped like the drift tasks (indices disjoint from the 20 evaluation drift tasks)."""
    def block(rng, root):
        ws, goal, _ = drift_task(body, rng.randrange(1000, 3000), root)
        _set_drift(ws, drift)
        return ws, (goal.universe if body == 'fs' else [])
    return block


def situation_agreement(model, body, drift, changed, k, seed, root, train_keys, max_blocks=300):
    """Checks of the changed tool only. changed=True: situations where the original and the changed rule disagree
    (k checks); changed=False: situations where they agree (k true successes and k true failures)."""
    from .explore import ALL_CAPS
    from ..agent.lift import effect_attrs
    from .p8 import _key
    tool, new_pre, old_pre = CHANGED_TOOL[body], pre_fn(body, drift), pre_fn(body, frozenset())
    rng, root = random.Random(seed), Path(root)
    cells = {'success': 0, 'failure': 0}

    def need():
        return cells['success'] + cells['failure'] < k if changed else min(cells.values()) < k
    r = {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'excluded_training_situations': 0}
    blocks = (drift_block(body, drift), test_block(body, drift))
    b = 0
    while b < max_blocks and need():
        ws, targets = blocks[b % 2](rng, root / f'b{b}')
        for _ in range(25):
            if not need():
                break
            pre = ws.observe(targets)
            cand = {'success': [], 'failure': []}
            for t, args in ws.actions(ws.universe(targets) if body == 'fs' else sorted(pre)):
                if t != tool or (new_pre(pre, t, args) != old_pre(pre, t, args)) != changed:
                    continue
                if _key(t, args, pre) in train_keys:
                    r['excluded_training_situations'] += 1
                    continue
                cand['success' if new_pre(pre, t, args) else 'failure'].append(args)
            open_cells = [c for c in cand if cand[c] and (changed or cells[c] < k)]
            if not open_cells:
                break
            c = rng.choice(open_cells)
            args = rng.choice(cand[c])
            predicted, _ = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            cells[c] += 1
            r['checks'] += 1
            if predicted is not None and not res['ok']:
                r['fp'] += 1
            elif predicted is None and res['ok']:
                r['fn'] += 1
            elif res['ok'] and not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a in args for k_ in effect_attrs(predicted[a])):
                r['eff'] += 1
        b += 1
    r['cells'] = cells
    r['accuracy'] = 1 - (r['fp'] + r['fn'] + r['eff']) / max(1, r['checks'])
    return r


# ---------------- ATANOR's re-verification (small experiment in a sandbox of the current world) ----------------
class Verifier:
    def __init__(self, drift_by_body, root, max_blocks=40):
        self.drift_by_body, self.root, self.max_blocks = drift_by_body, Path(root), max_blocks
        self.experiments = []

    def __call__(self, body, tool, required, forbidden, concepts):
        from .explore import ALL_CAPS
        rng = random.Random(f'verify-{body}-{tool}-{len(self.experiments)}')
        block = explore_block(body, self.drift_by_body[body])
        for b in range(self.max_blocks):
            ws, targets = block(rng, self.root / f'{len(self.experiments)}_{b}')
            st = ws.observe(targets)
            for t, args in ws.actions(ws.universe(targets)):
                if t != tool:
                    continue
                at = atoms(body, st, args, FAMILIES_ALL, concepts)
                if required <= at and forbidden not in at:
                    res = ws.execute(t, args, ALL_CAPS)
                    self.experiments.append({'body': body, 'tool': tool, 'args': list(args), 'ok': res['ok']})
                    return bool(res['ok'])
        self.experiments.append({'body': body, 'tool': tool, 'args': None, 'ok': None})
        return None


# ---------------- learning process ----------------
def collect_e3(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    for body in ('fs', 'view'):
        p = out / f'E3_{body}.jsonl'
        if p.exists():
            continue
        exps = explore(31, 600, out / 'explore_e3' / body, policy='contrast-kind', block=explore_block(body, DRIFT[body]))
        p.write_text('\n'.join(json.dumps(e.to_json()) for e in exps), encoding='utf-8')


def load_e3(body):
    return [Experience.from_json(json.loads(l)) for l in (OUT / f'E3_{body}.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def learn(out=OUT):
    out = Path(out)
    collect_e3(out)
    exp, raw_n = load_experience()
    info = {'raw': raw_n, 'decisions': {}, 'sizes': {}}
    keys = training_keys(exp)
    for body in ('fs', 'view'):
        e1, e2 = halves(exp[body])
        e3 = load_e3(body)
        keys |= training_keys({body: e3})
        info[f'{body}_n'] = [len(e1), len(e2), len(e3)]
        r1 = build(body, e1, BUDGET_BYTES)
        reps = {('stable', 'R1_KEEP'): r1, ('drift', 'R1_KEEP'): r1}
        r2, _ = revise(r1, e2, BUDGET_BYTES)
        reps[('stable', 'R2_P8')] = r2
        reps[('drift', 'R2_P8')], _ = revise(r2, e3, BUDGET_BYTES)
        for cond, use_verifier in (('P8B', True), ('P8B_NOVERIFY', False)):
            v_stable = Verifier({'fs': frozenset(), 'view': frozenset()}, out / 'verify' / cond / 'stable') if use_verifier else None
            s, ch_s = revise_b(r1, e2, BUDGET_BYTES, v_stable)
            v_drift = Verifier(DRIFT, out / 'verify' / cond / 'drift') if use_verifier else None
            d, ch_d = revise_b(s, e3, BUDGET_BYTES, v_drift)
            reps[('stable', cond)], reps[('drift', cond)] = s, d
            info['decisions'][f'{cond}_{body}'] = {'stable': ch_s, 'drift': ch_d,
                                                   'experiments_stable': v_stable.experiments if v_stable else [],
                                                   'experiments_drift': v_drift.experiments if v_drift else []}
        for (scen, cond), rep in reps.items():
            d = out / 'reps' / cond
            d.mkdir(parents=True, exist_ok=True)
            (d / f'{scen}_{body}.json').write_text(rep.dumps(), encoding='utf-8')
            info['sizes'][f'{scen}_{cond}_{body}'] = rep.size()
    (out / 'reps' / 'training_keys.json').write_text(json.dumps(sorted(keys)), encoding='utf-8')
    (out / 'learn_info.json').write_text(json.dumps(info, indent=1, default=str), encoding='utf-8')
    return info


# ---------------- test process ----------------
class Audit:
    """Records every attempt to open an experience log (P8 logs, exploration folders, E3) during a test process."""
    attempts = []

    @staticmethod
    def hook(event, args):
        import os
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.fspath(args[0])
            p = p.decode(errors='ignore') if isinstance(p, bytes) else p
            if 'experiences_s' in p or 'E3_' in p or os.sep + 'explore' in p or '/explore' in p:
                Audit.attempts.append(p)


def _model(cond, scen, body, rep_dir):
    if cond in INTERNAL:
        rep = Representation.loads((Path(rep_dir) / cond / f'{scen}_{body}.json').read_text(encoding='utf-8'))
        return ConceptModelB(rep, cond), rep.size()
    exp, _ = load_experience()
    es = list(exp[body]) + (load_e3(body) if scen == 'drift' else [])
    if cond == 'FULL_RAW':
        return ConceptModelB(build(body, es, None, FAMILIES_FLAT, invent_concepts=False), cond), None
    if cond == 'FULL_STRUCT':
        return ConceptModelB(build(body, es, None, FAMILIES_ALL, invent_concepts=False), cond), None
    if cond == 'CASE':
        return CaseModel(body, es), None
    from ..agent.bootstrap import VIEW_DOCS
    from ..world.view_world import TOOLS as VIEW_TOOLS
    spec = FS_SPEC if body == 'fs' else {'tools': VIEW_TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}
    return _Fixed(RuleModel(es, spec=spec)), None


def _tasks(model, body, scen, out, kind):
    rows = []
    if kind == 'test':
        n = 60 if body == 'fs' else 20
        for t in range(n):
            ws, goal, meta = (make_task if body == 'fs' else make_view_task)(t, 'test', out / f'{kind}_{body}' / f't{t}')
            if scen == 'drift':
                _set_drift(ws, DRIFT[body])
            rows.append(_run(ws, goal, model, out / f'{kind}_{body}' / f'j{t}.sqlite', t, meta))
    else:
        for t in range(20):
            ws, goal, meta = drift_task(body, t, out / f'{kind}_{body}' / f't{t}')
            rows.append(_run(ws, goal, model, out / f'{kind}_{body}' / f'j{t}.sqlite', t, meta))
    return rows


def _run(ws, goal, model, jpath, t, meta):
    j = Journal(jpath)
    rec = run_episode(ws, goal, model, j, f'p8b-{t}')
    j.close()
    return {'task': t, 'template': meta['template'], 'completed': goal.satisfied(ws.observe(goal.universe)) and not rec['keep_violated'],
            'actions': rec['actions'], 'noops': rec['noops']}


def test(cond, rep_dir, out, k=20):
    sys.addaudithook(Audit.hook)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    keys = set(json.loads((Path(rep_dir) / 'training_keys.json').read_text(encoding='utf-8')))
    res = {'cond': cond}
    for scen in ('stable', 'drift'):
        for body in ('fs', 'view'):
            t0 = time.time()
            model, size = _model(cond, scen, body, rep_dir)
            drift = DRIFT[body] if scen == 'drift' else frozenset()
            ag = novel_agreement(model, k, 9100 + (scen == 'drift') * 10 + (body == 'view'), out / f'agree_{scen}_{body}', test_block(body, drift),
                                 pre_fn(body, drift), keys)
            acc = _accuracy(ag)
            ch = CHANGED_TOOL[body]
            pt = ag['per_tool']
            def a_of(tools):
                c = sum(pt[t]['checks'] for t in tools)
                b = sum(pt[t]['fp'] + pt[t]['fn'] + pt[t]['eff'] for t in tools)
                return 1 - b / max(1, c)
            r = {'bytes': size, 'prediction': acc['accuracy'], 'checks': acc['checks'], 'fp': acc['fp'], 'fn': acc['fn'], 'eff': acc['eff'],
                 'changed_tool_prediction_mixed': a_of([ch]), 'other_tools_prediction': a_of([t for t in pt if t != ch]),
                 'excluded_training_situations': ag['excluded_training_situations'], 'per_tool': pt,
                 'test_tasks': _tasks(model, body, scen, out / scen, 'test')}
            if scen == 'drift':
                sa = 9300 + (body == 'view')
                r['changed_situations'] = situation_agreement(model, body, drift, True, k, sa, out / f'chg_{body}', keys)
                r['changed_tool_unchanged_situations'] = situation_agreement(model, body, drift, False, k, sa + 2, out / f'unchg_{body}', keys)
                r['drift_tasks'] = _tasks(model, body, scen, out / scen, 'drift')
            r['seconds'] = round(time.time() - t0, 1)
            res[f'{scen}_{body}'] = r
    res['log_open_attempts'] = list(Audit.attempts)
    (out / f'test_{cond}.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
    return res


def oracle_check(out):
    """Task validity in both worlds (all tasks must be solvable with the true model)."""
    out = Path(out)
    r = {}
    for body in ('fs', 'view'):
        rows = _tasks(DriftOracle(body, DRIFT[body]), body, 'drift', out / 'oracle', 'drift')
        r[body] = sum(x['completed'] for x in rows) / len(rows)
    (out / 'oracle_check.json').write_text(json.dumps(r), encoding='utf-8')
    return r


def verdict(results, learn_info):
    out = {}
    for body in ('fs', 'view'):
        P, R1 = results['P8B'], results['R1_KEEP']
        if P['log_open_attempts'] or any((P[f'{s}_{body}']['bytes'] or 0) > BUDGET_BYTES for s in ('stable', 'drift')):
            out[body] = {'pass': False, 'invalid': True}
            continue
        solved = lambda r, key: {x['task'] for x in r[key] if x['completed']}
        def retention(scen):
            base = solved(R1[f'{scen}_{body}'], 'test_tasks')
            return 1.0 if not base else len(base & solved(P[f'{scen}_{body}'], 'test_tasks')) / len(base)
        st, dr = P[f'stable_{body}'], P[f'drift_{body}']
        wrong_rev = learn_info['decisions'][f'P8B_{body}']['stable']['counts'].get('revise', 0)
        c = {'stable_pred': st['prediction'], 'R1_stable_pred': R1[f'stable_{body}']['prediction'],
             'stable_completion': sum(x['completed'] for x in st['test_tasks']) / len(st['test_tasks']),
             'R1_stable_completion': sum(x['completed'] for x in R1[f'stable_{body}']['test_tasks']) / len(R1[f'stable_{body}']['test_tasks']),
             'stable_retention': retention('stable'), 'wrong_revisions_stable': wrong_rev,
             'drift_changed_pred': dr['changed_situations']['accuracy'], 'R1_drift_changed_pred': R1[f'drift_{body}']['changed_situations']['accuracy'],
             'drift_changed_checks': dr['changed_situations']['checks'],
             'drift_other_pred': dr['other_tools_prediction'], 'drift_changed_tool_unchanged_pred': dr['changed_tool_unchanged_situations']['accuracy'],
             'drift_task_completion': sum(x['completed'] for x in dr['drift_tasks']) / len(dr['drift_tasks']),
             'drift_retention': retention('drift')}
        ok = (c['stable_pred'] >= c['R1_stable_pred'] - 0.01 and c['stable_completion'] >= c['R1_stable_completion'] - 0.02
              and c['stable_retention'] >= 0.95 and c['wrong_revisions_stable'] <= 1
              and c['drift_changed_pred'] >= 0.90 and c['drift_changed_pred'] >= c['R1_drift_changed_pred'] + 0.20
              and c['drift_changed_checks'] >= 20 and c['drift_other_pred'] >= 0.95 and c['drift_changed_tool_unchanged_pred'] >= 0.95 and c['drift_task_completion'] >= 0.80 and c['drift_retention'] >= 0.95)
        out[body] = {'pass': ok, **c}
    n = sum(v.get('pass', False) for v in out.values())
    overall = 'MEMORY_UPDATE_OK' if n == 2 else ('PARTIAL' if n == 1 else 'FAIL')
    return overall, out
