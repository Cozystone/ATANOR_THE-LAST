"""Preflight fixtures and tiny scripted native audit tests; no learned policy run."""
import copy
import hashlib
import json
import sqlite3

import pytest

from scripts import shared_world_fresh as fresh


@pytest.fixture
def registered_inputs(tmp_path, monkeypatch):
    root = tmp_path / 'repository'
    paths = ('packages/action_core/world.py', 'scripts/shared_world_fresh.py',
             'scripts/shared_world_metrics.py', 'tests/test_shared_fresh.py') + fresh.DEV_FILES
    for name in paths:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# synthetic committed source\n', encoding='utf-8')
    (root / 'docs').mkdir()
    committed = {p: (root / p).read_bytes() for p in paths}

    def git_stub(where, *args):
        assert where == root.resolve()
        if args == ('rev-parse', 'HEAD'):
            return b'a' * 40 + b'\n'
        if args[0] == 'show':
            name = args[1].split(':', 1)[1]
            if name not in committed:
                raise ValueError('uncommitted fixture path')
            return committed[name]
        if args[0] == 'ls-tree':
            return ('\n'.join(committed) + '\n').encode()
        if args[0] == 'merge-base':
            return b''
        raise AssertionError(args)

    monkeypatch.setattr(fresh, 'git', git_stub)
    closure = fresh.source_closure(root)
    training = tmp_path / 'training'
    training.mkdir()
    for arm in fresh.ARMS[:-1]:
        fresh.write_new(training / (arm + '.json'), {'revision': 0, 'seen': [], 'algorithm': arm})
    fresh.write_new(training / 'observations.json', [{'synthetic_row': i} for i in range(512)])
    fresh.write_new(training / 'manifest.json', {'status': 'DEV_TRAINING',
        'native_training_reexecution': True, 'cases': 32, 'steps_per_case': 16,
        'observations': 512, 'seed': 913100, 'source_hashes': closure,
        'files': {p: fresh.sha(training / p) for p in fresh.TRAIN_FILES},
        'training_cpu_seconds': {'relational': 1., 'full_context': 2., 'retrieval': 3.},
        'common_cpu_seconds': 4.})
    dev = tmp_path / 'dev.json'
    fresh.write_new(dev, {'status': 'DEV_READY', 'lives': 4, 'planning': fresh.PLAN,
        'totals': {a: {'all_native_verified': True, 'invalid_proposals': 0,
                      'evaluation_count': 8, 'evaluation_successes': 8} for a in fresh.ARMS},
        'source_hashes_before': closure, 'source_hashes_after': closure})
    # Pure registration tests do not replay this deliberately synthetic report.
    # Actual native replay is exercised independently below, without this mock.
    def audit_stub(reportpath, trainingdir):
        return {'dev_sha256': fresh.sha(reportpath), 'training_files': {
            n: fresh.sha(trainingdir / n) for n in fresh.TRAIN_FILES + ('manifest.json',)}}
    monkeypatch.setattr(fresh, 'audit_dev_replay', audit_stub)
    return root, training, dev, committed


def register(values):
    root, training, dev, committed = values
    path = root / 'docs' / 'protocol.json'
    value = fresh.prereg(path, training, dev, root=root)
    return path, value


def seal(values, path):
    values[3][path.relative_to(values[0]).as_posix()] = path.read_bytes()


def test_clean_prereg_and_committed_protocol_are_accepted(registered_inputs):
    path, value = register(registered_inputs)
    seal(registered_inputs, path)
    assert fresh.preflight(path, root=registered_inputs[0]) == value
    assert value['training']['cpu_seconds']['frozen'] == 5.
    assert value['design']['lives'] == 64
    assert 'scripts/shared_world_metrics.py' in value['sources']


def test_prereg_refuses_dirty_or_untracked_candidate_source(registered_inputs):
    root, training, dev, _ = registered_inputs
    (root / fresh.MODEL_FILES[0]).write_text('# dirty candidate\n', encoding='utf-8')
    with pytest.raises(ValueError, match='uncommitted|changed'):
        fresh.prereg(root / 'docs' / 'protocol.json', training, dev, root=root)
    assert not (root / 'docs' / 'protocol.json').exists()


def test_uncommitted_protocol_is_not_an_execution_authority(registered_inputs):
    path, _ = register(registered_inputs)
    with pytest.raises(ValueError, match='uncommitted'):
        fresh.preflight(path, root=registered_inputs[0])


@pytest.mark.parametrize('target', ['checkpoint', 'observations', 'manifest', 'source', 'dev'])
def test_changed_frozen_inputs_are_rejected(registered_inputs, target):
    path, _ = register(registered_inputs)
    seal(registered_inputs, path)
    root, training, dev, _ = registered_inputs
    changed = {'checkpoint': training / 'relational.json', 'observations': training / 'observations.json',
               'manifest': training / 'manifest.json', 'source': root / fresh.MODEL_FILES[0], 'dev': dev}[target]
    changed.write_bytes(changed.read_bytes() + b' ')
    with pytest.raises(ValueError):
        fresh.preflight(path, root=root)


def test_weak_dev_comparator_cannot_register(registered_inputs):
    root, training, dev, _ = registered_inputs
    value = fresh.read(dev)
    value['totals']['full_context']['evaluation_successes'] = 3
    dev.write_text(fresh.canonical(value), encoding='utf-8')
    with pytest.raises(ValueError, match='fifty percent'):
        fresh.prereg(root / 'docs' / 'protocol.json', training, dev, root=root)


def test_committing_changed_thresholds_does_not_lower_fixed_gate(registered_inputs):
    path, protocol = register(registered_inputs)
    protocol['thresholds']['success_min'] = .01
    path.write_text(fresh.canonical(protocol), encoding='utf-8')
    seal(registered_inputs, path)
    with pytest.raises(ValueError, match='fixed design'):
        fresh.preflight(path, root=registered_inputs[0])


def test_registration_and_attempt_are_never_overwritten(registered_inputs, tmp_path):
    path, _ = register(registered_inputs)
    with pytest.raises(FileExistsError):
        register(registered_inputs)
    claim = fresh.claim_attempt(path, tmp_path / 'attempt-one')
    assert claim['protocol_sha256'] == fresh.sha(path)
    with pytest.raises(FileExistsError):
        fresh.claim_attempt(path, tmp_path / 'attempt-two')
    assert not (tmp_path / 'attempt-two').exists()


def journal_fixture(tmp_path, *, arm='relational'):
    """Only a counter/model-binding fixture; intentionally not native proof."""
    path = tmp_path / 'journal.sqlite'
    checkpoint = {'revision': 0, 'seen': [], 'payload': 'base'}
    config = {'test_configuration': 'externally fixed'}
    goals = [{'id': f'g{i}', 'kinds': [['n1', 1]], 'equal': []} for i in range(4)]
    wrapped = {'format': 'shared-world-worker-v1', 'algorithm': 'relational', 'frozen': arm == 'frozen',
               'revision': 0, 'seen': [], 'model': checkpoint}
    events = [('BEGIN', {'model_digest': fresh.digest(wrapped), 'model_revision': 0,
        'binding': {'config': config, 'world_id': 'life:0', 'self_id': 'shared-core',
                    'total_budget': 32, 'decision_cap': 128}})]
    episodes = []
    for index, goal in enumerate(goals):
        result = {'goal_id': goal['id'], 'completed': True, 'steps': 1, 'reason': 'goal_reached'}
        events.extend([('GOAL', {'goal': goal, 'budget': 8, 'start_steps': index, 'result': None}),
            ('PREDICT', {'action': {'op': 'opaque', 'args': ['n1']}, 'prediction': {'test': True}, 'nodes': 1}),
            ('DISPATCH', {'step': index + 1}), ('RESULT', {}), ('LEARN', {}), ('GOAL_END', result)])
        episodes.append({'index': index, 'phase': 'learning' if index < 2 else 'evaluation',
                         'goal': goal, 'result': copy.deepcopy(result), 'charged_steps': 1})
    final = copy.deepcopy(wrapped)
    final['revision'], final['seen'] = 4, ['e0', 'e1', 'e2', 'e3']
    if arm != 'frozen':
        final['model'] = {'revision': 4, 'seen': final['seen'], 'payload': 'learned'}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE events(seq INTEGER PRIMARY KEY,kind TEXT,payload TEXT,digest TEXT)')
        db.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,payload TEXT)')
        previous = ''
        for seq, (kind, payload) in enumerate(events, 1):
            text = fresh.canonical(payload)
            previous = hashlib.sha256((previous + kind + text).encode()).hexdigest()
            db.execute('INSERT INTO events VALUES(?,?,?,?)', (seq, kind, text, previous))
        state = {'head': previous, 'steps': 4, 'model': final}
        db.execute('INSERT INTO state VALUES(1,?)', (fresh.canonical(state),))
    row = {'arm': arm, 'life': 0, 'episodes': episodes, 'actual_steps': 4,
           'state_model_digest': fresh.digest(final), 'journal_sha256': fresh.sha(path)}
    return path, row, dict(checkpoint=checkpoint, config=config, goals=goals, life=0, arm=arm)


@pytest.mark.parametrize('arm', ['relational', 'frozen'])
def test_count_and_initial_model_binding_fixture_passes_without_claiming_native_truth(tmp_path, arm):
    path, row, expected = journal_fixture(tmp_path, arm=arm)
    checked = fresh.audit_journal(path, row, **expected)
    assert checked['dispatches'] == 4 and checked['goals'] == 4
    assert 'native_verified' not in checked


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'total', 'false_result', 'base_model', 'external_goal'])
def test_recount_rejects_missing_duplicate_or_forged_counts(tmp_path, fault):
    path, row, expected = journal_fixture(tmp_path)
    if fault == 'missing': row['episodes'].pop()
    elif fault == 'duplicate': row['episodes'][1] = copy.deepcopy(row['episodes'][0])
    elif fault == 'total': row['actual_steps'] = 0
    elif fault == 'false_result': row['episodes'][0]['result']['completed'] = False
    elif fault == 'base_model': expected['checkpoint']['payload'] = 'forged'
    else: expected['goals'] = [dict(g, id='forged') for g in expected['goals']]
    with pytest.raises(ValueError):
        fresh.audit_journal(path, row, **expected)


def test_frozen_final_model_cannot_change_even_with_recomputed_state_digest(tmp_path):
    path, row, expected = journal_fixture(tmp_path, arm='frozen')
    with sqlite3.connect(path) as db:
        state = json.loads(db.execute('SELECT payload FROM state').fetchone()[0])
        state['model']['model']['payload'] = 'illicit-learning'
        db.execute('UPDATE state SET payload=?', (fresh.canonical(state),))
    row['state_model_digest'] = fresh.digest(state['model'])
    row['journal_sha256'] = fresh.sha(path)
    with pytest.raises(ValueError, match='frozen inner'):
        fresh.audit_journal(path, row, **expected)


def test_residual_cpu_is_charged_once_per_arm_on_top_of_training():
    rows = [{'cpu_seconds': 12., 'worker_cpu_seconds': 10.},
            {'cpu_seconds': 9., 'worker_cpu_seconds': 6.}]
    training = dict.fromkeys(fresh.ARMS, 4.)
    common, fixed = fresh.execution_costs(rows, training, 8.)
    assert common == 3. and fixed == dict.fromkeys(fresh.ARMS, 7.)
    assert fresh.execution_costs(rows, training, 4.) == (0., training)
    with pytest.raises(ValueError, match='worker CPU'):
        fresh.execution_costs([{'cpu_seconds': 1., 'worker_cpu_seconds': 2.}], training, 3.)


@pytest.fixture
def native_dev_inputs(tmp_path):
    """Test-only supplied actions, never candidate/training/fresh trajectories."""
    from packages.action_core.model import Forecast
    from packages.action_core.world import Sandbox, Action
    from packages.shared_world.experiment import make_life
    from packages.shared_world.runtime import WorldSession

    seed = 889001  # Not the DEV or fresh seed.
    config, goals = make_life(seed, ordinal=0)
    ref = next(iter(config['protected']))
    child = goals[0].kinds[0][0]
    spare = next(h for h, k in goals[1].kinds if k == 1)
    aux = next(h for h, k in goals[3].kinds if k == 1 and h != spare)
    parent_path = config['paths'][int(child[1:])].rsplit('/', 1)[0]
    parent = f'n{config["paths"].index(parent_path)}'
    script = [Action('mkdir', (parent,)), Action('copy', (ref, child)),
              Action('rename', (child, spare)), Action('rename', (spare, child)),
              Action('rename', (child, spare)), Action('copy', (ref, aux))]
    checkpoint = {'revision': 0, 'seen': [], 'payload': 'synthetic-no-model'}

    class ScriptedClient:
        def __init__(self, arm):
            self.state = {'format': 'shared-world-worker-v1',
                'algorithm': 'relational' if arm == 'frozen' else arm,
                'frozen': arm == 'frozen', 'revision': 0, 'seen': [],
                'model': copy.deepcopy(checkpoint)}

        def snapshot(self):
            return copy.deepcopy(self.state)

        def choose(self, frame, goal, actions, history, *, failed_attempts):
            action = script[self.state['revision']]
            assert action in actions
            forecast = Forecast([[float(k == i) for i in range(3)] for k in frame.kinds],
                frame.sizes, frame.equal, frame.parent, frame.handles)
            return action, forecast, 1

        def learn(self, event_id, before, action, after, history):
            self.state['revision'] += 1
            self.state['seen'].append(event_id)
            if not self.state['frozen']:
                self.state['model'].update(revision=self.state['revision'], seen=list(self.state['seen']))
            return True

    training, devdir = tmp_path / 'native-training', tmp_path / 'native-dev'
    training.mkdir(); devdir.mkdir()
    for name in ('relational', 'full_context', 'retrieval'):
        fresh.write_new(training / f'{name}.json', checkpoint)
    fresh.write_new(training / 'observations.json', [])
    fresh.write_new(training / 'manifest.json', {'test_fixture': True})
    rows = []
    for arm in fresh.ARMS:
        directory = devdir / f'000-{arm}'
        directory.mkdir()
        body = Sandbox(tmp_path / f'body-{arm}', **config)
        world = WorldSession(directory / 'world.sqlite', body, ScriptedClient(arm), config=config,
            total_budget=32, world_id='life:0', self_id='shared-core')
        episodes = []
        try:
            for index, goal in enumerate(goals):
                world.issue_goal(goal, 8)
                result = world.run_goal()
                assert result['completed'] is True, (index, result, [a.to_dict() for a in script])
                episodes.append({'index': index, 'phase': 'learning' if index < 2 else 'evaluation',
                    'goal': goal.to_dict(), 'result': result, 'charged_steps': result['steps']})
            state = world.state
        finally:
            world.close()
        rows.append({'life': 0, 'arm': arm, 'episodes': episodes, 'errors': [],
            'actual_steps': state['steps'], 'state_model_digest': fresh.digest(state['model']),
            'journal_sha256': fresh.sha(directory / 'world.sqlite'), 'cpu_seconds': 1.})
    reportpath = devdir / 'report.json'
    fresh.write_new(reportpath, {'status': 'DEV_READY', 'lives': 1, 'seed': seed, 'rows': rows,
        'totals': {arm: {'evaluation_successes': 2, 'evaluation_count': 2, 'expected_count': 2,
            'evaluation_charged_steps': 3, 'cpu_seconds': 1., 'all_native_verified': True,
            'invalid_proposals': 0} for arm in fresh.ARMS}})
    return reportpath, training


def test_dev_audit_reexecutes_native_goals_and_binds_initial_checkpoints(native_dev_inputs):
    proof = fresh.audit_dev_replay(*native_dev_inputs)
    assert proof['native_arm_runs'] == 4 and proof['goal_ends'] == 16
    assert proof['first_decision_pairs'] == 1
    assert proof['dev_sha256'] == fresh.sha(native_dev_inputs[0])


@pytest.mark.parametrize('fault', ['total', 'seed', 'checkpoint'])
def test_dev_audit_rejects_forged_totals_or_external_input_binding(native_dev_inputs, fault):
    reportpath, training = native_dev_inputs
    report = fresh.read(reportpath)
    if fault == 'total':
        report['totals']['full_context']['evaluation_successes'] = 1
    elif fault == 'seed':
        report['seed'] += 100
    else:
        checkpoint = fresh.read(training / 'full_context.json')
        checkpoint['payload'] = 'different-initial-model'
        (training / 'full_context.json').write_text(fresh.canonical(checkpoint), encoding='utf-8')
    reportpath.write_text(fresh.canonical(report), encoding='utf-8')
    with pytest.raises(ValueError, match='totals|native replay|initial model'):
        fresh.audit_dev_replay(reportpath, training)
