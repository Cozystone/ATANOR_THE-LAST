"""Command line: semantics | explore | evaluate | pilot (evaluator-owned, charter §4 평가기). v2."""
import argparse
import copy
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

from ..agent.loop import run_episode
from ..agent.models import CouncilModel, DocModel, RetrievalModel, RuleModel
from ..core.journal import Journal
from ..core.types import Experience
from ..world.fs_world import ENV_VERSION
from . import metrics
from .explore import explore
from .generator import BUDGET, make_task
from .oracle import TrueModel, reachable, semantic_check

PKG = Path(__file__).resolve().parents[1]
CONDITIONS = {'A': DocModel, 'B': RetrievalModel, 'C': RuleModel, 'D': CouncilModel}


def write_jsonl(path, rows, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a' if append else 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def source_identity():
    """Digest of every .py under atanor_os plus git state, so a result names the code that produced it."""
    files = sorted(p for p in PKG.rglob('*.py') if 'runs' not in p.parts and 'results' not in p.parts)
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(PKG).as_posix().encode())
        h.update(p.read_bytes())
    ident = {'source_sha256': h.hexdigest()[:16], 'source_files': len(files)}
    try:
        ident['git_head'] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                                           cwd=str(PKG.parent), timeout=20).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'atanor_os'], capture_output=True, text=True,
                               cwd=str(PKG.parent), timeout=20).stdout
        ident['git_atanor_os_untracked_or_modified'] = bool(dirty.strip())
    except Exception as e:
        ident['git'] = f'unavailable: {type(e).__name__}'
    return ident


def judge(ws, goal, work):
    """Independent re-observation of the real workspace; partial is over the literals that were false at the start."""
    state = ws.observe(goal.universe)
    must = [l.holds(state) for l in goal.must]
    keep = [l.holds(state) for l in goal.keep]
    done_work = [l.holds(state) for l in work]
    return {'completed': all(must) and all(keep), 'partial': sum(done_work) / max(1, len(done_work)),
            'keep_ok': all(keep), 'work_literals': len(work)}


def build_model(cond, experiences):
    t0 = time.perf_counter()
    m = TrueModel() if cond == 'ORACLE' else CONDITIONS[cond](experiences)
    return m, time.perf_counter() - t0


def evaluate(split, seed, experiences, conditions, n_tasks, out, adapt=False, checks=None):
    out.mkdir(parents=True, exist_ok=True)
    records, learn, sizes, reach_cache = [], {}, {}, {}
    for cond in conditions:
        journal = Journal(out / f'journal_{cond}.sqlite')
        base, learn[cond] = build_model(cond, experiences)
        (out / f'model_{cond}.json').write_text(json.dumps(base.describe(), default=str, indent=1), encoding='utf-8')
        for t in range(n_tasks):
            ws, goal, meta = make_task(t, split, out / 'ws' / f'{cond}_{t}')
            initial = ws.observe(goal.universe)
            work = [l for l in goal.must if not l.holds(initial)]
            if t not in reach_cache:
                reach_cache[t] = reachable(ws, goal)
                if reach_cache[t] is None and checks is not None:
                    checks['unreachable'] = checks.get('unreachable', 0) + 1
            model = copy.deepcopy(base) if adapt else base
            if hasattr(model, 'reset_stats'):
                model.reset_stats()
            if tracemalloc.is_tracing():
                tracemalloc.reset_peak()
            rec = run_episode(ws, goal, model, journal, f'{split}-s{seed}-{cond}-t{t}', adapt=adapt)
            rec.update(task=t, template=meta['template'], target=meta['target'], seed=seed, split=split,
                       judge=judge(ws, goal, work), reachable_len=reach_cache[t],
                       peak_mem=tracemalloc.get_traced_memory()[1] if tracemalloc.is_tracing() else None,
                       council=model.stats() if hasattr(model, 'stats') else None)
            records.append(rec)
            print(json.dumps({'seed': seed, 'cond': cond, 'task': t, 'tpl': meta['template'],
                              'done': metrics.strict(rec), 'acts': rec['actions'], 'noops': rec['noops'],
                              'abstain': rec['abstained'], 'pbudget': rec['planner_budget_exceeded'],
                              'wall': round(rec['wall_s'], 2)}), flush=True)
        journal.close()
        sizes[cond] = {'journal_bytes': (out / f'journal_{cond}.sqlite').stat().st_size,
                       'model_json_bytes': (out / f'model_{cond}.json').stat().st_size}
    return records, learn, sizes


def env_info(a, seeds):
    return {'python': sys.version.split()[0], 'platform': platform.platform(), 'machine': platform.node(),
            'cpus': os.cpu_count(), 'env_version': ENV_VERSION, 'budget': BUDGET, 'steps': a.steps,
            'tasks': a.tasks, 'seeds': seeds, 'split': a.split, 'adapt': a.adapt, **source_identity()}


def run_tests(out, expr):
    r = subprocess.run([sys.executable, '-m', 'pytest', str(PKG / 'tests'), '-q', '-p', 'no:cacheprovider', '-k', expr],
                       capture_output=True, text=True, cwd=str(PKG.parent))
    (out / f"tests_{expr.replace(' ', '_')}.txt").write_text(r.stdout + r.stderr, encoding='utf-8')
    return r.returncode == 0


def cmd_semantics(a):
    r = semantic_check(a.k, seed=a.seed, root=a.out)
    print(json.dumps(r, default=str))
    sys.exit(0 if r['ok'] else 1)


def cmd_explore(a):
    exps = explore(a.seed, a.steps, Path(a.out) / 'ws')
    write_jsonl(Path(a.out) / 'experiences.jsonl', [e.to_json() for e in exps])
    per = {}
    for e in exps:
        k = per.setdefault(e.tool, [0, 0])
        k[0] += 1
        k[1] += e.succeeded
    print(json.dumps({'steps': len(exps), 'per_tool[attempts,successes]': per}))


def cmd_evaluate(a):
    exps = [Experience.from_json(j) for j in read_jsonl(a.experiences)]
    out = Path(a.out)
    checks = {'unreachable': 0, 'label': 'exploratory'}
    records, learn, sizes = evaluate(a.split, a.seed, exps, a.conditions.split(','), a.tasks, out, a.adapt, checks)
    write_jsonl(out / 'records.jsonl', records)
    summary = metrics.summarize(records, None, checks, {a.seed: learn}, env_info(a, [a.seed]), {a.seed: sizes})
    (out / 'metrics.json').write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    (out / 'REPORT.md').write_text(metrics.report(summary), encoding='utf-8')
    print(json.dumps({'verdict': summary['verdict'],
                      'completion': {c: round(v['completion'], 3) for c, v in summary['conditions'].items()}}))


def cmd_pilot(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    if a.skip_tests and a.label == 'pre-registered':
        sys.exit('refusing: a pre-registered run must execute the validity tests (use --label replication-...)')
    proto_path = PKG / 'protocol.json'
    protocol = json.loads(proto_path.read_text(encoding='utf-8')) if proto_path.exists() else None
    if protocol is not None and any(k not in protocol for k in metrics.PROTOCOL_KEYS):
        print(json.dumps({'warning': 'protocol.json lacks keys; run is EXPLORATORY', 'missing':
                          [k for k in metrics.PROTOCOL_KEYS if k not in protocol]}), flush=True)
    (out / 'protocol_used.json').write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding='utf-8')
    tracemalloc.start()
    seeds = [int(x) for x in a.seeds.split(',')]
    sem_seed = int(hashlib.sha256(f'{a.label}-{seeds[0]}'.encode()).hexdigest()[:8], 16)
    sem = semantic_check(20, seed=sem_seed, root=out / 'semantics')
    (out / 'semantics.json').write_text(json.dumps(sem, default=str, indent=1), encoding='utf-8')
    checks = {'label': a.label, 'semantics_ok': sem['ok'], 'semantics_seed': sem_seed,
              'semantics_cells': sem['cells'], 'semantics_mismatch': sem['n_mismatch'],
              'tests_passed': None if a.skip_tests else run_tests(out, 'not learning'),
              'learner_tests_passed': None if a.skip_tests else run_tests(out, 'learning'),
              'unreachable': 0}
    conds = a.conditions.split(',')
    records, learn_costs, sizes = [], {}, {}
    write_jsonl(out / 'records.jsonl', [])
    for i, seed in enumerate(seeds):
        t0 = time.perf_counter()
        exps = explore(seed, a.steps, out / 'explore' / f's{seed}')
        write_jsonl(out / 'explore' / f'experiences_s{seed}.jsonl', [e.to_json() for e in exps])
        cs = conds + (['ORACLE'] if i == 0 else [])
        recs, lc, sz = evaluate(a.split, seed, exps, cs, a.tasks, out / f'eval_s{seed}', a.adapt, checks)
        write_jsonl(out / 'records.jsonl', recs, append=True)
        records += recs
        learn_costs[seed], sizes[seed] = lc, sz
        print(json.dumps({'seed': seed, 'explore_steps': len(exps), 'explore_successes': sum(e.succeeded for e in exps),
                          'seconds': round(time.perf_counter() - t0, 1)}), flush=True)
    summary = metrics.summarize(records, protocol, checks, learn_costs, env_info(a, seeds), sizes)
    (out / 'metrics.json').write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    (out / 'REPORT.md').write_text(metrics.report(summary), encoding='utf-8')
    print(json.dumps({'verdict': summary['verdict'], 'secondary': metrics.secondary(summary, protocol), 'checks': checks,
                      'completion': {c: round(v['completion'], 3) for c, v in summary['conditions'].items()}}))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='atanor_os')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('semantics')
    s.add_argument('--k', type=int, default=20, help='required checks per (tool, outcome) cell')
    s.add_argument('--seed', type=int, default=7)
    s.add_argument('--out', default=None)
    e = sub.add_parser('explore')
    e.add_argument('--seed', type=int, required=True)
    e.add_argument('--steps', type=int, default=300)
    e.add_argument('--out', required=True)
    for name in ('evaluate', 'pilot'):
        p = sub.add_parser(name)
        p.add_argument('--split', default='dev')
        p.add_argument('--tasks', type=int, default=20)
        p.add_argument('--conditions', default='A,B,C,D')
        p.add_argument('--out', required=True)
        p.add_argument('--adapt', action='store_true')
        if name == 'evaluate':
            p.add_argument('--seed', type=int, required=True)
            p.add_argument('--experiences', required=True)
            p.set_defaults(steps=None)
        else:
            p.add_argument('--seeds', default='1,2,3,4,5')
            p.add_argument('--steps', type=int, default=300)
            p.add_argument('--skip-tests', action='store_true', help='replication/cost run without the spec tests')
            p.add_argument('--label', default='pre-registered', help="'pre-registered' or 'replication-<host>'")
    a = ap.parse_args(argv)
    {'semantics': cmd_semantics, 'explore': cmd_explore, 'evaluate': cmd_evaluate, 'pilot': cmd_pilot}[a.cmd](a)
