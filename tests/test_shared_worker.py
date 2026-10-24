"""Process/syntax mechanism checks, not native authority or capability evidence."""
import copy
import json
import math

import pytest

from packages.action_core.model import Forecast, Learner as LegacyLearner
from packages.action_core.planner import Goal
from packages.action_core.retrieval import Retrieval
from packages.action_core.schema import OperationSchema
from packages.action_core.world import Action, Frame
from packages.shared_world.contracts import JointForecast
from packages.shared_world.full_context import FullContextLearner
from packages.shared_world.relational import RelationalLearner
from packages.shared_world.worker import Client, ModelState, FORMAT


SCHEMA = OperationSchema((('v17', 2), ('z9', 1)))
ACTION = Action('v17', ('n0', 'n1'))
GOAL = Goal('destination', (('n1', 1),))


def views():
    before = Frame([1, 0], [.2, 0.], [[1, 0], [0, 0]], [[0, 0], [0, 0]], ('n0', 'n1'))
    after = Frame([1, 1], [.2, .2], [[1, 1], [1, 1]], [[0, 0], [0, 0]], ('n0', 'n1'))
    return before, after


def forecast(frame):
    return Forecast([[int(k == i) for i in range(3)] for k in frame.kinds],
                    copy.deepcopy(frame.sizes), copy.deepcopy(frame.equal),
                    copy.deepcopy(frame.parent), frame.handles)


def base(algorithm):
    factory = {'relational': RelationalLearner, 'full_context': FullContextLearner,
               'retrieval': Retrieval}[algorithm]
    kwargs = {'schema': SCHEMA}
    if algorithm != 'retrieval':
        kwargs['updates'] = 1
    model = factory(**kwargs)
    before, after = views()
    model.learn('base_event', before, ACTION, after, [])
    return json.loads(json.dumps(model.snapshot()))


@pytest.mark.parametrize('algorithm', ['relational', 'full_context', 'retrieval'])
def test_real_process_learn_snapshot_restore_roundtrip(algorithm):
    before, after = views()
    with Client(algorithm, seed=7, schema=SCHEMA, horizon=1, limit=16) as first:
        assert first.learn('first', before, ACTION, after, []) is True
        assert first.learn('first', before, ACTION, after, []) is False
        snapshot = first.snapshot()
        assert snapshot['algorithm'] == algorithm
        assert snapshot['frozen'] is False
        assert snapshot['revision'] == 1
        assert first.worker_cpu_seconds > 0
        expected = first.choose(before, GOAL, [ACTION])
    with Client(algorithm, seed=999, schema=SCHEMA, horizon=1, limit=16) as second:
        second.restore(json.loads(json.dumps(snapshot)))
        assert second.snapshot() == snapshot
        actual = second.choose(before, GOAL, [ACTION])
    assert expected[0] == actual[0]
    assert expected[1].to_dict() == actual[1].to_dict()
    assert expected[2] == actual[2]


@pytest.mark.parametrize('algorithm', ['relational', 'full_context', 'retrieval'])
def test_real_process_frozen_predictions_and_inner_state_unchanged(algorithm):
    before, _ = views()
    raw = base(algorithm)
    with Client(algorithm, schema=SCHEMA, frozen=True, horizon=1, limit=16) as worker:
        worker.restore(raw)
        previous = worker.snapshot()
        prediction = worker.choose(before, GOAL, [ACTION])[1].to_dict()
        assert worker.learn('new_failure', before, ACTION, before, []) is True
        current = worker.snapshot()
        assert current['revision'] == previous['revision'] + 1
        assert current['seen'] == ['base_event', 'new_failure']
        assert current['model'] == previous['model'] == raw
        assert worker.choose(before, GOAL, [ACTION])[1].to_dict() == prediction
        assert worker.learn('new_failure', before, ACTION, before, []) is False
    with Client(algorithm, schema=SCHEMA, frozen=True, horizon=1, limit=16) as restored:
        restored.restore(current)
        assert restored.snapshot() == current
        assert restored.choose(before, GOAL, [ACTION])[1].to_dict() == prediction


def fake_client(reply):
    client = Client.__new__(Client)
    client.algorithm, client.frozen, client.schema = 'relational', False, SCHEMA
    client.budget = {'horizon': 1, 'width': 2, 'limit': 16, 'revisit_penalty': .2}
    client._request = lambda *_args, **_kwargs: reply
    return client


def valid_reply():
    before, _ = views()
    return {'action': ACTION.to_dict(), 'forecast': JointForecast([(1., forecast(before))]).to_dict(), 'nodes': 1}


@pytest.mark.parametrize('forgery', ['authority', 'forecast_authority', 'action_authority',
                                    'too_many_nodes', 'bool_nodes', 'foreign_scope', 'foreign_parent',
                                    'nonfinite_probability', 'foreign_action'])
def test_client_rechecks_forged_raw_choice_replies(forgery):
    reply = valid_reply()
    if forgery == 'authority':
        reply['verified'] = True
    elif forgery == 'forecast_authority':
        reply['forecast']['source'] = 'native'
    elif forgery == 'action_authority':
        reply['action']['status'] = 'valid'
    elif forgery == 'too_many_nodes':
        reply['nodes'] = 17
    elif forgery == 'bool_nodes':
        reply['nodes'] = True
    elif forgery == 'foreign_scope':
        reply['forecast']['outcomes'][0]['state']['handles'][0] = 'n9'
    elif forgery == 'foreign_parent':
        reply['forecast']['outcomes'][0]['state']['parent'][0][1] = 1
    elif forgery == 'nonfinite_probability':
        reply['forecast']['outcomes'][0]['weight'] = math.nan
    else:
        reply['action'] = Action('z9', ('n0',)).to_dict()
    before, _ = views()
    with pytest.raises(ValueError):
        fake_client(reply).choose(before, GOAL, [ACTION])


def test_client_accepts_typed_joint_and_marginal_prediction_replies():
    before, _ = views()
    reply = valid_reply()
    assert type(fake_client(reply).choose(before, GOAL, [ACTION])[1]) is JointForecast
    reply['forecast'] = forecast(before).to_dict()
    assert type(fake_client(reply).choose(before, GOAL, [ACTION])[1]) is Forecast


@pytest.mark.parametrize('forgery', ['authority', 'wrong_request', 'negative_cpu', 'nan_cpu', 'model_cpu'])
def test_transport_wrapper_rejects_forged_envelope(forgery):
    client = Client.__new__(Client)
    client.worker_cpu_seconds, client._next_request = 0., 0
    response = {'ok': True, 'request_id': 0, 'worker_cpu_seconds': .125, 'result': True}
    if forgery == 'authority':
        response['verified'] = True
    elif forgery == 'wrong_request':
        response['request_id'] = 1
    elif forgery == 'negative_cpu':
        response['worker_cpu_seconds'] = -1.
    elif forgery == 'nan_cpu':
        response['worker_cpu_seconds'] = math.nan
    else:
        response['model_cpu_seconds'] = 0.
    client._exchange = lambda _request: response
    with pytest.raises(ValueError):
        client._request('snapshot')
    assert client.worker_cpu_seconds == 0.


def test_transport_wrapper_accumulates_its_cpu_field_not_model_result():
    client = Client.__new__(Client)
    client.worker_cpu_seconds, client._next_request = 0., 0
    client._exchange = lambda r: {'ok': True, 'request_id': r['request_id'],
                                  'worker_cpu_seconds': .125,
                                  'result': {'model_claimed_cpu': 9000}}
    client._request('snapshot')
    client._request('snapshot')
    assert client.worker_cpu_seconds == .25


def test_foreign_algorithm_schema_and_frozen_checkpoints_rejected():
    relational = base('relational')
    full = base('full_context')
    state = ModelState('relational', False, SCHEMA)
    state.restore(relational)
    previous = state.snapshot()
    with pytest.raises(ValueError, match='algorithm/schema'):
        state.restore(full)
    assert state.snapshot() == previous
    bad_schema = copy.deepcopy(relational)
    bad_schema['schema'][0]['id'] = 'foreign'
    with pytest.raises(ValueError, match='algorithm/schema'):
        state.restore(bad_schema)
    bad_frozen = state.snapshot()
    bad_frozen['frozen'] = True
    with pytest.raises(ValueError, match='frozen binding'):
        state.restore(bad_frozen)
    assert state.snapshot() == previous
    legacy = LegacyLearner(updates=0, schema=SCHEMA).snapshot()
    with pytest.raises(ValueError, match='foreign model'):
        ModelState('full_context', False, SCHEMA).restore(legacy)


def test_wrapped_revision_and_extra_authority_rejected():
    state = ModelState('relational', False, SCHEMA)
    state.restore(base('relational'))
    good = state.snapshot()
    bad = copy.deepcopy(good)
    bad['revision'] += 1
    with pytest.raises(ValueError, match='seen/revision'):
        state.restore(bad)
    bad = copy.deepcopy(good)
    bad['source_bindings'] = {'verified': True}
    with pytest.raises(ValueError, match='fields'):
        state.restore(bad)
    assert state.snapshot() == good


def test_real_process_rejects_actual_authority_and_bad_learn_acknowledgment():
    before, after = views()
    with Client(schema=SCHEMA) as worker:
        before_snapshot = worker.snapshot()
        with pytest.raises(ValueError, match='serialized action'):
            worker._request('learn', event_id='bad', before=before.to_dict(), after=after.to_dict(),
                            action={**ACTION.to_dict(), 'verified': True}, history=[])
        assert worker.snapshot() == before_snapshot
        with pytest.raises(ValueError, match='fields'):
            worker._request('snapshot', authority='supervisor')
        assert worker.snapshot() == before_snapshot


def test_frozen_wrapper_rejects_predicted_self_training():
    state = ModelState('relational', True, SCHEMA)
    state.restore(base('relational'))
    before, after = views()
    old = state.snapshot()
    with pytest.raises(ValueError, match='observed Frame'):
        state.learn('forged', before, ACTION, forecast(after), [])
    assert state.snapshot() == old


def test_client_snapshot_cannot_change_arm_binding():
    client = fake_client({'format': FORMAT, 'algorithm': 'relational', 'frozen': True,
                          'revision': 0, 'seen': [], 'model': base('relational')})
    with pytest.raises(ValueError, match='frozen binding'):
        client.snapshot()


def test_invalid_learn_acknowledgment_is_rejected():
    before, after = views()
    client = fake_client({'accepted': True, 'verified': True})
    with pytest.raises(ValueError, match='acknowledgment'):
        client.learn('event', before, ACTION, after, [])


def test_full_context_explicit_training_options_and_restore_preservation():
    raw = base('full_context')
    with Client('full_context', schema=SCHEMA, updates=3,
                change_balanced=True, latest_update=True) as worker:
        initialized = worker.snapshot()['model']
        assert initialized['updates'] == 3
        assert initialized['change_balanced'] is True
        assert initialized['latest_update'] is True
        worker.restore(raw)
        assert worker.snapshot()['model'] == raw


def test_failed_attempts_are_keyword_only_and_separate_from_learning_history():
    before, after = views()
    captured = []
    client = fake_client(valid_reply())
    client._request = lambda command, **fields: captured.append((command, fields)) or valid_reply()
    history, failed = [(after, ACTION)], [(before, ACTION)]
    original_history, original_failed = copy.deepcopy(history), copy.deepcopy(failed)
    client.choose(before, GOAL, [ACTION], history, failed_attempts=failed)
    assert captured[-1][1]['history'] == [[after.to_dict(), ACTION.to_dict()]]
    assert captured[-1][1]['failed_attempts'] == [[before.to_dict(), ACTION.to_dict()]]
    assert history == original_history and failed == original_failed
    client.choose(before, GOAL, [ACTION], history)
    assert captured[-1][1]['history'] == [[after.to_dict(), ACTION.to_dict()]]
    assert captured[-1][1]['failed_attempts'] == []
    with pytest.raises(TypeError):
        client.choose(before, GOAL, [ACTION], history, failed)


@pytest.mark.parametrize('forgery', ['forecast', 'frame_authority', 'action_authority',
                                    'foreign_scope', 'foreign_parent', 'unknown_operation',
                                    'envelope', 'overflow'])
def test_failed_attempts_reject_nonactual_forged_or_foreign_inputs_before_send(forgery):
    before, _ = views()
    prior, action = copy.deepcopy(before), ACTION
    failed = [(prior, action)]
    if forgery == 'forecast':
        failed = [(forecast(prior), action)]
    elif forgery == 'frame_authority':
        prior.verified = True
    elif forgery == 'action_authority':
        action = copy.deepcopy(action)
        object.__setattr__(action, 'verified', True)
        failed = [(prior, action)]
    elif forgery == 'foreign_scope':
        prior = Frame([0], [0.], [[0]], [[0]], ('n0',))
        failed = [(prior, Action('z9', ('n0',)))]
    elif forgery == 'foreign_parent':
        prior.parent[0][1] = 1
    elif forgery == 'unknown_operation':
        failed = [(prior, Action('other', ('n0',)))]
    elif forgery == 'envelope':
        failed = {'verified': True, 'attempts': failed}
    else:
        failed = failed * 257
    client = fake_client(valid_reply())
    sent = []
    client._request = lambda *_args, **_kwargs: sent.append(True) or valid_reply()
    with pytest.raises(ValueError):
        client.choose(before, GOAL, [ACTION], failed_attempts=failed)
    assert sent == []


def test_real_process_only_explicit_failed_attempts_affect_repeat_penalty():
    before, _ = views()
    other = Action('z9', ('n1',))
    with Client('relational', schema=SCHEMA, horizon=1, limit=16,
                revisit_penalty=.2) as worker:
        initial = worker.snapshot()
        assert worker.choose(before, GOAL, [ACTION, other])[0] == ACTION
        # A prior action in learning history says nothing about its actual
        # result. Do not infer a failed attempt from the next pre-state.
        assert worker.choose(before, GOAL, [ACTION, other], [(before, ACTION)])[0] == ACTION
        assert worker.choose(before, GOAL, [ACTION, other], [(before, ACTION)],
                             failed_attempts=[(before, ACTION)])[0] == other
        assert worker.snapshot() == initial


def test_real_process_requires_strict_failed_attempt_request_field():
    before, _ = views()
    with Client(schema=SCHEMA, horizon=1, limit=16) as worker:
        request = {'frame': before.to_dict(), 'goal': GOAL.to_dict(),
                   'actions': [ACTION.to_dict()], 'history': [], 'budget': worker.budget}
        with pytest.raises(ValueError, match='request fields'):
            worker._request('choose', **request)
        request['failed_attempts'] = [[before.to_dict(), {**ACTION.to_dict(), 'verified': True}]]
        with pytest.raises(ValueError, match='serialized action'):
            worker._request('choose', **request)
