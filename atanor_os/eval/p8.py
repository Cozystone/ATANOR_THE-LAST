"""P8 harness (evaluator side). Learning and testing run in separate processes:
  learn  -> reads today's experience logs, writes each condition's representation / config
  test   -> for INTERNAL conditions runs in an EMPTY directory holding only the representation file, with an
            audit hook that records any attempt to open an experience log (INVALID if one happens);
            measures prediction on unseen situations and task completion.
"""
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

from ..agent.concepts import FAMILIES_ALL, FAMILIES_FLAT, CaseModel, ConceptModel, Representation, atoms, build, concept_use, revise
from ..agent.loop import run_episode
from ..agent.models import RuleModel
from ..core.journal import Journal
from ..core.types import Experience
from .generator import make_task
from .oracle import true_pre
from .view_tasks import make_view_task, view_true_pre

PKG = Path(__file__).resolve().parents[1]
R = PKG / 'results'
ORDER = ['p1-test-01', 'p1-test-02', 'p1-test-02-adapt', 'p1-test-03-contrast', 'p1-test-03-scarce', 'p1-test-03-scarce-rerun', 'p2-h2-01',
         'p3-view-01', 'p5-h4-fs-control', 'p5-h4-fs-target', 'p5-h4-view-control', 'p5-h4-view-target']
VIEW_RUNS = {'p3-view-01', 'p5-h4-view-control', 'p5-h4-view-target'}
BUDGETS = {'INTERNAL_2KB': 2048, 'INTERNAL_8KB': 8192, 'INTERNAL_32KB': 32768, 'INTERNAL_INF': None}


def load_experience():
    """Chronological, deduplicated by (tool, atom signature, outcome, raw effect). Returns {body: [Experience]} and counts."""
    seq = {'fs': [], 'view': []}
    raw_n = {'fs': 0, 'view': 0}
    for run in ORDER:
        body = 'view' if run in VIEW_RUNS else 'fs'
        for s in range(1, 6):
            p = R / run / 'explore' / f'experiences_s{s}.jsonl'
            if p.exists():
                for l in p.read_text(encoding='utf-8').splitlines():
                    if l.strip():
                        seq[body].append(Experience.from_json(json.loads(l)))
                        raw_n[body] += 1
    out = {}
    for body, es in seq.items():
        seen, keep = set(), []
        for e in es:
            k = (e.tool, atoms(body, e.pre, e.args), e.succeeded,
                 json.dumps([sorted(e.post.get(a, {}).items()) for a in e.args], default=str))
            if k not in seen:
                seen.add(k)
                keep.append(e)
        out[body] = keep
    return out, raw_n


def halves(es):
    h = len(es) // 2
    return es[:h], es[h:]


def learn(out):
    """Process 1: build every condition's model input. INTERNAL: build on E1, revise with E2 (old log not used)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    exp, raw_n = load_experience()
    info = {'raw_actions': raw_n, 'dedup': {b: len(v) for b, v in exp.items()}, 'internal': {}}
    for body, es in exp.items():
        e1, e2 = halves(es)
        info[f'{body}_halves'] = [len(e1), len(e2)]
        for cond, budget in BUDGETS.items():
            t = time.time()
            r1 = build(body, e1, budget)
            (out / f'{cond}_{body}_R1.json').write_text(r1.dumps(), encoding='utf-8')
            r2, change = revise(r1, e2, budget)
            (out / f'{cond}_{body}.json').write_text(r2.dumps(), encoding='utf-8')
            info['internal'][f'{cond}_{body}'] = {'bytes_R1': r1.size(), 'bytes': r2.size(), 'concepts_R1': len(r1.dictionary), 'concepts': len(r2.dictionary),
                                                  'change': change, 'concept_use': concept_use(r2.rules), 'seconds': round(time.time() - t, 1)}
    (out / 'training_keys.json').write_text(json.dumps(sorted(training_keys(exp))), encoding='utf-8')
    info['learn_seconds'] = round(time.time() - t0, 1)
    (out / 'learn_info.json').write_text(json.dumps(info, indent=1, default=str), encoding='utf-8')
    return info


# ---------------- test process ----------------
class LogAudit:
    attempts = []

    @staticmethod
    def hook(event, args):
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.fspath(args[0])
            p = p.decode(errors='ignore') if isinstance(p, bytes) else p
            if 'experiences_s' in p or os.sep + 'explore' + os.sep in p:
                LogAudit.attempts.append(p)


def fs_block(rng, root):
    ws, goal, _ = make_task(rng.randrange(1000, 3000), 'test', root)
    return ws, goal.universe


def view_block(rng, root):
    ws, goal, _ = make_view_task(rng.randrange(1000, 3000), 'test', root)
    return ws, []


def _accuracy(ag):
    tot = sum(v['checks'] for v in ag['per_tool'].values())
    bad = sum(v['fp'] + v['fn'] + v['eff'] for v in ag['per_tool'].values())
    return {'checks': tot, 'accuracy': 1 - bad / max(1, tot), 'fp': sum(v['fp'] for v in ag['per_tool'].values()),
            'fn': sum(v['fn'] for v in ag['per_tool'].values()), 'eff': sum(v['eff'] for v in ag['per_tool'].values()),
            'near_checks': sum(v['near_checks'] for v in ag['per_tool'].values()), 'per_tool': ag['per_tool'], 'filled': ag['filled']}


def make_model(cond, body, rep_dir):
    if cond.startswith('INTERNAL'):
        rep = Representation.loads((Path(rep_dir) / f'{cond}_{body}.json').read_text(encoding='utf-8'))
        return ConceptModel(rep, cond), rep.size()
    exp, _ = load_experience()
    es = exp[body]
    if cond == 'FULL_RAW':
        return ConceptModel(build(body, es, None, FAMILIES_FLAT, invent_concepts=False), cond), None
    if cond == 'FULL_STRUCT':
        return ConceptModel(build(body, es, None, FAMILIES_ALL, invent_concepts=False), cond), None
    if cond == 'CASE':
        return CaseModel(body, es), None
    if cond == 'FIXED':
        from ..agent.bootstrap import VIEW_DOCS
        from ..world.view_world import TOOLS as VIEW_TOOLS
        from ..agent.models import FS_SPEC
        spec = FS_SPEC if body == 'fs' else {'tools': VIEW_TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}
        return RuleModel(es, spec=spec), None
    raise ValueError(cond)


class _Fixed:
    """FIXED without the documentation fallback, so every condition answers from experience only."""

    def __init__(self, m):
        self.m, self.name = m, 'FIXED'

    def predict(self, state, tool, args, sig=None):
        post, st = self.m.predict(state, tool, args, sig)
        if st.endswith('documented'):
            return None, 'learned_fail'
        return post, st

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': 'FIXED'}


def test(cond, rep_dir, out, k=20, n_fs_tasks=60, n_view_tasks=20):
    """Process 2 for one condition."""
    sys.addaudithook(LogAudit.hook)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    res = {'cond': cond}
    train_keys = set(json.loads(Path(rep_dir, 'training_keys.json').read_text(encoding='utf-8')))   # hashes only, written by learn()
    for body in ('fs', 'view'):
        t0 = time.time()
        model, size = make_model(cond, body, rep_dir)
        if cond == 'FIXED':
            model = _Fixed(model)
        res[f'{body}_bytes'] = size
        block = fs_block if body == 'fs' else view_block
        ag = novel_agreement(model, k, 8008 if body == 'fs' else 8009, out / f'agree_{body}', block,
                             true_pre if body == 'fs' else view_true_pre, train_keys)
        res[f'{body}_prediction'] = {**_accuracy(ag), 'excluded_training_situations': ag['excluded_training_situations']}
        done = 0
        rows = []
        n = n_fs_tasks if body == 'fs' else n_view_tasks
        for t in range(n):
            ws, goal, meta = (make_task if body == 'fs' else make_view_task)(t, 'test', out / f'task_{body}' / f't{t}')
            j = Journal(out / f'task_{body}' / f'j{t}.sqlite')
            rec = run_episode(ws, goal, model, j, f'p8-{cond}-{body}-{t}')
            j.close()
            ok = goal.satisfied(ws.observe(goal.universe)) and not rec['keep_violated']
            done += ok
            rows.append({'task': t, 'template': meta['template'], 'completed': ok, 'actions': rec['actions'], 'noops': rec['noops'],
                         'planner_budget_exceeded': rec['planner_budget_exceeded']})
        res[f'{body}_tasks'] = {'n': n, 'completed': done, 'completion': done / n, 'rows': rows}
        res[f'{body}_seconds'] = round(time.time() - t0, 1)
    res['log_open_attempts'] = list(LogAudit.attempts)
    (out / f'test_{cond}.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
    return res


def verdict(results, learn_info, budget_bytes=8192):
    I, F, C = results['INTERNAL_8KB'], results['FULL_RAW'], results['CASE']
    if I['log_open_attempts'] or (I['fs_bytes'] or 0) > budget_bytes or (I['view_bytes'] or 0) > budget_bytes:
        return 'INVALID', {}
    acc = lambda r: r['fs_prediction']['accuracy']
    reuse = sum(1 for b in ('fs', 'view') for n, tools in learn_info['internal'][f'INTERNAL_8KB_{b}']['concept_use'].items() if len(tools) >= 2)
    changed = any(sum(len(learn_info['internal'][f'INTERNAL_8KB_{b}']['change'][k]) for k in ('added', 'removed', 'edited')) > 0 for b in ('fs', 'view'))
    r1_drop = results.get('INTERNAL_8KB_R1')
    no_drop = r1_drop is None or acc(I) >= acc(r1_drop) - 0.02
    c = {'pred_vs_full_raw_pp': 100 * (acc(I) - acc(F)), 'pred_vs_case_pp': 100 * (acc(I) - acc(C)),
         'tasks_fs_ge': I['fs_tasks']['completion'] >= max(F['fs_tasks']['completion'], C['fs_tasks']['completion']),
         'tasks_view_ge': I['view_tasks']['completion'] >= max(F['view_tasks']['completion'], C['view_tasks']['completion']),
         'reused_concepts': reuse, 'dictionary_changed': changed, 'no_drop_after_revision': no_drop}
    if acc(I) <= acc(F) or acc(I) <= acc(C):
        return 'WEAK', c
    if c['pred_vs_full_raw_pp'] >= 5 and c['pred_vs_case_pp'] >= 5 and c['tasks_fs_ge'] and c['tasks_view_ge'] and reuse >= 1 and changed and no_drop:
        return 'USEFUL_CONCEPTS', c
    return 'INCONCLUSIVE', c


def training_keys(exp):
    """Exact (tool, args, full pre-state) of every training experience: an unseen situation must differ."""
    keys = set()
    for es in exp.values():
        for e in es:
            keys.add(_key(e.tool, e.args, e.pre))
    return keys


def _key(tool, args, pre):
    return hashlib.sha256(json.dumps([tool, list(args), sorted((p, sorted(o.items())) for p, o in pre.items())], default=str).encode()).hexdigest()


def novel_agreement(model, k, seed, root, block, pre_fn, train_keys, max_blocks=400):
    """rule_agreement's stratified sampler (>= k per (tool, true outcome) cell, near-miss failures first),
    restricted to situations that do NOT occur in the training log; excluded samples are counted."""
    from .explore import ALL_CAPS
    from ..agent.lift import effect_attrs
    rng = random.Random(seed)
    root = Path(root)
    cells, near_cells, per_tool, excluded, block_i = None, {}, {}, 0, 0
    while block_i < max_blocks and (cells is None or min(cells.values()) < k):
        ws, targets = block(rng, root / f'b{block_i}')
        if cells is None:
            cells = {f'{t}:{o}': 0 for t in ws.TOOLS for o in ('success', 'failure')}
            near_cells = {t: 0 for t in ws.TOOLS}
            per_tool = {t: {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'near_checks': 0} for t in ws.TOOLS}
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(targets)
            buckets, succ_args = {}, {}
            for tool, args in ws.actions(sorted(pre)):
                if _key(tool, args, pre) in train_keys:
                    excluded += 1
                    continue
                ok = pre_fn(pre, tool, args)
                buckets.setdefault(f"{tool}:{'success' if ok else 'failure'}", []).append((tool, args))
                if ok:
                    succ_args.setdefault(tool, []).append(args)
            for tool, sa in succ_args.items():
                near = [(t, a) for t, a in buckets.get(f'{tool}:failure', []) if any(sum(x != y for x, y in zip(a, s_)) == 1 for s_ in sa)]
                if near:
                    buckets[f'{tool}:near'] = near
            needy = [c for c in buckets if (near_cells[c.split(':')[0]] if c.endswith(':near') else cells[c]) < k]
            if not needy:
                break
            nn = [c for c in needy if c.endswith(':near')]
            cell = rng.choice(nn or needy)
            tool, args = rng.choice(buckets[cell])
            predicted, _ = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            is_near = cell.endswith(':near')
            if is_near:
                near_cells[tool] += 1
                cells[f'{tool}:failure'] += 1
            else:
                cells[cell] += 1
            pt = per_tool[tool]
            pt['checks'] += 1
            pt['near_checks'] += int(is_near)
            if predicted is not None and not res['ok']:
                pt['fp'] += 1
            elif predicted is None and res['ok']:
                pt['fn'] += 1
            elif res['ok'] and not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a in args for k_ in effect_attrs(predicted[a])):
                pt['eff'] += 1
        block_i += 1
    filled = bool(cells) and min(cells.values()) >= k
    return {'per_tool': per_tool, 'cells': cells, 'near_cells': near_cells, 'filled': filled, 'excluded_training_situations': excluded}
