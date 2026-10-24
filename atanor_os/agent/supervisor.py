"""Long-running operator (P4): a stream of goal episodes under one durable journal, built to be killed at
any moment and restarted (charter §7: intent → act → verify, and the record is never assumed to be the
world).

On start the supervisor RECONCILES before anything else: every journal action whose outcome was not
verified ('intended' / 'executed' / 'unknown') is judged against the real, re-observed workspace —
    not_done  the argument objects still look as they did before the action (nothing happened)
    done      they look as the agent predicted (the action happened; only its record was lost)
    unknown   neither (an unpredicted effect or an external change) — nothing is assumed
— then unfinished episodes are resumed from the REAL state, never from the remembered one, and the
model is rebuilt from the base experiences plus everything the journal holds, so what was learned
before the crash is not lost either.

The supervisor owns no task semantics: `task_source(index, root)` (the evaluator, or later a user
instruction) supplies goals, `reopen(root)` re-attaches a body to an existing workspace.
"""
import json
import shutil
import time
import tracemalloc
from pathlib import Path

from ..core.journal import Journal
from ..core.types import Experience, Goal
from .lift import effect_attrs
from .loop import run_episode


def _same(a, b, attrs=None):
    if a is None or b is None:
        return False
    return all(a.get(k) == b.get(k) for k in (attrs or effect_attrs(a)))


def _predicted_match(real, pred):
    return pred is not None and real is not None and all(pred.get(k) in ('unknown', real.get(k)) for k in effect_attrs(pred))


class Supervisor:
    def __init__(self, root, model_factory, base_experiences, task_source, reopen, adapt=True, record_states=True):
        """model_factory(experiences) -> model; base_experiences: the frozen exploration log;
        task_source(index, root) -> (ws, goal, meta); reopen(root) -> ws for a workspace that already exists."""
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal = Journal(self.root / 'journal.sqlite')
        self.task_source, self.reopen = task_source, reopen
        self.adapt, self.record_states = adapt, record_states
        self.stats = {'started_at': time.time(), 'resumed_episodes': 0, 'reconciled': {'done': 0, 'not_done': 0, 'unknown': 0},
                      'discarded_preparing': 0, 'startup_s': None, 'model_rebuild_s': None, 'journal_experiences': 0,
                      'update_s': 0.0, 'updates': 0}
        t0 = time.perf_counter()
        self._discard_preparing()
        self._reconcile()
        rows = [json.loads(r[0]) for r in self.journal.db.execute('SELECT data FROM experiences ORDER BY rowid')]
        own = [Experience.from_json(j) for j in rows]
        self.stats['journal_experiences'] = len(own)
        t1 = time.perf_counter()
        self.model = model_factory(list(base_experiences) + own)
        self.stats['model_rebuild_s'] = time.perf_counter() - t1
        self.stats['startup_s'] = time.perf_counter() - t0
        self.journal.event('supervisor_start', {k: v for k, v in self.stats.items() if k != 'reconciled'} | {'reconciled': dict(self.stats['reconciled'])})

    # --- intent vs reality ---
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
        for aid, episode, step, tool, args, status in self.journal.unresolved():
            ep = self.journal.episode(episode)
            row = self.journal.db.execute('SELECT pre, post FROM actions WHERE id=?', (aid,)).fetchone()
            pre = json.loads(row[0]) if row and row[0] else None
            post = json.loads(row[1]) if row and row[1] else None
            verdict = 'unknown'
            if ep is not None and pre is not None:
                try:
                    goal = Goal.from_json(json.loads(ep['goal']))
                    real = self.reopen(ep['root']).observe(goal.universe)
                    args_l = json.loads(args)
                    if all(_same(real.get(a), pre.get(a)) for a in args_l):
                        verdict = 'not_done'
                    elif post is not None and all(_predicted_match(real.get(a), post.get(a)) for a in args_l):
                        verdict = 'done'
                except Exception as e:                       # the workspace itself may be gone or unreadable
                    verdict = f'unknown'
                    self.journal.event('reconcile_error', {'action': aid, 'error': repr(e)})
            self.stats['reconciled'][verdict] += 1
            self.journal.mark(aid, 'reconciled', None if verdict == 'unknown' else verdict == 'done', f'reconciled:{verdict}:{status}')

    # --- episodes ---
    def _run(self, ws, goal, episode_id, start_step, fault=None):
        t0 = time.perf_counter()
        before = self.stats['update_s']
        model = _Timed(self.model, self.stats) if self.adapt else self.model
        rec = run_episode(ws, goal, model, self.journal, episode_id, adapt=self.adapt, start_step=start_step,
                          record_states=self.record_states, fault=fault)
        real = ws.observe(goal.universe)
        done = goal.satisfied(real)
        result = {'episode': episode_id, 'completed': done, 'start_step': start_step, 'actions': rec['actions'],
                  'noops': rec['noops'], 'plan_predicted': rec['plan_predicted'], 'pred_errors': rec['pred_errors'],
                  'abstained': rec['abstained'], 'planner_budget_exceeded': rec['planner_budget_exceeded'],
                  'keep_violated': rec['keep_violated'], 'wall_s': time.perf_counter() - t0, 'cpu_s': rec['cpu_s'],
                  'update_s': self.stats['update_s'] - before, 'resumed': start_step > 0,
                  **self.journal.episode_totals(episode_id)}          # counts across every process that worked on it
        self.journal.finish_episode(episode_id, 'done' if done else 'failed', result)
        with (self.root / 'episodes.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(result) + '\n')
            f.flush()
        return result

    def run(self, n_episodes, stop_file=None, fault=None, pace_s=0.0):
        """Finish `n_episodes` episodes in total (done or failed, counting those finished before a restart).
        `fault` (tests only) is a callable fault(step) with an arm(episode_id) method, passed to the loop;
        `pace_s` (tests only) sleeps between episodes so a crash test has time to kill the process."""
        results = []
        for ep in self.journal.open_episodes():                      # unfinished work first, from the real state
            goal = Goal.from_json(json.loads(ep['goal']))
            ws = self.reopen(ep['root'])
            start = self.journal.episode_steps(ep['id'])
            self.stats['resumed_episodes'] += 1
            self.journal.event('resume', {'episode': ep['id'], 'start_step': start})
            if fault is not None:
                fault.arm(ep['id'])
            results.append(self._run(ws, goal, ep['id'], start, fault))
        while self.journal.count_episodes() < n_episodes:
            if stop_file and Path(stop_file).exists():
                break
            idx = self.journal.count_episodes(any_status=True)
            episode_id = f'sup-{idx}'
            task_root = self.root / 'ws' / f'ep{idx}'
            self.journal.begin_episode(episode_id, '{}', str(task_root), '{}', status='preparing')   # row first (idempotent restart)
            ws, goal, meta = self.task_source(idx, task_root)
            self.journal.start_episode(episode_id, json.dumps(goal.to_json()), str(ws.root if hasattr(ws, 'root') else ''),
                                       json.dumps(meta, default=str))
            if fault is not None:
                fault.arm(episode_id)
            results.append(self._run(ws, goal, episode_id, 0, fault))
            if pace_s:
                time.sleep(pace_s)
        return results

    def summary(self):
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
                'episodes_done': db.execute("SELECT COUNT(*) FROM episodes WHERE status='done'").fetchone()[0],
                'episodes_total': self.journal.count_episodes(any_status=True),
                'episode_rows': len(rows), 'completed_rows': sum(r['completed'] for r in rows),
                'resumed_rows': sum(r['resumed'] for r in rows),
                'journal_bytes': (self.root / 'journal.sqlite').stat().st_size, 'unresolved': len(self.journal.unresolved()),
                'action_status': self.journal.counts(), 'peak_mem_mb': None if peak is None else peak / 1e6,
                'model': self.model.describe().get('condition'),
                'experiences_now': len(getattr(self.model, 'experiences', []))}

    def close(self):
        self.journal.close()


class _Timed:
    """Wraps a model so that online updates are timed (learning cost is measured separately, charter §5)."""

    def __init__(self, model, stats):
        self._m, self._s = model, stats
        self.name = model.name

    def __getattr__(self, k):
        return getattr(self._m, k)

    def update(self, exp):
        t0 = time.perf_counter()
        self._m.update(exp)
        self._s['update_s'] += time.perf_counter() - t0
        self._s['updates'] += 1
