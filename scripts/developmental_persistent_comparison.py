"""Preregistered DEV native persistent comparison, not generality/agency.

Fresh instance seed138001,count5; known empty/restore mechanics and supplied
eight-goal schedule. Existing192 actual seed events. Frozen vs incremental,
same persistent WorldSession, no resets/retries;6 actions/goal,48 total/arm,
4096 queries/decision,120s wall cap. All learning/journaling CPU counted.
Gain requires >=2 additional successes without more native actions, OR equal
successes and <=80% CPU with no more actions. Independent native replay and no
retention regression required. Error reduction alone is NOT capability gain.
"""
import json
import sys
import tempfile
import time
import random
from pathlib import Path
from collections import Counter
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_persistent_client import PersistentClient
from scripts.representation_r3_dev import configuration
from scripts.representation_r1_dev import SCHEMA
from scripts.developmental_continual_probe import score
from packages.action_core.world import Sandbox, Frame, Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession, verify_world


def run(output, *, planner_comparison=False):
    # Separate NEW preregistration, never a rerun/reinterpretation of persistent-v1:
    # seed139001,count5; four seed139003-selected subsets (2,3,2,3) interleaved
    # with restore goals. Both incremental, horizon4,4096queries,48actions.
    # New capability criterion: >=2more completed goals within SAME budgets,
    # <=2x total CPU, no retention loss, both native replays GREEN. Actions may
    # increase when previously abstained tasks are solved; report this explicitly.
    output.mkdir(exist_ok=False)
    old = []
    for name in ('developmental-continual.json', 'developmental-online-eval.json'):
        old += json.loads((ROOT / 'evidence' / name).read_text())['records']
    cfg, aliases, reference, payload = configuration(5, 139001 if planner_comparison else 138001)
    summary = {}; started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_persistent_compare_') as root:
        for arm in (('beam', 'cost_ordered') if planner_comparison else ('frozen', 'online')):
            body = Sandbox(Path(root) / arm, **cfg)
            full = body.observe().sizes[body.handles.index(reference)]
            schedule = ({0}, set(), {1, 2}, set(), {3, 4}, set(), {0, 2, 4}, set())
            if planner_comparison:
                rng = random.Random(139003)
                schedule = [s for count in (2, 3, 2, 3)
                            for s in (set(rng.sample(range(5), count)), set())]
            goals = [Goal(str(i), sizes=tuple((h, 0. if j in empty else full)
                         for j, h in enumerate(aliases))) for i, empty in enumerate(schedule)]
            client = PersistentClient(old, schema=SCHEMA, learning=arm != 'frozen',
                horizon=4 if planner_comparison else 3,
                planner='cost_ordered' if arm == 'cost_ordered' else 'beam')
            db = output / (arm + '.sqlite'); results = []
            cpu = time.process_time()
            with closing(WorldSession(db, body, client, config=cfg, total_budget=48,
                    world_id='world', self_id='self')) as world:
                for goal in goals:
                    world.issue_goal(goal, 6)
                    while world.state['active'] is not None:
                        if time.monotonic() - started > 120:
                            raise TimeoutError('persistent comparison hard cap')
                        result = world.step()
                        if world.state['halted']:
                            raise RuntimeError(result)
                    results.append(result)
                steps = world.state['steps']
            cpu = time.process_time() - cpu
            verified = verify_world(db, expected_config=cfg, expected_total_budget=48,
                expected_world_id='world', expected_self_id='self',
                expected_goals=[(g, 6) for g in goals])
            retention = Counter()
            for row in old:
                retention.update(score(client.adapter.predict_cells(Frame.from_dict(row['before']),
                    Action.from_dict(row['action'])), Frame.from_dict(row['after'])))
            summary[arm] = dict(successes=sum(r['completed'] for r in results),
                actions=steps, cpu=cpu, results=results, replay=verified, retention=retention)
    a, b = (summary['cost_ordered'], summary['beam']) if planner_comparison else (summary['online'], summary['frozen'])
    gain = (a['actions'] <= b['actions'] and (a['successes'] >= b['successes'] + 2 or
        (a['successes'] == b['successes'] and a['cpu'] <= .8 * b['cpu']))
        and a['retention'] == b['retention'] and all(s['replay']['green'] for s in summary.values()))
    if planner_comparison:
        gain = (a['successes'] >= b['successes'] + 2 and a['cpu'] <= 2*b['cpu']
            and a['retention'] == b['retention'] and all(s['replay']['green'] for s in summary.values()))
    result = dict(comparison='planner' if planner_comparison else 'learning',
        verdict='DEV_PERSISTENT_GAIN' if gain else 'NO_DEV_PERSISTENT_GAIN', summary=summary)
    (output / 'report.json').write_text(json.dumps(result, sort_keys=True))
    print(json.dumps(result))


if __name__ == '__main__':
    run(Path(sys.argv[1]), planner_comparison='--planner-comparison' in sys.argv[2:])
