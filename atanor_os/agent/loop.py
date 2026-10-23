"""Decision/execution loop (charter §7): observe → plan → record intent → gate → act → re-observe → verify.

Receding horizon: only the first action of a plan is executed, then the world is re-observed.
A failed action is remembered for this exact state so it is not retried blindly.
No plan with the search exhausted = abstain; no plan because a search budget stopped the
planner = planner_budget_exceeded. Both end the episode (there is nothing to execute).
"""
import time

from ..core.types import Experience
from ..world.fs_world import CAPABILITY, Workspace
from .planner import canon, plan

CHECK = ('kind', 'ext', 'hash')


def run_episode(ws, goal, model, journal, episode_id, adapt=False):
    rec = {'episode': episode_id, 'condition': model.name, 'steps': [], 'actions': 0, 'noops': 0, 'blocked': 0,
           'abstained': False, 'planner_budget_exceeded': False, 'budget_exceeded': False,
           'pred_errors': 0, 'pred_total': 0, 'docs_predictions': 0, 'keep_violated': False,
           'env_errors': 0, 'status_counts': {}, 'plan_stops': {}, 'plan_expanded': 0, 'plan_predicted': 0,
           'plan_seconds': 0.0, 'adapt': adapt}
    t0, c0 = time.perf_counter(), time.process_time()
    state = ws.observe(goal.universe)
    avoid, avoid_key = set(), canon(state)
    for step in range(goal.budget['actions']):
        if goal.satisfied(state):
            break
        key = canon(state)
        if key != avoid_key:
            avoid, avoid_key = set(), key
        p, pst = plan(state, goal, model, Workspace.actions(sorted(state)), avoid)
        rec['plan_expanded'] += pst['expanded']
        rec['plan_predicted'] += pst['predicted']
        rec['plan_seconds'] += pst['seconds']
        rec['plan_stops'][pst['stop']] = rec['plan_stops'].get(pst['stop'], 0) + 1
        if p is None:
            if pst['stop'] == 'exhausted':
                rec['abstained'] = True
            else:
                rec['planner_budget_exceeded'] = True
            break
        tool, args = p[0]
        predicted, status = model.predict(state, tool, args)
        rec['status_counts'][status] = rec['status_counts'].get(status, 0) + 1
        if status.endswith('documented'):
            rec['docs_predictions'] += 1
        aid = f'{episode_id}:{step}'
        journal.intent(aid, episode_id, step, tool, args, {'status': status, 'ok': predicted is not None})
        cap = CAPABILITY.get(tool)
        if cap and not goal.capabilities.get(cap):           # executor gate, independent of the planner
            rec['blocked'] += 1
            journal.mark(aid, 'blocked', False, 'capability')
            break
        try:
            res = ws.execute(tool, args, goal.capabilities)
            journal.mark(aid, 'executed', res['ok'], res['error'])
            post = ws.observe(goal.universe)
        except Exception as e:                                # outcome unknown: stop, never guess
            rec['env_errors'] += 1
            journal.mark(aid, 'unknown', None, repr(e))
            break
        journal.mark(aid, 'verified', res['ok'], res['error'])
        rec['actions'] += 1
        if not res['ok']:
            rec['noops'] += 1
            avoid.add((tool, args))
        err = res['ok'] != (predicted is not None) or (res['ok'] and any(
            predicted[a][k] not in ('unknown', post[a][k]) for a in args for k in CHECK))
        rec['pred_total'] += 1
        rec['pred_errors'] += int(err)
        exp = Experience(aid, tool, tuple(args), state, post, res['ok'], res['blocked'], res['ms'], False, episode_id)
        journal.experience(exp, episode_id)
        if adapt:
            model.update(exp)
        if any(not l.holds(post) for l in goal.keep):
            rec['keep_violated'] = True
        rec['steps'].append({'step': step, 'tool': tool, 'args': list(args), 'status': status, 'ok': res['ok'],
                             'pred_error': err, 'plan_len': len(p), 'plan_stop': pst['stop']})
        state = post
    rec['agent_believes_done'] = goal.satisfied(state)
    rec['budget_exceeded'] = not (rec['agent_believes_done'] or rec['abstained'] or rec['planner_budget_exceeded']
                                  or rec['blocked'] or rec['env_errors'])
    rec['wall_s'] = time.perf_counter() - t0
    rec['cpu_s'] = time.process_time() - c0
    return rec
