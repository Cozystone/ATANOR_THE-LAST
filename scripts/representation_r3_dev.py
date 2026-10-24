"""Exposed training/scope probes for generic set-effect partition, not final data."""
import argparse
import json
from pathlib import Path
import random
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.planner import Goal
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.planning import choose
from scripts.representation_r1_dev import SCHEMA


def configuration(count, seed, pattern='coupled_full', payload=None):
    rng = random.Random(seed)
    names = [f'{rng.getrandbits(72):018x}' for _ in range(count + 1)]
    aliases, reference = names[:-1], names[-1]
    payload = payload if payload is not None else rng.randbytes(rng.randint(53, 199))
    initial = {reference: payload}
    links = {}
    if pattern in ('coupled_full', 'coupled_empty'):
        initial[aliases[0]] = payload if pattern == 'coupled_full' else b''
        links = {name: aliases[0] for name in aliases[1:]}
    elif pattern in ('detached_absent', 'detached_empty'):
        initial[aliases[1]] = payload
        links = {name: aliases[1] for name in aliases[2:]}
        if pattern == 'detached_empty':
            initial[aliases[0]] = b''
    elif pattern in ('independent_full', 'independent_mixed'):
        initial.update({name: payload for name in aliases})
        if pattern == 'independent_mixed':
            initial[aliases[0]] = b''
    else:
        raise ValueError('unknown DEV pattern')
    paths = list(names)
    rng.shuffle(paths)
    handles = {name: f'n{paths.index(name)}' for name in names}
    projection = json.loads((ROOT / 'evidence/r2-discovery/receipt.json').read_text())['projection']
    cfg = {'paths': paths, 'initial': initial, 'initial_links': links,
           'protected': {handles[reference]}, 'operations': SCHEMA, 'relation_spec': projection}
    return cfg, [handles[name] for name in aliases], handles[reference], payload


def make_goal(body, aliases, collective):
    view = body.observe()
    return Goal('empty-class' if collective else 'empty-one',
        sizes=tuple((h, 0. if collective or i == 0 else view.sizes[view.handles.index(h)])
                    for i, h in enumerate(aliases)))


def native_success(body, aliases, reference, payload, collective):
    for i, handle in enumerate(aliases):
        path = body._paths[handle]
        expected = b'' if collective or i == 0 else payload
        if not path.is_file() or path.read_bytes() != expected:
            return False
    return body._paths[reference].read_bytes() == payload


def train(output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r3_train_'))
    models = {arm: RelationalLearner(schema=SCHEMA, partitioned=arm == 'on') for arm in ('on', 'off')}
    data = []
    patterns = ('coupled_full', 'coupled_empty', 'detached_absent', 'detached_empty',
                'independent_full', 'independent_mixed')
    for count in (2, 3):
        for length in (7, 41):
            for index, pattern in enumerate(patterns):
                cfg, _, _, _ = configuration(count, 1141 + count * 100 + length + index, pattern, b'x' * length)
                template = Sandbox(root / f'surface_{count}_{length}_{index}', **cfg)
                for ordinal, action in enumerate(template.actions()):
                    body = Sandbox(root / f'train_{count}_{length}_{index}_{ordinal}', **cfg)
                    before = body.observe()
                    body.step(action)
                    after = body.observe()
                    event = str(len(data))
                    data.append({'before': before.to_dict(), 'action': action.to_dict(), 'after': after.to_dict()})
                    for model in models.values():
                        model.learn(event, before, action, after)
    summary = {'transitions': len(data), 'training_alias_counts': [2, 3]}
    for arm, model in models.items():
        model._compile()
        summary[arm] = {op: {'programs': len(v['programs']), 'unsupported': v['unsupported']}
                        for op, v in model.cache.items()}
        with (output / f'{arm}.json').open('x') as stream:
            json.dump(model.snapshot(), stream, sort_keys=True)
    with (output / 'experience.json').open('x') as stream:
        json.dump(data, stream, sort_keys=True)
    with (output / 'report.json').open('x') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary, indent=2))


def probe(training, output):
    output.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix='atanor_r3_dev_'))
    rows = []
    for count in (3, 4, 5):
        for collective in (False, True):
            for arm in ('on', 'off'):
                cfg, aliases, reference, payload = configuration(count, 761 + count)
                body = Sandbox(root / f'{count}_{collective}_{arm}', **cfg)
                model = RelationalLearner.restore(json.loads((training / f'{arm}.json').read_text()))
                goal = make_goal(body, aliases, collective)
                trace = []
                for step in range(2):
                    if native_success(body, aliases, reference, payload, collective):
                        break
                    action, forecast, nodes = choose(model, body.observe(), goal, body.actions(), horizon=2, limit=32768)
                    body.step(action)
                    trace.append({'action': action.to_dict(), 'nodes': nodes, 'prediction': forecast.to_dict()})
                row = {'aliases': count, 'collective': collective, 'arm': arm,
                       'success': native_success(body, aliases, reference, payload, collective), 'trace': trace}
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if k != 'trace'}),
                      [v['action'] for v in trace], flush=True)
    with (output / 'traces.json').open('x') as stream:
        json.dump(rows, stream, indent=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['train', 'probe'])
    parser.add_argument('--training', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    train(args.output) if args.mode == 'train' else probe(args.training, args.output)
