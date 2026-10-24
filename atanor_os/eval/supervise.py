"""P4 evaluator side: wire the supervisor to a body's task generator, and the crash test — kill the
supervisor process at random moments, restart it, and verify from disk that every episode it calls done
is done, that no action is left unresolved, and how much the crashes cost."""
import json
import random
import subprocess
import sys
import time
from pathlib import Path

from ..agent.models import RuleModel
from ..agent.supervisor import Supervisor
from ..core.journal import Journal
from ..core.types import Experience, Goal
from ..world.fs_world import Workspace
from ..world.view_world import ViewWorkspace

STREAM_BASE = 1000          # task indices 1000.. of the train split: disjoint from TRAIN_TASKS (100..119) and test


def reopen_fs(root):
    return Workspace(root, create=False)


def reopen_view(root):
    root = Path(root).parent                        # the view task root holds data/ and view/
    return ViewWorkspace(root / 'view', Workspace(root / 'data', create=False), create=False)


def task_stream(body, split='train'):
    from .run import BODIES
    make = BODIES[body]['make_task']

    def source(index, root):
        return make(STREAM_BASE + index, split, root)
    return source


def read_experiences(path):
    return [Experience.from_json(json.loads(l)) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


def run_supervisor(root, body, experiences_path, n_episodes, adapt=True, stop_file=None, pace_s=0.0):
    from .run import BODIES
    import tracemalloc
    tracemalloc.start()
    spec = BODIES[body]['spec']
    base = read_experiences(experiences_path)
    sup = Supervisor(root, lambda exps: RuleModel(exps, spec=spec), base, task_stream(body),
                     reopen_fs if body == 'fs' else reopen_view, adapt=adapt)
    try:
        sup.run(n_episodes, stop_file=stop_file, pace_s=pace_s)
        summary = sup.summary()
    finally:
        sup.close()
    tmp = Path(root) / 'summary.json.tmp'                        # atomic: a kill mid-write leaves no torn summary
    tmp.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    tmp.replace(Path(root) / 'summary.json')
    return summary


def verify_from_disk(root, body):
    """Evaluator's own check of a supervisor root: re-open every episode's workspace and judge its goal."""
    j = Journal(Path(root) / 'journal.sqlite')
    reopen = reopen_fs if body == 'fs' else reopen_view
    rows = j.db.execute('SELECT id, goal, root, status, result FROM episodes').fetchall()
    out = {'episodes': len(rows), 'claimed_done': 0, 'really_done': 0, 'false_done': [], 'failed': 0, 'running': 0,
           'unresolved_actions': len(j.unresolved()), 'action_status': j.counts(), 'duplicate_action_ids': 0}
    for eid, goal_j, wroot, status, result in rows:
        if status == 'running':
            out['running'] += 1
            continue
        goal = Goal.from_json(json.loads(goal_j))
        real = reopen(wroot).observe(goal.universe)
        ok = goal.satisfied(real)
        if status == 'done':
            out['claimed_done'] += 1
            out['really_done'] += int(ok)
            if not ok:
                out['false_done'].append(eid)
        else:
            out['failed'] += 1
    dup = j.db.execute('SELECT COUNT(*) - COUNT(DISTINCT id) FROM actions').fetchone()[0]
    out['duplicate_action_ids'] = dup
    j.close()
    return out


def _finished(root):
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
    log = {'restarts': 0, 'kills': 0, 'natural_exits': 0, 'natural_errors': 0, 'no_progress_kills': 0, 'wall_s': 0.0,
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
    final = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.exists() else None
    verify = verify_from_disk(root, body)
    return {'crash_log': log, 'final_summary': final, 'verify': verify,
            'ok': (final is not None and verify['false_done'] == [] and verify['unresolved_actions'] == 0
                   and verify['duplicate_action_ids'] == 0 and verify['running'] == 0
                   and verify['claimed_done'] + verify['failed'] >= n_episodes)}
