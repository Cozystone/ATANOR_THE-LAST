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

from ..agent.bootstrap import VIEW_DOCS
from ..agent.loop import run_episode
from ..agent.models import FS_SPEC, CouncilModel, DocModel, RetrievalModel, RuleModel
from ..agent.rule_learner import LEARNER_VERSION
from ..agent.skills import SkillModel
from ..core.journal import Journal
from ..core.types import Experience
from ..world.fs_world import ENV_VERSION
from ..world.view_world import TOOLS as VIEW_TOOLS
from . import metrics
from .explore import POLICIES, explore, fs_block
from .generator import BUDGET, make_task
from .oracle import TrueModel, fs_sem_block, reachable, rule_agreement, semantic_check, true_pre
from .view_tasks import ViewTrueModel, make_view_task, view_block, view_sem_block, view_true_pre

PKG = Path(__file__).resolve().parents[1]
CONDITIONS = {'A': DocModel, 'B': RetrievalModel, 'C': RuleModel, 'D': CouncilModel,
              'CT': RuleModel, 'E': SkillModel}
TRAIN_TASKS = 20           # goal-directed training episodes for CT/E (train split, indices 100..119)
TRAIN_CONDS = ('CT', 'E')
BODIES = {
    'fs':   {'make_task': make_task, 'block': fs_block, 'sem_block': fs_sem_block, 'oracle': TrueModel,
             'pre': true_pre, 'spec': FS_SPEC},
    'view': {'make_task': make_view_task, 'block': view_block, 'sem_block': view_sem_block, 'oracle': ViewTrueModel,
             'pre': view_true_pre, 'spec': {'tools': VIEW_TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}},
}


def write_jsonl(path, rows, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a' if append else 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + '\n')


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def source_identity():
    """Digest of every .py under atanor_os plus git state, so a result names the code that produced it."""
    files = sorted(p for p in PKG.rglob('*.py') if not {'runs', 'results'} & set(p.relative_to(PKG).parts))
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(PKG).as_posix().encode())
        h.update(p.read_bytes())
    ident = {'source_sha256': h.hexdigest()[:16], 'source_files': len(files)}
    try:
        head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                              cwd=str(PKG.parent), timeout=20)
        if head.returncode != 0:
            ident['git'] = 'not a repository (snapshot copy)'
            return ident
        ident['git_head'] = head.stdout.strip()
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


def build_model(cond, experiences, body='fs'):
    t0 = time.perf_counter()
    B = BODIES[body]
    m = B['oracle']() if cond == 'ORACLE' else CONDITIONS[cond](experiences, spec=B['spec'])
    return m, time.perf_counter() - t0


def train_phase(seed, experiences, out, body='fs'):
    """Goal-directed training episodes (train split) acted by C's frozen rules. Shared by CT and E:
    returns the experiences gathered, the successful action traces, and the cost of the phase."""
    t0 = time.perf_counter()
    actor = RuleModel(experiences, spec=BODIES[body]['spec'])
    journal = Journal(out / 'journal_train.sqlite')
    traces, done = [], 0
    for i in range(TRAIN_TASKS):
        ws, goal, _ = BODIES[body]['make_task'](100 + i, 'train', out / 'ws_train' / f't{i}')
        rec = run_episode(ws, goal, actor, journal, f'train-s{seed}-t{i}')
        if goal.satisfied(ws.observe(goal.universe)):
            done += 1
            traces.append([(s['tool'], tuple(s['args'])) for s in rec['steps'] if s['ok']])
    rows = [json.loads(r[0]) for r in journal.db.execute('SELECT data FROM experiences')]
    journal.close()
    train_exps = [Experience.from_json(j) for j in rows]
    return train_exps, traces, {'episodes': TRAIN_TASKS, 'completed': done, 'experiences': len(train_exps),
                                'wall_s': time.perf_counter() - t0}


def evaluate(split, seed, experiences, conditions, n_tasks, out, adapt=False, checks=None, body='fs'):
    out.mkdir(parents=True, exist_ok=True)
    records, learn, sizes, reach_cache = [], {}, {}, {}
    B = BODIES[body]
    make = B['make_task']
    oracle = B['oracle']
    train = None
    for cond in conditions:
        journal = Journal(out / f'journal_{cond}.sqlite')
        exps = experiences
        if cond in TRAIN_CONDS:
            if train is None:
                train = train_phase(seed, experiences, out, body)
                (out / 'train_phase.json').write_text(json.dumps(train[2], indent=1), encoding='utf-8')
            exps = list(experiences) + train[0]
        base, build_s = build_model(cond, exps, body)
        learn[cond] = {'build_s': build_s}
        if cond in TRAIN_CONDS:
            learn[cond]['train_phase'] = train[2]
        if cond == 'E':
            t0 = time.perf_counter()
            macros = base.learn_traces(train[1])
            learn[cond]['macros'] = len(macros)
            learn[cond]['macro_extraction_s'] = time.perf_counter() - t0
        (out / f'model_{cond}.json').write_text(json.dumps(base.describe(), default=str, indent=1), encoding='utf-8')
        agree = rule_agreement(base, k=20, seed=1000 + seed, root=out / 'agree' / cond, block=B['sem_block'], pre_fn=B['pre'])
        learn[cond]['agreement'] = agree                      # what the frozen model got right, independent of tasks
        (out / f'agreement_{cond}.json').write_text(json.dumps(agree, indent=1), encoding='utf-8')
        for t in range(n_tasks):
            ws, goal, meta = make(t, split, out / 'ws' / f'{cond}_{t}')
            initial = ws.observe(goal.universe)
            work = [l for l in goal.must if not l.holds(initial)]
            if t not in reach_cache:
                reach_cache[t] = reachable(ws, goal, model=oracle())
                if reach_cache[t] is None and checks is not None:
                    checks['unreachable'] = checks.get('unreachable', 0) + 1
            model = copy.deepcopy(base) if adapt else base
            if hasattr(model, 'reset_stats'):
                model.reset_stats()
            if tracemalloc.is_tracing():
                tracemalloc.reset_peak()
            rec = run_episode(ws, goal, model, journal, f'{split}-s{seed}-{cond}-t{t}', adapt=adapt)
            rec.update(condition=cond, task=t, template=meta['template'], target=meta['target'], seed=seed, split=split,
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
            'tasks': a.tasks, 'seeds': seeds, 'split': a.split, 'adapt': a.adapt,
            'policy': getattr(a, 'policy', None), 'body': getattr(a, 'body', 'fs'),
            'learner_version': LEARNER_VERSION, **source_identity()}


def cmd_compare(a):
    if a.metric == 'agreement':
        print(json.dumps(compare_agreement(a.a, a.b or a.a, a.cond), indent=1, default=str))
        return
    _cmd_compare(a)


def _cmd_compare(a):
    """Paired comparison by (seed, task): one condition across two runs (e.g. exploration policies), or two
    conditions (--cond-b) inside the same or another run. Always reports strict completion; --metric adds a
    per-episode quantity (plan_predicted, actions, noops, wall_s) as a ratio a/b."""
    cond_b = a.cond_b or a.cond
    ra = [r for r in read_jsonl(Path(a.a) / 'records.jsonl') if r['condition'] == a.cond]
    rb = [r for r in read_jsonl(Path(a.b or a.a) / 'records.jsonl') if r['condition'] == cond_b]
    kb = {(r['seed'], r['task']): r for r in rb}
    pairs = [(r, kb[(r['seed'], r['task'])]) for r in ra if (r['seed'], r['task']) in kb]
    d = [metrics.strict(x) - metrics.strict(y) for x, y in pairs]
    seeds = sorted({x['seed'] for x, _ in pairs})
    per_seed = {s: 100 * metrics.mean(metrics.strict(x) - metrics.strict(y) for x, y in pairs if x['seed'] == s) for s in seeds}
    extra = {}
    if a.metric:
        m = a.metric
        ratio = lambda ps: metrics.mean(x.get(m, 0) for x, _ in ps) / max(metrics.mean(y.get(m, 0) for _, y in ps), 1e-9)
        extra = {'metric': m, 'mean_a': metrics.mean(x.get(m, 0) for x, _ in pairs),
                 'mean_b': metrics.mean(y.get(m, 0) for _, y in pairs), 'ratio': ratio(pairs),
                 'per_seed_ratio': {s: ratio([pq for pq in pairs if pq[0]['seed'] == s]) for s in seeds}}
    out = {'cond': a.cond, 'cond_b': cond_b, 'a': a.a, 'b': a.b or a.a, 'pairs': len(pairs), **extra,
           'completion_a': metrics.mean(metrics.strict(x) for x, _ in pairs),
           'completion_b': metrics.mean(metrics.strict(y) for _, y in pairs),
           'mean_pp': 100 * metrics.mean(d), 'pairs_pos': sum(v > 0 for v in d), 'pairs_zero': sum(v == 0 for v in d),
           'pairs_neg': sum(v < 0 for v in d), 'seeds_ge': sum(v >= 0 for v in per_seed.values()), 'seeds': len(seeds),
           'per_seed_pp': per_seed,
           'by_template': {t: (100 * metrics.mean(metrics.strict(x) - metrics.strict(y) for x, y in pairs if x['template'] == t))
                           for t in sorted({x['template'] for x, _ in pairs})}}
    print(json.dumps(out, indent=1))


def compare_agreement(run_a, run_b, cond='C'):
    """H4 primary: per seed, the number of tools whose frozen `cond` model agrees exactly with the true
    semantics (rule_agreement 'exact'), run a vs run b, plus strict counts and first-success steps."""
    def per_seed(run):
        m = json.loads((Path(run) / 'metrics.json').read_text(encoding='utf-8'))
        out = {}
        for sd, cs in m['learn_cost_s'].items():
            ag = cs[cond]['agreement']
            out[int(sd)] = {'exact': ag['n_exact'], 'strict': ag.get('n_strict'), 'n_tools': ag['n_tools'],
                            'filled': ag['filled'], 'first_success': cs.get('explore', {}).get('first_success'),
                            'explore_s': cs.get('explore', {}).get('explore_s')}
        return out, m
    a, ma = per_seed(run_a)
    b, mb = per_seed(run_b)
    seeds = sorted(set(a) & set(b))
    d = {s: a[s]['exact'] - b[s]['exact'] for s in seeds}
    xs = lambda r: sum(r[s]['explore_s'] or 0 for s in seeds)
    return {'cond': cond, 'a': str(run_a), 'b': str(run_b), 'seeds': seeds,
            'exact_a': sum(a[s]['exact'] for s in seeds), 'exact_b': sum(b[s]['exact'] for s in seeds),
            'delta_exact': sum(d.values()), 'per_seed_delta': d, 'seeds_lower': sum(v < 0 for v in d.values()),
            'strict_a': sum(a[s]['strict'] or 0 for s in seeds), 'strict_b': sum(b[s]['strict'] or 0 for s in seeds),
            'all_filled': all(a[s]['filled'] and b[s]['filled'] for s in seeds),
            'explore_cost_ratio': xs(a) / max(xs(b), 1e-9),
            'completion_a': ma['conditions'][cond]['completion'], 'completion_b': mb['conditions'][cond]['completion'],
            'verdict_a': ma['verdict'], 'verdict_b': mb['verdict'],
            'first_success_a': {s: a[s]['first_success'] for s in seeds}, 'first_success_b': {s: b[s]['first_success'] for s in seeds}}


def run_tests(out, marks):
    """pytest over the package tests selected by a marker expression (markers: learning, timing, fs, view)."""
    r = subprocess.run([sys.executable, '-m', 'pytest', str(PKG / 'tests'), '-q', '-p', 'no:cacheprovider', '-m', marks],
                       capture_output=True, text=True, cwd=str(PKG.parent))
    (out / f"tests_{marks.replace(' ', '_')}.txt").write_text(r.stdout + r.stderr, encoding='utf-8')
    return r.returncode == 0


def validity_gate(body):
    """The tests a pre-registered run of `body` must pass: everything except learner-performance assertions,
    wall-clock dependent process tests and the other bodies' specific tests."""
    return 'not learning and not timing' + ''.join(f' and not {b}' for b in BODIES if b != body)


def protocol_mismatch(protocol, a, seeds):
    """Frozen design parameters that the executed run does not match (each one invalidates the run)."""
    if protocol is None:
        return []
    run = {'split': a.split, 'explore_steps': a.steps, 'tasks': a.tasks, 'policy': a.policy, 'body': a.body,
           'seeds': seeds, 'budget': BUDGET, 'train_tasks': TRAIN_TASKS}
    out = [{'field': k, 'protocol': protocol[k], 'run': v} for k, v in run.items() if k in protocol and protocol[k] != v]
    if 'conditions_list' in protocol and sorted(protocol['conditions_list']) != sorted(a.conditions.split(',')):
        out.append({'field': 'conditions', 'protocol': protocol['conditions_list'], 'run': a.conditions.split(',')})
    return out


def _sem(a, k, seed, root):
    B = BODIES[a.body]
    return semantic_check(k, seed=seed, root=root, block=B['sem_block'], model=B['oracle'](), pre_fn=B['pre'])


def cmd_semantics(a):
    r = _sem(a, a.k, a.seed, a.out)
    print(json.dumps(r, default=str))
    sys.exit(0 if r['ok'] else 1)


def cmd_explore(a):
    exps = explore(a.seed, a.steps, Path(a.out) / 'ws', policy=a.policy, block=BODIES[a.body]['block'],
                   type_attrs=BODIES[a.body]['spec'].get('type_attrs', ('kind',)))
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
    checks = {'unreachable': 0, 'label': 'exploratory', 'body': a.body}
    records, learn, sizes = evaluate(a.split, a.seed, exps, a.conditions.split(','), a.tasks, out, a.adapt, checks, a.body)
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
    proto_path = Path(a.protocol) if a.protocol else PKG / ('protocol.json' if a.body == 'fs' else f'protocol_{a.body}.json')
    protocol = json.loads(proto_path.read_text(encoding='utf-8')) if proto_path.exists() else None
    ident0 = source_identity()                                   # the code that runs; compared again at the end
    mismatch = protocol_mismatch(protocol, a, [int(x) for x in a.seeds.split(',')])
    if mismatch:
        print(json.dumps({'protocol_mismatch': mismatch, 'note': 'run will be INVALID'}, default=str), flush=True)
    if protocol is not None and any(k not in protocol for k in metrics.PROTOCOL_KEYS):
        print(json.dumps({'warning': 'protocol.json lacks keys; run is EXPLORATORY', 'missing':
                          [k for k in metrics.PROTOCOL_KEYS if k not in protocol]}), flush=True)
    (out / 'protocol_used.json').write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding='utf-8')
    tracemalloc.start()
    seeds = [int(x) for x in a.seeds.split(',')]
    sem_seed = int(hashlib.sha256(f'{a.label}-{seeds[0]}'.encode()).hexdigest()[:8], 16)
    sem = _sem(a, 20, sem_seed, out / 'semantics')
    (out / 'semantics.json').write_text(json.dumps(sem, default=str, indent=1), encoding='utf-8')
    checks = {'label': a.label, 'policy': a.policy, 'body': a.body, 'semantics_ok': sem['ok'], 'semantics_seed': sem_seed,
              'semantics_cells': sem['cells'], 'semantics_mismatch': sem['n_mismatch'],
              'tests_passed': None if a.skip_tests else run_tests(out, validity_gate(a.body)),
              'tests_gate': validity_gate(a.body),
              'learner_tests_passed': None if a.skip_tests else run_tests(out, 'learning'),
              'protocol_mismatch': mismatch, 'unreachable': 0}
    conds = a.conditions.split(',')
    records, learn_costs, sizes = [], {}, {}
    write_jsonl(out / 'records.jsonl', [])
    for i, seed in enumerate(seeds):
        t0 = time.perf_counter()
        t_x = time.perf_counter()
        exps = explore(seed, a.steps, out / 'explore' / f's{seed}', policy=a.policy, block=BODIES[a.body]['block'],
                       type_attrs=BODIES[a.body]['spec'].get('type_attrs', ('kind',)))
        explore_cost = {'explore_s': time.perf_counter() - t_x, **getattr(explore, 'last_stats', {})}
        write_jsonl(out / 'explore' / f'experiences_s{seed}.jsonl', [e.to_json() for e in exps])
        cs = conds + (['ORACLE'] if i == 0 else [])
        recs, lc, sz = evaluate(a.split, seed, exps, cs, a.tasks, out / f'eval_s{seed}', a.adapt, checks, a.body)
        write_jsonl(out / 'records.jsonl', recs, append=True)
        records += recs
        lc['explore'] = explore_cost
        learn_costs[seed], sizes[seed] = lc, sz
        print(json.dumps({'seed': seed, 'explore_steps': len(exps), 'explore_successes': sum(e.succeeded for e in exps),
                          'seconds': round(time.perf_counter() - t0, 1)}), flush=True)
    env = env_info(a, seeds)
    env['source_sha256_at_start'] = ident0['source_sha256']
    checks['source_changed_during_run'] = env['source_sha256'] != ident0['source_sha256']
    checks['protocol_file'] = str(proto_path)
    summary = metrics.summarize(records, protocol, checks, learn_costs, env, sizes)
    (out / 'metrics.json').write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    (out / 'REPORT.md').write_text(metrics.report(summary), encoding='utf-8')
    print(json.dumps({'verdict': summary['verdict'], 'secondary': metrics.secondary(summary, protocol), 'checks': checks,
                      'completion': {c: round(v['completion'], 3) for c, v in summary['conditions'].items()}}))


def cmd_supervise(a):
    from .supervise import run_supervisor
    summary = run_supervisor(a.root, a.body, a.experiences, a.episodes, adapt=not a.frozen, stop_file=a.stop_file,
                             pace_s=a.pace_s)
    print(json.dumps(summary, default=str))


def cmd_crash(a):
    from .supervise import crash_test
    r = crash_test(a.root, a.body, a.experiences, a.episodes, a.kill_min, a.kill_max, seed=a.seed, max_restarts=a.max_restarts,
                   pace_s=a.pace_s)
    (Path(a.root) / 'crash_report.json').write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
    print(json.dumps({'ok': r['ok'], 'crash_log': r['crash_log'], 'verify': r['verify']}, default=str))


def cmd_p6(a):
    from . import p6
    if a.cmd == 'p6-train':
        log = p6.train(a.out, n_extra=a.n_extra, reading_epochs=a.reading_epochs)
        print(json.dumps({k: log[k] for k in ('lexicon_epochs', 'teacher_calls', 'web')}, default=str))
    elif a.cmd == 'p6-dev':
        print(json.dumps(p6.dev(a.state, a.out), default=str)[:4000])
    else:
        proto = json.loads(Path(a.protocol).read_text(encoding='utf-8'))
        r = p6.evaluate(a.state, a.sealed, a.commit, a.out, protocol=proto.get('decision_values', {}))
        print(json.dumps({'verdict': r['verdict'], 'summary': r['summary'], 'checks': r['checks']}, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='atanor_os')
    sub = ap.add_subparsers(dest='cmd', required=True)
    t6 = sub.add_parser('p6-train')
    t6.add_argument('--out', required=True)
    t6.add_argument('--n-extra', type=int, default=60)
    t6.add_argument('--reading-epochs', type=int, default=2)
    d6 = sub.add_parser('p6-dev')
    d6.add_argument('--state', required=True)
    d6.add_argument('--out', required=True)
    e6 = sub.add_parser('p6-eval')
    for k in ('--state', '--sealed', '--commit', '--out', '--protocol'):
        e6.add_argument(k, required=True)
    sv = sub.add_parser('supervise', help='P4: run a stream of episodes under one durable, resumable journal')
    sv.add_argument('--root', required=True)
    sv.add_argument('--body', default='fs', choices=tuple(BODIES))
    sv.add_argument('--experiences', required=True, help='frozen exploration log (jsonl) the model starts from')
    sv.add_argument('--episodes', type=int, default=20)
    sv.add_argument('--frozen', action='store_true', help='no online learning during the stream')
    sv.add_argument('--stop-file', default=None)
    sv.add_argument('--pace-s', type=float, default=0.0, help='tests: sleep between episodes')
    sv.set_defaults(func=cmd_supervise)
    cr = sub.add_parser('crash', help='P4: kill/restart the supervisor at random moments and verify from disk')
    cr.add_argument('--root', required=True)
    cr.add_argument('--body', default='fs', choices=tuple(BODIES))
    cr.add_argument('--experiences', required=True)
    cr.add_argument('--episodes', type=int, default=10)
    cr.add_argument('--kill-min', type=float, default=0.5)
    cr.add_argument('--kill-max', type=float, default=3.0)
    cr.add_argument('--seed', type=int, default=1)
    cr.add_argument('--max-restarts', type=int, default=200)
    cr.add_argument('--pace-s', type=float, default=0.0, help='tests: sleep between the supervisor\'s episodes')
    cr.set_defaults(func=cmd_crash)
    s = sub.add_parser('semantics')
    s.add_argument('--k', type=int, default=20, help='required checks per (tool, outcome) cell')
    s.add_argument('--seed', type=int, default=7)
    s.add_argument('--out', default=None)
    s.add_argument('--body', default='fs', choices=tuple(BODIES))
    e = sub.add_parser('explore')
    e.add_argument('--seed', type=int, required=True)
    e.add_argument('--steps', type=int, default=300)
    e.add_argument('--out', required=True)
    e.add_argument('--policy', default='novelty', choices=POLICIES)
    e.add_argument('--body', default='fs', choices=tuple(BODIES))
    c = sub.add_parser('compare')
    c.add_argument('--a', required=True)
    c.add_argument('--b', default=None, help='second run (default: same run as --a)')
    c.add_argument('--cond', default='C')
    c.add_argument('--cond-b', default=None, help='condition taken from --b (default: --cond)')
    c.add_argument('--metric', default=None, choices=(None, 'plan_predicted', 'actions', 'noops', 'wall_s', 'plan_expanded', 'agreement'))
    for name in ('evaluate', 'pilot'):
        p = sub.add_parser(name)
        p.add_argument('--split', default=None if name == 'pilot' else 'dev', required=(name == 'pilot'))
        p.add_argument('--tasks', type=int, default=20)
        p.add_argument('--conditions', default='A,B,C,D')
        p.add_argument('--out', required=True)
        p.add_argument('--adapt', action='store_true')
        p.add_argument('--body', default='fs', choices=tuple(BODIES))
        if name == 'evaluate':
            p.add_argument('--seed', type=int, required=True)
            p.add_argument('--experiences', required=True)
            p.set_defaults(steps=None)
        else:
            p.add_argument('--seeds', default='1,2,3,4,5')
            p.add_argument('--steps', type=int, default=300)
            p.add_argument('--skip-tests', action='store_true', help='replication/cost run without the spec tests')
            p.add_argument('--label', default='pre-registered', help="'pre-registered' or 'replication-<host>'")
            p.add_argument('--protocol', default=None, help='frozen protocol file (default: protocol.json / protocol_<body>.json)')
            p.add_argument('--policy', default='novelty', choices=POLICIES)
    a = ap.parse_args(argv)
    {'semantics': cmd_semantics, 'explore': cmd_explore, 'evaluate': cmd_evaluate, 'pilot': cmd_pilot,
     'compare': cmd_compare, 'supervise': cmd_supervise, 'crash': cmd_crash, 'p6-train': cmd_p6,
     'p6-dev': cmd_p6, 'p6-eval': cmd_p6}[a.cmd](a)
