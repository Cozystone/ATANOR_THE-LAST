"""Frozen new-instance DEV mixed-effect life, NOT new mechanics or agency.

Same192 + same3 historical rename observations in both learners. seed141001,
five linked files, protected reference and one vacant slot; one unchanged body
per arm, four supplied goals: selective empty, identity-preserving move, restore,
move back. ALL permitted actions remain available. Both use cost-order search,
depth2,4096queries/decision,4actions/goal,16total,180s wall overall. No retry.
PASS: families4/4,>=1more relational goal than local, no paired goal loss,
<=3x total CPU,old192retention unchanged, independent native replay GREEN.
This restores complementary previously separate learned abilities; it does not
claim the learner invented either representational language or selected goals.
"""
import json
import sys
import time
import tempfile
from pathlib import Path
from contextlib import closing
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_persistent_client import PersistentClient
from scripts.representation_r3_dev import configuration
from scripts.developmental_continual_probe import score
from packages.action_core.world import Sandbox, Frame, Action
from packages.action_core.planner import Goal
from packages.shared_world.runtime import WorldSession, verify_world


def run(output):
    output.mkdir(exist_ok=False)
    old = sum([json.loads((ROOT / 'evidence' / name).read_text())['records'] for name in
        ('developmental-continual.json', 'developmental-online-eval.json')], [])
    examples = [json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
    examples += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows']
                 if r['case'] in ('declared_absent', 'declared_present')]
    cfg, aliases, reference, payload = configuration(5, 141001)
    cfg['paths'].append('vacant_slot'); dest = 'n6'
    cfg['operations'] = cfg['operations'] + [{'id':'rename', 'arity':2}]
    results = {}; started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_mixed_life_') as root:
        for arm in ('local', 'families'):
            body = Sandbox(Path(root)/arm, **cfg); frame = body.observe()
            channel = next(iter(frame.relations)); full = frame.sizes[int(reference[1:])]
            goals = [Goal('empty', sizes=tuple((h, 0. if i == 0 else full) for i,h in enumerate(aliases))),
                Goal('move', kinds=((aliases[1],0),(dest,1)), relations=((channel,dest,aliases[2],1),)),
                Goal('restore', sizes=((aliases[0],full),)),
                Goal('back', kinds=((dest,0),(aliases[1],1)), relations=((channel,aliases[1],aliases[2],1),))]
            cpu = time.process_time()
            client = PersistentClient(old+examples, schema=cfg['operations'], horizon=2,
                planner='cost_ordered', representation=arm)
            path = output/(arm+'.sqlite'); outcomes = []
            with closing(WorldSession(path, body, client, config=cfg, total_budget=16,
                    world_id='world', self_id='self')) as world:
                for goal in goals:
                    world.issue_goal(goal, 4)
                    while world.state['active'] is not None:
                        if time.monotonic()-started > 180: raise TimeoutError('180s cap')
                        result = world.step()
                        if world.state['halted']: raise RuntimeError(result)
                    outcomes.append(result)
                steps = world.state['steps']
            cpu = time.process_time()-cpu
            replay = verify_world(path, expected_config=cfg, expected_total_budget=16,
                expected_world_id='world', expected_self_id='self', expected_goals=[(g,4) for g in goals])
            retained = Counter()
            for r in old:
                retained.update(score(client.adapter.predict_cells(Frame.from_dict(r['before']),
                    Action.from_dict(r['action'])), Frame.from_dict(r['after'])))
            results[arm] = dict(outcomes=outcomes, actions=steps, cpu=cpu, replay=replay, retention=retained)
    a,b = results['families'],results['local']
    passed = (all(r['completed'] for r in a['outcomes'])
        and sum(a['outcomes'][i]['completed'] for i in (1,3)) >= 1+sum(b['outcomes'][i]['completed'] for i in (1,3))
        and a['cpu'] <= 3*b['cpu'] and a['retention'] == b['retention']
        and all(r['replay']['green'] for r in results.values()))
    result = dict(verdict='BOUNDED_MIXED_LIFE_GAIN' if passed else 'NO_MIXED_LIFE_GAIN', results=results)
    (output/'report.json').write_text(json.dumps(result,sort_keys=True))
    print(json.dumps(result))


if __name__ == '__main__': run(Path(sys.argv[1]))
