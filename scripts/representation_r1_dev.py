"""Developer-exposed native corpus and probes; NEVER fresh capability evidence."""
import argparse
import copy
import json
import random
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.planner import Goal
from packages.action_core.world import Action, Frame, Sandbox
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.planning import choose

SCHEMA = [{'id': 'empty', 'arity': 1}, {'id': 'unlink', 'arity': 1}, {'id': 'copy', 'arity': 2}]
CHANNEL = 'r_c2_eq'


def sensor():
    # Fixed R0 artifact, not a new hand-coded samefile predicate.
    model = json.loads((ROOT / 'evidence/r0-v1/trained.json').read_text())
    report = json.loads((ROOT / 'evidence/r0-v1/report.json').read_text())
    return {'version': 'stat-comparison-v1', 'fields': report['supervisor_channel_mapping'],
            'channels': {CHANNEL: model['rule']}}


def config(seed, linked=False, states=(1, 1), payload=None, on=True, projection=None):
    rng = random.Random(seed)
    names = [f'{rng.getrandbits(80):020x}.bin' for _ in range(3)]
    payload = payload if payload is not None else rng.randbytes(rng.randint(1, 512))
    initial = {names[2]: payload}
    for i, state in enumerate(states):
        if state != 0 and not (i == 1 and linked):
            initial[names[i]] = payload if state == 1 else b''
    cfg = {'paths': names, 'initial': initial, 'protected': {'n2'}, 'operations': SCHEMA,
           'initial_links': {names[1]: names[0]} if linked else {}}
    if on:
        cfg['relation_spec'] = sensor() if projection is None else copy.deepcopy(projection)
    return cfg, payload


def strip(frame):
    value = frame.to_dict()
    value.pop('view_version', None)
    value.pop('relations', None)
    return Frame.from_dict(value)


def train(output, projection=None):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r1_train_'))
    models = {arm: RelationalLearner(schema=SCHEMA) for arm in ('on', 'off')}
    records = []
    patterns = [(False, (a, b)) for a in (0, 1, 2) for b in (0, 1, 2)]
    patterns += [(True, (1, 1)), (True, (2, 2))]
    start = time.perf_counter()
    for length in (7, 41):
        for index, (linked, states) in enumerate(patterns):
            cfg, _ = config(101 + index + length, linked, states, b'x' * length, projection=projection)
            template = Sandbox(root / f'surface_{length}_{index}', **cfg)
            for ordinal, action in enumerate(template.actions()):
                body = Sandbox(root / f'train_{length}_{index}_{ordinal}', **cfg)
                before = body.observe()
                success = body.step(action)
                after = body.observe()
                record = {'before': before.to_dict(), 'action': action.to_dict(), 'after': after.to_dict(),
                          'success': success}
                event_id = str(len(records))
                records.append(record)
                models['on'].learn(event_id, before, action, after)
                models['off'].learn(event_id, strip(before), action, strip(after))
    result = {'transitions': len(records), 'root': str(root), 'seconds': time.perf_counter() - start}
    for arm, model in models.items():
        model._compile()
        result[arm] = {op: {'programs': len(data['programs']), 'unsupported': data['unsupported']}
                       for op, data in model.cache.items()}
        (output / f'{arm}.json').write_text(json.dumps(model.snapshot(), sort_keys=True), encoding='utf-8')
    (output / 'experience.json').write_text(json.dumps(records, sort_keys=True), encoding='utf-8')
    (output / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


def probe(training, output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r1_dev_'))
    results = []
    for linked in (False, True):
        for arm in ('on', 'off'):
            cfg, payload = config(4981, linked, on=arm == 'on')
            body = Sandbox(root / f'{linked}_{arm}', **cfg)
            model = RelationalLearner.restore(json.loads((training / f'{arm}.json').read_text()))
            goal = Goal('empty-without-collateral', sizes=(('n0', 0.), ('n1', body.observe().sizes[1])))
            trace = []
            for step in range(2):
                if goal.holds(body.evidence()):
                    break
                before = body.observe()
                action, prediction, nodes = choose(model, before, goal, body.actions(), horizon=2, limit=8192)
                success = body.step(action)
                trace.append({'before': before.to_dict(), 'action': action.to_dict(),
                              'prediction': prediction.to_dict(), 'after': body.observe().to_dict(),
                              'success': success, 'nodes': nodes})
            native = ((body.root / cfg['paths'][0]).read_bytes() == b'' if
                      (body.root / cfg['paths'][0]).is_file() else False)
            sibling = body.root / cfg['paths'][1]
            native = native and sibling.is_file() and sibling.read_bytes() == payload
            row = {'linked': linked, 'arm': arm, 'completed': bool(native), 'trace': trace}
            results.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != 'trace'}),
                  [item['action'] for item in trace])
    (output / 'traces.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['train', 'probe'])
    parser.add_argument('--training', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    train(args.output) if args.mode == 'train' else probe(args.training, args.output)
