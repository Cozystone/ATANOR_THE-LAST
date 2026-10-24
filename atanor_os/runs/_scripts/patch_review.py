"""Fixes for the surviving findings of magi-review-02 (see DECISIONS.md)."""
import pathlib, re, sys
P = pathlib.Path(sys.argv[1])


def patch(rel, pairs):
    p = P / rel
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: anchor not found:\n{old[:200]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


# ---------------- F3/F4: pytest markers, body-aware validity gate, protocol parameter binding ----------------
patch('atanor_os/tests/conftest.py', [(
    "if str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n",
    "if str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\n\n"
    "def pytest_configure(config):\n"
    "    for m in ('learning: learner-performance assertion (not part of a run\\'s validity gate)',\n"
    "              'timing: wall-clock dependent process test (not part of a run\\'s validity gate)',\n"
    "              'fs: filesystem-body specific', 'view: view-body specific'):\n"
    "        config.addinivalue_line('markers', m)\n")])


def mark(rel, marks_by_test, file_marks=()):
    p = P / rel
    s = p.read_text(encoding='utf-8')
    if 'import pytest' not in s:
        s = s.replace('\n\n', '\n\nimport pytest\n\n', 1) if s.startswith('"""') else 'import pytest\n' + s
    for name in re.findall(r'^def (test_\w+)\(', s, flags=re.M):
        ms = list(file_marks) + list(marks_by_test.get(name, ()))
        if ms:
            s = s.replace(f'\ndef {name}(', '\n' + ''.join(f'@pytest.mark.{m}\n' for m in ms) + f'def {name}(', 1)
    p.write_text(s, encoding='utf-8')


mark('atanor_os/tests/test_learning.py', {}, file_marks=('learning', 'fs'))
mark('atanor_os/tests/test_view.py', {'test_same_learner_induces_view_rules_from_exploration': ('learning',)}, file_marks=('view',))
for f in ('test_world.py', 'test_oracle.py', 'test_evaluator.py', 'test_skills.py'):
    mark(f'atanor_os/tests/{f}', {}, file_marks=('fs',))
mark('atanor_os/tests/test_supervisor.py', {'test_process_level_crash_test': ('timing',), 'test_supervisor_runs_the_view_body': ('view',),
                                           'test_supervisor_reconciles_and_resumes_after_crash': ('fs',)})

patch('atanor_os/eval/run.py', [
    ('''def run_tests(out, expr):
    r = subprocess.run([sys.executable, '-m', 'pytest', str(PKG / 'tests'), '-q', '-p', 'no:cacheprovider', '-k', expr],
                       capture_output=True, text=True, cwd=str(PKG.parent))
    (out / f"tests_{expr.replace(' ', '_')}.txt").write_text(r.stdout + r.stderr, encoding='utf-8')
    return r.returncode == 0
''', '''def run_tests(out, marks):
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
'''),
    ('''    ident0 = source_identity()                                   # the code that runs; compared again at the end
''', '''    ident0 = source_identity()                                   # the code that runs; compared again at the end
    mismatch = protocol_mismatch(protocol, a, [int(x) for x in a.seeds.split(',')])
    if mismatch:
        print(json.dumps({'protocol_mismatch': mismatch, 'note': 'run will be INVALID'}, default=str), flush=True)
'''),
    ('''              'tests_passed': None if a.skip_tests else run_tests(out, 'not learning'),
              'learner_tests_passed': None if a.skip_tests else run_tests(out, 'learning'),
              'unreachable': 0}
''', '''              'tests_passed': None if a.skip_tests else run_tests(out, validity_gate(a.body)),
              'tests_gate': validity_gate(a.body),
              'learner_tests_passed': None if a.skip_tests else run_tests(out, 'learning'),
              'protocol_mismatch': mismatch, 'unreachable': 0}
'''),
    ('''        p.add_argument('--split', default='dev')
''', '''        p.add_argument('--split', default=None if name == 'pilot' else 'dev', required=(name == 'pilot'))
'''),
])
patch('atanor_os/eval/metrics.py', [(
    "               or ck.get('source_changed_during_run') is True\n",
    "               or ck.get('source_changed_during_run') is True or bool(ck.get('protocol_mismatch'))\n")])

# ---------------- F2: rule_agreement — near-miss failures, unknown effects, filled requirement ----------------
p = P / 'atanor_os/eval/oracle.py'; s = p.read_text(encoding='utf-8')
old = s[s.index('def rule_agreement('):]
new = '''def rule_agreement(model, k=20, seed=11, root=None, max_blocks=400, block=fs_sem_block, pre_fn=None):
    """A condition's model against the body's real tools on fresh train-distribution situations, stratified like
    `semantic_check` (>= k per (tool, true outcome) cell) plus a best-effort NEAR cell per tool: failing actions
    that differ from a successful action of the same tool in the same state by exactly one argument (the
    precondition near-misses a learner over-generalizes on; type mismatches dominate the plain failure cell).
    Per tool: fp = predicted success where the real tool failed, fn = predicted failure where it succeeded,
    eff = real successes predicted as such whose predicted attributes differ from the real post-state,
    unk = real successes whose prediction left an attribute 'unknown', docs = answers resting on documentation
    alone, near_* = the same restricted to the near cell. Labels: `exact` (the pre-registered v1 criterion:
    cells filled and fp = fn = eff = 0 over the plain cells) and `strict` (exact, unk = 0, near cell filled
    with near_fp = 0). Evaluator-side; never consulted by the agent."""
    from .explore import ALL_CAPS
    pre_fn = pre_fn or true_pre
    rng = random.Random(seed)
    root = Path(root or tempfile.mkdtemp(prefix='atanor_agree_'))
    cells, near_cells, per_tool, block_i = None, {}, {}, 0
    while block_i < max_blocks and (cells is None or min(cells.values()) < k):
        ws, targets = block(rng, root / f'b{block_i}')
        if cells is None:
            cells = {f'{t}:{o}': 0 for t in ws.TOOLS for o in ('success', 'failure')}
            near_cells = {t: 0 for t in ws.TOOLS}
            per_tool = {t: {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'unk': 0, 'docs': 0, 'near_checks': 0, 'near_fp': 0}
                        for t in ws.TOOLS}
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(targets)
            buckets, succ_args = {}, {}
            for tool, args in ws.actions(sorted(pre)):
                ok = pre_fn(pre, tool, args)
                buckets.setdefault(f"{tool}:{'success' if ok else 'failure'}", []).append((tool, args))
                if ok:
                    succ_args.setdefault(tool, []).append(args)
            for tool, sa in succ_args.items():                     # near-miss failures: one argument away from a success
                near = [(t, a) for t, a in buckets.get(f'{tool}:failure', [])
                        if any(sum(x != y for x, y in zip(a, s_)) == 1 for s_ in sa)]
                if near:
                    buckets[f'{tool}:near'] = near
            needy = [c for c in buckets if (near_cells if c.endswith(':near') else cells)[c.split(':')[0] if c.endswith(':near') else c] < k]
            if not needy:
                break
            needy_near = [c for c in needy if c.endswith(':near')]
            cell = rng.choice(needy_near or needy)                  # near cells first while they are available
            tool, args = rng.choice(buckets[cell])
            predicted, status = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            is_near = cell.endswith(':near')
            if is_near:
                near_cells[tool] += 1
                cells[f'{tool}:failure'] += 1                        # a near miss is also a plain failure sample
            else:
                cells[cell] += 1
            pt = per_tool[tool]
            pt['checks'] += 1
            pt['near_checks'] += int(is_near)
            pt['docs'] += int(str(status).endswith('documented'))
            if predicted is not None and not res['ok']:
                pt['fp'] += 1
                pt['near_fp'] += int(is_near)
            elif predicted is None and res['ok']:
                pt['fn'] += 1
            elif res['ok']:
                attrs = [(a, k_) for a in args for k_ in effect_attrs(predicted[a])]
                if any(predicted[a][k_] == 'unknown' for a, k_ in attrs):
                    pt['unk'] += 1
                if not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a, k_ in attrs):
                    pt['eff'] += 1
        block_i += 1
    filled = bool(cells) and min(cells.values()) >= k
    exact = sorted(t for t, v in per_tool.items() if filled and v['checks'] and v['fp'] == v['fn'] == v['eff'] == 0)
    strict = sorted(t for t in exact if per_tool[t]['unk'] == 0 and near_cells.get(t, 0) >= k and per_tool[t]['near_fp'] == 0)
    return {'k': k, 'seed': seed, 'cells': cells or {}, 'near_cells': near_cells, 'per_tool': per_tool,
            'exact_tools': exact, 'n_exact': len(exact), 'strict_tools': strict, 'n_strict': len(strict),
            'n_tools': len(per_tool), 'filled': filled}
'''
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

patch('atanor_os/eval/metrics.py', [
    ('''            tot = {k: sum(v[k] for v in ag['per_tool'].values()) for k in ('checks', 'fp', 'fn', 'eff', 'docs')}
            rows.append((str(sd), c, f"{ag['n_exact']}/{ag['n_tools']}", ' '.join(ag['exact_tools']) or '-', tot))
''', '''            tot = {k: sum(v.get(k, 0) for v in ag['per_tool'].values()) for k in ('checks', 'fp', 'fn', 'eff', 'unk', 'docs', 'near_checks', 'near_fp')}
            tot['filled'] = ag.get('filled')
            tot['strict'] = f"{ag.get('n_strict', '-')}/{ag['n_tools']}"
            rows.append((str(sd), c, f"{ag['n_exact']}/{ag['n_tools']}", ' '.join(ag['exact_tools']) or '-', tot))
'''),
    ('''        L += ['', '## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측)', '',
              '| seed | 조건 | 정확 도구 | 어떤 도구 | 검사 | fp | fn | eff | 설명서 답 |', '|---|---|---:|---|---:|---:|---:|---:|---:|']
        for sd, c_, ne, tools, tot in rows:
            L.append(f"| {sd} | {c_} | {ne} | {tools} | {tot['checks']} | {tot['fp']} | {tot['fn']} | {tot['eff']} | {tot['docs']} |")
''', '''        L += ['', '## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측, unk=효과 미정, near=성공과 인자 하나 차이인 실패)', '',
              '| seed | 조건 | 정확 도구 | 엄격 도구 | 어떤 도구(정확) | 검사 | fp | fn | eff | unk | near 검사 | near fp | 설명서 답 | 셀 충족 |',
              '|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
        for sd, c_, ne, tools, tot in rows:
            L.append(f"| {sd} | {c_} | {ne} | {tot['strict']} | {tools} | {tot['checks']} | {tot['fp']} | {tot['fn']} | {tot['eff']} | {tot['unk']} | "
                     f"{tot['near_checks']} | {tot['near_fp']} | {tot['docs']} | {tot['filled']} |")
'''),
])

# ---------------- F5/F6/F7/F8: supervisor idempotency, atomic verify+experience, journal-wide counters, atomic writes ----------------
patch('atanor_os/core/journal.py', [
    ('''    def begin_episode(self, eid, goal_json, root, meta_json='{}'):
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?)',
                            (eid, goal_json, root, meta_json, 'running', time.time(), None, None))
''', '''    def begin_episode(self, eid, goal_json, root, meta_json='{}', status='running'):
        with self.db:
            self.db.execute('INSERT INTO episodes VALUES(?,?,?,?,?,?,?,?)',
                            (eid, goal_json, root, meta_json, status, time.time(), None, None))

    def start_episode(self, eid, goal_json, root, meta_json='{}'):
        """A 'preparing' episode (row written before its workspace was made) becomes 'running'."""
        with self.db:
            self.db.execute("UPDATE episodes SET goal=?, root=?, meta=?, status='running', started=? WHERE id=?",
                            (goal_json, root, meta_json, time.time(), eid))

    def episodes_with_status(self, status):
        return [dict(zip(('id', 'goal', 'root', 'meta', 'status'), r)) for r in
                self.db.execute('SELECT id, goal, root, meta, status FROM episodes WHERE status=? ORDER BY started', (status,))]

    def delete_episode(self, eid):
        with self.db:
            self.db.execute('DELETE FROM episodes WHERE id=?', (eid,))

    def verify(self, aid, ok, error, exp, episode):
        """Verification and its experience in ONE transaction: a kill cannot leave one without the other."""
        with self.db:
            self.db.execute('UPDATE actions SET status=?, done_at=?, ok=?, error=? WHERE id=?',
                            ('verified', time.time(), int(ok), error, aid))
            self.db.execute('INSERT INTO experiences VALUES(?,?,?)', (exp.id, episode, json.dumps(exp.to_json())))

    def episode_totals(self, eid):
        """Actions really performed for an episode across all its processes, and how many of them failed."""
        r = self.db.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END), 0) FROM actions "
                            "WHERE episode=? AND status IN ('verified', 'reconciled')", (eid,)).fetchone()
        return {'actions_total': r[0], 'noops_total': r[1]}
'''),
])

patch('atanor_os/agent/loop.py', [
    ('''        journal.mark(aid, 'verified', res['ok'], res['error'])
        rec['actions'] += 1
        if not res['ok']:
            rec['noops'] += 1
            avoid.add((tool, args))
        err = res['ok'] != (predicted is not None) or (res['ok'] and any(
            predicted[a][k] not in ('unknown', post[a].get(k)) for a in args for k in effect_attrs(predicted[a])))
        rec['pred_total'] += 1
        rec['pred_errors'] += int(err)
        exp = Experience(aid, tool, tuple(args), state, post, res['ok'], res['blocked'], res['ms'], False, episode_id)
        journal.experience(exp, episode_id)
''', '''        exp = Experience(aid, tool, tuple(args), state, post, res['ok'], res['blocked'], res['ms'], False, episode_id)
        journal.verify(aid, res['ok'], res['error'], exp, episode_id)      # verification + experience, one transaction
        rec['actions'] += 1
        if not res['ok']:
            rec['noops'] += 1
            avoid.add((tool, args))
        err = res['ok'] != (predicted is not None) or (res['ok'] and any(
            predicted[a][k] not in ('unknown', post[a].get(k)) for a in args for k in effect_attrs(predicted[a])))
        rec['pred_total'] += 1
        rec['pred_errors'] += int(err)
'''),
])

patch('atanor_os/agent/supervisor.py', [
    ('''import json
import time
import tracemalloc
from pathlib import Path
''', '''import json
import shutil
import time
import tracemalloc
from pathlib import Path
'''),
    ('''        self.stats = {'started_at': time.time(), 'resumed_episodes': 0, 'reconciled': {'done': 0, 'not_done': 0, 'unknown': 0},
                      'startup_s': None, 'model_rebuild_s': None, 'journal_experiences': 0, 'update_s': 0.0, 'updates': 0}
        t0 = time.perf_counter()
        self._reconcile()
''', '''        self.stats = {'started_at': time.time(), 'resumed_episodes': 0, 'reconciled': {'done': 0, 'not_done': 0, 'unknown': 0},
                      'discarded_preparing': 0, 'startup_s': None, 'model_rebuild_s': None, 'journal_experiences': 0,
                      'update_s': 0.0, 'updates': 0}
        t0 = time.perf_counter()
        self._discard_preparing()
        self._reconcile()
'''),
    ('''    # --- intent vs reality ---
    def _reconcile(self):
''', '''    # --- intent vs reality ---
    def _discard_preparing(self):
        """An episode row is written BEFORE its workspace is made; a kill in between leaves a 'preparing' row
        (no action was ever taken for it). Its half-made workspace is removed and the row deleted, so the
        index is reused and a restart cannot wedge on an existing directory."""
        for ep in self.journal.episodes_with_status('preparing'):
            if ep['root']:
                shutil.rmtree(ep['root'], ignore_errors=True)
            self.journal.delete_episode(ep['id'])
            self.stats['discarded_preparing'] += 1
            self.journal.event('discard_preparing', {'episode': ep['id'], 'root': ep['root']})

    def _reconcile(self):
'''),
    ('''        result = {'episode': episode_id, 'completed': done, 'start_step': start_step, 'actions': rec['actions'],
                  'noops': rec['noops'], 'plan_predicted': rec['plan_predicted'], 'pred_errors': rec['pred_errors'],
                  'abstained': rec['abstained'], 'planner_budget_exceeded': rec['planner_budget_exceeded'],
                  'keep_violated': rec['keep_violated'], 'wall_s': time.perf_counter() - t0, 'cpu_s': rec['cpu_s'],
                  'update_s': self.stats['update_s'] - before, 'resumed': start_step > 0}
        self.journal.finish_episode(episode_id, 'done' if done else 'failed', result)
        with (self.root / 'episodes.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(result) + '\\n')
        return result
''', '''        result = {'episode': episode_id, 'completed': done, 'start_step': start_step, 'actions': rec['actions'],
                  'noops': rec['noops'], 'plan_predicted': rec['plan_predicted'], 'pred_errors': rec['pred_errors'],
                  'abstained': rec['abstained'], 'planner_budget_exceeded': rec['planner_budget_exceeded'],
                  'keep_violated': rec['keep_violated'], 'wall_s': time.perf_counter() - t0, 'cpu_s': rec['cpu_s'],
                  'update_s': self.stats['update_s'] - before, 'resumed': start_step > 0,
                  **self.journal.episode_totals(episode_id)}          # counts across every process that worked on it
        self.journal.finish_episode(episode_id, 'done' if done else 'failed', result)
        with (self.root / 'episodes.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(result) + '\\n')
            f.flush()
        return result
'''),
    ('''            idx = self.journal.count_episodes(any_status=True)
            episode_id = f'sup-{idx}'
            ws, goal, meta = self.task_source(idx, self.root / 'ws' / f'ep{idx}')
            self.journal.begin_episode(episode_id, json.dumps(goal.to_json()), str(ws.root if hasattr(ws, 'root') else ''),
                                       json.dumps(meta, default=str))
''', '''            idx = self.journal.count_episodes(any_status=True)
            episode_id = f'sup-{idx}'
            task_root = self.root / 'ws' / f'ep{idx}'
            self.journal.begin_episode(episode_id, '{}', str(task_root), '{}', status='preparing')   # row first (idempotent restart)
            ws, goal, meta = self.task_source(idx, task_root)
            self.journal.start_episode(episode_id, json.dumps(goal.to_json()), str(ws.root if hasattr(ws, 'root') else ''),
                                       json.dumps(meta, default=str))
'''),
    ('''    def summary(self):
        peak = tracemalloc.get_traced_memory()[1] if tracemalloc.is_tracing() else None
        rows = [json.loads(l) for l in (self.root / 'episodes.jsonl').read_text(encoding='utf-8').splitlines()] \\
            if (self.root / 'episodes.jsonl').exists() else []
        db = self.journal.db
        return {**self.stats, 'episodes_finished': self.journal.count_episodes(),
''', '''    def summary(self):
        """Journal-wide figures (they span every process that worked on this root); this process's own
        counters are under 'this_process'."""
        peak = tracemalloc.get_traced_memory()[1] if tracemalloc.is_tracing() else None
        rows, malformed = [], 0
        if (self.root / 'episodes.jsonl').exists():
            for l in (self.root / 'episodes.jsonl').read_text(encoding='utf-8').splitlines():
                try:
                    rows.append(json.loads(l))
                except ValueError:                                   # a line torn by a kill mid-write
                    malformed += 1
        db = self.journal.db
        reconciled = {'done': 0, 'not_done': 0, 'unknown': 0}
        for (note,) in db.execute("SELECT error FROM actions WHERE status='reconciled'"):
            v = (note or '').split(':')[1] if ':' in (note or '') else 'unknown'
            reconciled[v if v in reconciled else 'unknown'] += 1
        resumes = db.execute("SELECT COUNT(*) FROM events WHERE kind='resume'").fetchone()[0]
        starts = db.execute("SELECT COUNT(*) FROM events WHERE kind='supervisor_start'").fetchone()[0]
        return {'this_process': dict(self.stats), 'reconciled': reconciled, 'resumed_episodes': resumes, 'process_starts': starts,
                'discarded_preparing': db.execute("SELECT COUNT(*) FROM events WHERE kind='discard_preparing'").fetchone()[0],
                'malformed_episode_rows': malformed, 'episodes_finished': self.journal.count_episodes(),
'''),
])

patch('atanor_os/eval/supervise.py', [
    ('''    (Path(root) / 'summary.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    return summary
''', '''    tmp = Path(root) / 'summary.json.tmp'                        # atomic: a kill mid-write leaves no torn summary
    tmp.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    tmp.replace(Path(root) / 'summary.json')
    return summary
'''),
    ('''    log = {'restarts': 0, 'kills': 0, 'natural_exits': 0, 'no_progress_kills': 0, 'wall_s': 0.0, 'kill_delays': [],
           'window_final': [kill_min, kill_max]}
    t0 = time.perf_counter()
    while log['restarts'] < max_restarts:
        if summary_path.exists():
            s = json.loads(summary_path.read_text(encoding='utf-8'))
            if s.get('episodes_finished', 0) >= n_episodes:
                break
            summary_path.unlink()
        before = _finished(root)
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(Path.cwd()))
        log['restarts'] += 1
        delay = rng.uniform(kill_min, kill_max)
        try:
            proc.wait(timeout=delay)
            log['natural_exits'] += 1
''', '''    log = {'restarts': 0, 'kills': 0, 'natural_exits': 0, 'natural_errors': 0, 'no_progress_kills': 0, 'wall_s': 0.0,
           'kill_delays': [], 'window_final': [kill_min, kill_max]}
    t0 = time.perf_counter()
    stderr_log = root / 'supervisor_stderr.log'                  # natural exits with an error stay diagnosable
    while log['restarts'] < max_restarts:
        if summary_path.exists():
            try:
                s = json.loads(summary_path.read_text(encoding='utf-8'))
            except ValueError:
                s = {}
            if s.get('episodes_finished', 0) >= n_episodes:
                break
            summary_path.unlink()
        before = _finished(root)
        with stderr_log.open('ab') as err:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err, cwd=str(Path.cwd()))
        log['restarts'] += 1
        delay = rng.uniform(kill_min, kill_max)
        try:
            proc.wait(timeout=delay)
            log['natural_exits'] += 1
            log['natural_errors'] += int(proc.returncode != 0)
'''),
])

# ---------------- F9: type-grouping attributes declared by the body spec ----------------
patch('atanor_os/agent/rule_learner.py', [
    ('''def _type_key(e):
    out = []
    for a in e.args:
        o = e.pre.get(a)
        out.append((None, None) if o is None else (o.get('kind'), o.get('value')))
    return tuple(out)


def learn_operator(tool, arity, exps):
''', '''def _type_key(e, type_attrs):
    out = []
    for a in e.args:
        o = e.pre.get(a)
        out.append(tuple(None for _ in type_attrs) if o is None else tuple(o.get(t) for t in type_attrs))
    return tuple(out)


def learn_operator(tool, arity, exps, type_attrs=('kind',)):
    """type_attrs: the attributes that name an object's type, declared by the body spec (filesystem: kind;
    view: kind and the value object's name) — provided knowledge, listed in BOOTSTRAP_MANIFEST."""
'''),
    ('''    for e in succ:
        by_type.setdefault(_type_key(e), []).append(e)
''', '''    for e in succ:
        by_type.setdefault(_type_key(e, type_attrs), []).append(e)
'''),
    ('''            same['kinds'] = same['kinds'] if same['kinds'] == g['kinds'] else tuple(
                (k1[0], k1[1] if k1[1] == k2[1] else '*') for k1, k2 in zip(same['kinds'], g['kinds']))
''', '''            same['kinds'] = same['kinds'] if same['kinds'] == g['kinds'] else tuple(
                tuple(x if x == y else '*' for x, y in zip(k1, k2)) for k1, k2 in zip(same['kinds'], g['kinds']))
'''),
])
patch('atanor_os/agent/models.py', [
    ("FS_SPEC = {'tools': TOOLS, 'docs': DOCS}\n", "FS_SPEC = {'tools': TOOLS, 'docs': DOCS, 'type_attrs': ('kind',)}\n"),
    ("            self.ops[t] = learn_operator(t, self.spec['tools'][t], exps) if exps else None\n",
     "            self.ops[t] = learn_operator(t, self.spec['tools'][t], exps, self.spec.get('type_attrs', ('kind',))) if exps else None\n"),
])
patch('atanor_os/eval/run.py', [
    ("             'pre': view_true_pre, 'spec': {'tools': VIEW_TOOLS, 'docs': VIEW_DOCS}},\n",
     "             'pre': view_true_pre, 'spec': {'tools': VIEW_TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}},\n"),
])
p = P / 'atanor_os/tests/test_view.py'; s = p.read_text(encoding='utf-8')
n = s.count("spec={'tools': TOOLS, 'docs': VIEW_DOCS}")
s = s.replace("spec={'tools': TOOLS, 'docs': VIEW_DOCS}", "spec={'tools': TOOLS, 'docs': VIEW_DOCS, 'type_attrs': ('kind', 'value')}")
s = s.replace("    opg = learn_operator('group', 2, exps_g)\n", "    opg = learn_operator('group', 2, exps_g, type_attrs=('kind', 'value'))\n")
p.write_text(s, encoding='utf-8')
print('review fixes patched; view spec replacements:', n)
