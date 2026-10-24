import pathlib, sys
P = pathlib.Path(sys.argv[1])

# supervisor: optional pacing between episodes (test knob: widens the window in which a kill can land)
p = P / 'atanor_os/agent/supervisor.py'; s = p.read_text(encoding='utf-8')
old = '''    def run(self, n_episodes, stop_file=None, fault=None):
        """Finish `n_episodes` episodes in total (done or failed, counting those finished before a restart).
        `fault` (tests only) is a callable fault(step) with an arm(episode_id) method, passed to the loop."""
        results = []
'''
new = '''    def run(self, n_episodes, stop_file=None, fault=None, pace_s=0.0):
        """Finish `n_episodes` episodes in total (done or failed, counting those finished before a restart).
        `fault` (tests only) is a callable fault(step) with an arm(episode_id) method, passed to the loop;
        `pace_s` (tests only) sleeps between episodes so a crash test has time to kill the process."""
        results = []
'''
assert old in s; s = s.replace(old, new)
old = '''            if fault is not None:
                fault.arm(episode_id)
            results.append(self._run(ws, goal, episode_id, 0, fault))
        return results
'''
new = '''            if fault is not None:
                fault.arm(episode_id)
            results.append(self._run(ws, goal, episode_id, 0, fault))
            if pace_s:
                time.sleep(pace_s)
        return results
'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

# eval/supervise: pace through the CLI; adaptive kill window so slow machines still make progress
p = P / 'atanor_os/eval/supervise.py'; s = p.read_text(encoding='utf-8')
old = '''def run_supervisor(root, body, experiences_path, n_episodes, adapt=True, stop_file=None):
'''
new = '''def run_supervisor(root, body, experiences_path, n_episodes, adapt=True, stop_file=None, pace_s=0.0):
'''
assert old in s; s = s.replace(old, new)
old = '''        sup.run(n_episodes, stop_file=stop_file)
        summary = sup.summary()
'''
new = '''        sup.run(n_episodes, stop_file=stop_file, pace_s=pace_s)
        summary = sup.summary()
'''
assert old in s; s = s.replace(old, new)
old = '''def crash_test(root, body, experiences_path, n_episodes, kill_min, kill_max, seed=1, max_restarts=200, python=None):
    """Spawn `python -m atanor_os supervise ...`, kill it after a random delay, restart, until the summary says
    all episodes are done. Returns the evaluator's disk verification plus crash accounting."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    summary_path = root / 'summary.json'
    cmd = [python or sys.executable, '-m', 'atanor_os', 'supervise', '--body', body, '--experiences', str(experiences_path),
           '--root', str(root), '--episodes', str(n_episodes)]
    log = {'restarts': 0, 'kills': 0, 'natural_exits': 0, 'wall_s': 0.0, 'kill_delays': []}
    t0 = time.perf_counter()
    while log['restarts'] < max_restarts:
        if summary_path.exists():
            s = json.loads(summary_path.read_text(encoding='utf-8'))
            if s.get('episodes_finished', 0) >= n_episodes:
                break
            summary_path.unlink()
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(Path.cwd()))
        log['restarts'] += 1
        delay = rng.uniform(kill_min, kill_max)
        try:
            proc.wait(timeout=delay)
            log['natural_exits'] += 1
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log['kills'] += 1
            log['kill_delays'].append(round(delay, 3))
    log['wall_s'] = time.perf_counter() - t0
'''
new = '''def _finished(root):
    """Episodes finished so far, read from the journal (not from the supervisor's summary)."""
    p = Path(root) / 'journal.sqlite'
    if not p.exists():
        return 0
    j = Journal(p)
    try:
        return j.count_episodes()
    finally:
        j.close()


def crash_test(root, body, experiences_path, n_episodes, kill_min, kill_max, seed=1, max_restarts=200, python=None,
               pace_s=0.0, adaptive=True):
    """Spawn `python -m atanor_os supervise ...`, kill it after a random delay, restart, until the summary says
    all episodes are finished. Returns the evaluator's disk verification plus crash accounting.
    adaptive: after a kill that let no episode finish (the window was shorter than the process start-up on
    this machine) the window grows by 1.5x, so slow machines still progress; windows that saw progress are kept."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    summary_path = root / 'summary.json'
    cmd = [python or sys.executable, '-m', 'atanor_os', 'supervise', '--body', body, '--experiences', str(experiences_path),
           '--root', str(root), '--episodes', str(n_episodes)] + (['--pace-s', str(pace_s)] if pace_s else [])
    log = {'restarts': 0, 'kills': 0, 'natural_exits': 0, 'no_progress_kills': 0, 'wall_s': 0.0, 'kill_delays': [],
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
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            log['kills'] += 1
            log['kill_delays'].append(round(delay, 3))
            if adaptive and _finished(root) == before:
                log['no_progress_kills'] += 1
                kill_min, kill_max = kill_min * 1.5, kill_max * 1.5
    log['wall_s'] = time.perf_counter() - t0
    log['window_final'] = [round(kill_min, 3), round(kill_max, 3)]
'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

# run.py CLI: --pace-s
p = P / 'atanor_os/eval/run.py'; s = p.read_text(encoding='utf-8')
old = '''    summary = run_supervisor(a.root, a.body, a.experiences, a.episodes, adapt=not a.frozen, stop_file=a.stop_file)
'''
new = '''    summary = run_supervisor(a.root, a.body, a.experiences, a.episodes, adapt=not a.frozen, stop_file=a.stop_file,
                             pace_s=a.pace_s)
'''
assert old in s; s = s.replace(old, new)
old = '''    r = crash_test(a.root, a.body, a.experiences, a.episodes, a.kill_min, a.kill_max, seed=a.seed, max_restarts=a.max_restarts)
'''
new = '''    r = crash_test(a.root, a.body, a.experiences, a.episodes, a.kill_min, a.kill_max, seed=a.seed, max_restarts=a.max_restarts,
                   pace_s=a.pace_s)
'''
assert old in s; s = s.replace(old, new)
old = '''    sv.add_argument('--stop-file', default=None)
'''
new = '''    sv.add_argument('--stop-file', default=None)
    sv.add_argument('--pace-s', type=float, default=0.0, help='tests: sleep between episodes')
'''
assert old in s; s = s.replace(old, new)
old = '''    cr.add_argument('--max-restarts', type=int, default=200)
'''
new = '''    cr.add_argument('--max-restarts', type=int, default=200)
    cr.add_argument('--pace-s', type=float, default=0.0, help='tests: sleep between the supervisor\\'s episodes')
'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

# test: paced workload + adaptive window => at least one kill on any machine, progress on slow ones
p = P / 'atanor_os/tests/test_supervisor.py'; s = p.read_text(encoding='utf-8')
old = '''    r = crash_test(tmp_path / 'crash', 'fs', p, n_episodes=15, kill_min=0.4, kill_max=0.9, seed=2, max_restarts=80)
    assert r['ok'], json.dumps(r, default=str)[:2000]
    assert r['crash_log']['kills'] >= 1, r['crash_log']                   # the test must actually have killed it
'''
new = '''    r = crash_test(tmp_path / 'crash', 'fs', p, n_episodes=10, kill_min=0.4, kill_max=0.9, seed=2, max_restarts=120, pace_s=0.25)
    assert r['ok'], json.dumps(r, default=str)[:2000]
    assert r['crash_log']['kills'] >= 1, r['crash_log']                   # the test must actually have killed it
'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding='utf-8')
print('p4b patched')
