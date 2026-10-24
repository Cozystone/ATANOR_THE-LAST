"""JSON learner process with explicit algorithm/frozen bindings.

This is API/process separation, NOT an OS sandbox or hostile-worker attestation.
CPU is measured by this local request wrapper, never supplied by a model result;
it is not independently authenticated against a compromised worker process.
Native observations, completion, permissions and time availability remain the
supervisor's responsibility. The frozen wrapper cannot update its inner model.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from packages.action_core.planner import Goal
from packages.action_core.retrieval import Retrieval
from packages.action_core.schema import bind_schema
from packages.action_core.world import Action, Frame
from .contracts import parse_prediction
from .full_context import FullContextLearner, MODEL_FORMAT as FULL_FORMAT
from .relational import RelationalLearner, FORMAT as RELATIONAL_FORMAT


FORMAT = 'shared-world-worker-v1'
ALGORITHMS = ('relational', 'full_context', 'retrieval')
SNAPSHOT_FIELDS = {'format', 'algorithm', 'frozen', 'revision', 'seen', 'model'}
FRAME_FIELDS = {'kinds', 'sizes', 'equal', 'parent', 'handles', 'relations'}


def _fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(f'unexpected {label} fields')


def _frame(frame):
    if type(frame) is not Frame or set(vars(frame)) != FRAME_FIELDS:
        raise ValueError('only exact observed Frame fields are supported')
    return Frame.from_dict(frame.to_dict())


def _action(action, frame, schema):
    if type(action) is not Action or set(vars(action)) != {'op', 'args'}:
        raise ValueError('only exact Action fields are supported')
    schema.index(action)
    if any(handle not in frame.handles for handle in action.args):
        raise ValueError('action reference outside observed scope')


def history_dump(history):
    if type(history) not in (list, tuple):
        raise ValueError('history must be a sequence of observed frame/action pairs')
    result = []
    for pair in history:
        if type(pair) not in (list, tuple) or len(pair) != 2:
            raise ValueError('invalid observed history pair')
        observed = _frame(pair[0])
        if type(pair[1]) is not Action or set(vars(pair[1])) != {'op', 'args'}:
            raise ValueError('invalid history action')
        result.append([observed.to_dict(), pair[1].to_dict()])
    return result


def history_load(value):
    if type(value) is not list or any(type(p) is not list or len(p) != 2 for p in value):
        raise ValueError('invalid observed history structure')
    return [(Frame.from_dict(f), Action.from_dict(a)) for f, a in value]


def _failed_attempts(value, frame, schema):
    """Validate supervisor-supplied observed no-effect attempts, not infer them.

    Only the supervisor can compare the actual before/after Frame AND native
    evidence. These pairs carry no independent attestation. In particular, a
    later history entry's pre-state must never be treated as an earlier result.
    """
    attempts = history_load(history_dump(value))
    if len(attempts) > 256:
        raise ValueError('failed-attempt record budget exceeded')
    for before, action in attempts:
        _action(action, before, schema)
        if before.handles != frame.handles or before.parent != frame.parent:
            raise ValueError('failed attempt outside observation scope')
    return attempts


def _transition(before, action, after, history, schema):
    before, after = _frame(before), _frame(after)
    _action(action, before, schema)
    if before.handles != after.handles or before.parent != after.parent:
        raise ValueError('transition observation scope changed')
    history = history_load(history_dump(history))
    for past, previous in history:
        _action(previous, past, schema)
        if past.handles != before.handles:
            raise ValueError('history observation scope changed')
    return before, action, after, history


def _algorithm(snapshot):
    if type(snapshot) is not dict:
        raise ValueError('model checkpoint must be a mapping')
    if snapshot.get('algorithm') == 'relational' and snapshot.get('format') == RELATIONAL_FORMAT:
        return 'relational'
    if snapshot.get('algorithm') == 'neural' and snapshot.get('format') == FULL_FORMAT:
        return 'full_context'
    if snapshot.get('algorithm') == 'retrieval' and 'format' not in snapshot:
        return 'retrieval'
    raise ValueError('foreign model format/algorithm')


def _events(seen, revision):
    if (type(seen) is not list or any(type(v) is not str or not v for v in seen) or
            len(set(seen)) != len(seen) or type(revision) is not int or revision != len(seen)):
        raise ValueError('invalid seen/revision binding')


def _check_raw(snapshot, algorithm, schema):
    if _algorithm(snapshot) != algorithm or bind_schema(snapshot.get('schema')).to_data() != schema.to_data():
        raise ValueError('checkpoint differs from bound algorithm/schema')
    _events(snapshot.get('seen'), snapshot.get('revision'))
    if algorithm == 'relational':
        _fields(snapshot, {'algorithm', 'format', 'schema', 'partitioned', 'max_records', 'max_rules',
                           'max_depth', 'updates', 'revision', 'seen', 'rows'}, 'relational checkpoint')
        if type(snapshot['partitioned']) is not bool:
            raise ValueError('invalid partitioned-effect checkpoint mode')
    elif algorithm == 'full_context':
        _fields(snapshot, {'algorithm', 'format', 'schema', 'weights', 'revision', 'updates',
                           'change_balanced', 'latest_update', 'rng', 'seen', 'replay'},
                'full-context checkpoint')
    if algorithm == 'retrieval':
        _fields(snapshot, {'algorithm', 'schema', 'revision', 'seen', 'rows'}, 'retrieval checkpoint')
        if type(snapshot['rows']) is not list or len(snapshot['rows']) != min(512, snapshot['revision']):
            raise ValueError('invalid retrieval replay size')
        for row in snapshot['rows']:
            _fields(row, {'before', 'action', 'after', 'history'}, 'retrieval transition')
            _transition(Frame.from_dict(row['before']), Action.from_dict(row['action']),
                        Frame.from_dict(row['after']), history_load(row['history']), schema)


def _check_wrapped(value, algorithm, frozen, schema):
    _fields(value, SNAPSHOT_FIELDS, 'worker checkpoint')
    if (value['format'] != FORMAT or value['algorithm'] != algorithm or
            type(value['frozen']) is not bool or value['frozen'] != frozen):
        raise ValueError('worker checkpoint algorithm/frozen binding mismatch')
    _events(value['seen'], value['revision'])
    _check_raw(value['model'], algorithm, schema)
    inner_seen, outer_seen = set(value['model']['seen']), set(value['seen'])
    if not inner_seen <= outer_seen or (not frozen and inner_seen != outer_seen):
        raise ValueError('worker/model revision binding mismatch')


def _fresh_model(algorithm, seed, updates, schema, change_balanced, latest_update):
    if algorithm == 'relational':
        return RelationalLearner(seed=seed, updates=updates, schema=schema)
    if algorithm == 'full_context':
        return FullContextLearner(seed=seed, updates=updates, schema=schema,
                                  change_balanced=change_balanced, latest_update=latest_update)
    if algorithm == 'retrieval':
        return Retrieval(schema=schema)
    raise ValueError('unknown model algorithm')


def _restore_model(snapshot, algorithm, schema):
    _check_raw(snapshot, algorithm, schema)
    factory = {'relational': RelationalLearner, 'full_context': FullContextLearner, 'retrieval': Retrieval}[algorithm]
    return factory.restore(snapshot)


class ModelState:
    """Explicit frozen wrapper. Revision acknowledges observations, not training."""
    def __init__(self, algorithm, frozen, schema, *, seed=1, updates=1,
                 change_balanced=False, latest_update=False):
        if (algorithm not in ALGORITHMS or type(frozen) is not bool or type(seed) is not int or
                type(updates) is not int or updates < 0 or
                type(change_balanced) is not bool or type(latest_update) is not bool):
            raise ValueError('invalid model arm binding')
        self.algorithm, self.frozen, self.schema = algorithm, frozen, bind_schema(schema)
        self.model = _fresh_model(algorithm, seed, updates, self.schema, change_balanced, latest_update)
        self.seen, self.revision = set(), 0

    def predict(self, *args, **kwargs):
        return self.model.predict(*args, **kwargs)

    def learn(self, event_id, before, action, after, history):
        if type(event_id) is not str or not event_id:
            raise ValueError('event identity must be a nonempty string')
        before, action, after, history = _transition(before, action, after, history, self.schema)
        if event_id in self.seen:
            return False
        if not self.frozen:
            previous = self.model.revision
            accepted = self.model.learn(event_id, before, action, after, history)
            if accepted is not True or self.model.revision != previous + 1:
                raise ValueError('model failed observation revision contract')
        # Frozen: do not call inner learn, so weights, rules, RNG and replay stay
        # fixed for every algorithm, including nearest-neighbour retrieval.
        self.seen.add(event_id)
        self.revision += 1
        return True

    def snapshot(self):
        return {'format': FORMAT, 'algorithm': self.algorithm, 'frozen': self.frozen,
                'revision': self.revision, 'seen': sorted(self.seen), 'model': self.model.snapshot()}

    def restore(self, snapshot):
        # Wrapped checkpoints must retain the explicit frozen binding. A normal
        # base can initialize a frozen arm only by explicitly importing its raw
        # ['model'] snapshot into that already frozen Client.
        if type(snapshot) is dict and snapshot.get('format') == FORMAT:
            _check_wrapped(snapshot, self.algorithm, self.frozen, self.schema)
            raw, seen, revision = snapshot['model'], snapshot['seen'], snapshot['revision']
        else:
            _check_raw(snapshot, self.algorithm, self.schema)
            raw, seen, revision = snapshot, snapshot['seen'], snapshot['revision']
        model = _restore_model(raw, self.algorithm, self.schema)
        self.model, self.seen, self.revision = model, set(seen), revision


def _budget(value):
    _fields(value, {'horizon', 'width', 'limit', 'revisit_penalty'}, 'planning budget')
    if (any(type(value[k]) is not int or value[k] <= 0 for k in ('horizon', 'width', 'limit')) or
            type(value['revisit_penalty']) not in (int, float) or
            not math.isfinite(value['revisit_penalty']) or value['revisit_penalty'] < 0):
        raise ValueError('invalid planning budget')
    return value


def serve():
    state = None
    previous_cpu = 0.  # Include initial imports/startup in the first response.
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            if type(request) is not dict or type(request.get('request_id')) is not int:
                raise ValueError('invalid request envelope')
            request_id = request['request_id']
            command = request.get('command')
            fields = {
                'init': {'algorithm', 'frozen', 'seed', 'updates', 'schema', 'change_balanced', 'latest_update'},
                'restore': {'snapshot'}, 'snapshot': set(),
                'learn': {'event_id', 'before', 'action', 'after', 'history'},
                'choose': {'frame', 'goal', 'actions', 'history', 'failed_attempts', 'budget'},
            }
            if command not in fields:
                raise ValueError('unknown worker command')
            _fields(request, fields[command] | {'command', 'request_id'}, 'request')
            if command == 'init':
                if state is not None:
                    raise ValueError('worker is already bound')
                state = ModelState(request['algorithm'], request['frozen'], request['schema'],
                                   seed=request['seed'], updates=request['updates'],
                                   change_balanced=request['change_balanced'], latest_update=request['latest_update'])
                result = True
            elif state is None:
                raise ValueError('worker must be initialized')
            elif command == 'restore':
                state.restore(request['snapshot'])
                result = True
            elif command == 'snapshot':
                result = state.snapshot()
            elif command == 'learn':
                result = state.learn(request['event_id'], Frame.from_dict(request['before']),
                                     Action.from_dict(request['action']), Frame.from_dict(request['after']),
                                     history_load(request['history']))
            else:
                from .planning import choose
                budget = _budget(request['budget'])
                frame = Frame.from_dict(request['frame'])
                failed_attempts = _failed_attempts(history_load(request['failed_attempts']), frame, state.schema)
                action, forecast, nodes = choose(state, frame,
                    Goal.from_dict(request['goal']), [Action.from_dict(a) for a in request['actions']],
                    history_load(request['history']), failed_attempts=failed_attempts, **budget)
                result = {'action': action.to_dict(), 'forecast': forecast.to_dict(), 'nodes': nodes}
            # Serialize result inside the measured boundary too; stdout timing
            # and the following wrapper bookkeeping appear in the next delta.
            json.dumps(result, allow_nan=False)
            response = {'ok': True, 'result': result}
        except Exception as error:
            response = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        current_cpu = time.process_time()
        response.update(request_id=request_id, worker_cpu_seconds=max(0., current_cpu - previous_cpu))
        previous_cpu = current_cpu
        print(json.dumps(response, allow_nan=False, separators=(',', ':')), flush=True)


class Client:
    def __init__(self, algorithm='relational', *, seed=1, updates=1, schema=None,
                 frozen=False, timeout=60, horizon=2, width=8, limit=4096, revisit_penalty=.2,
                 change_balanced=False, latest_update=False):
        if (algorithm not in ALGORITHMS or type(frozen) is not bool or type(seed) is not int or
                type(updates) is not int or updates < 0 or
                type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0 or
                type(change_balanced) is not bool or type(latest_update) is not bool):
            raise ValueError('invalid worker configuration')
        self.algorithm, self.frozen, self.schema = algorithm, frozen, bind_schema(schema)
        self.timeout = timeout
        self.budget = _budget({'horizon': horizon, 'width': width, 'limit': limit,
                              'revisit_penalty': revisit_penalty})
        self.worker_cpu_seconds, self._next_request = 0., 0
        self._closed = False
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        self.process = subprocess.Popen([sys.executable, '-B', '-m', 'packages.shared_world.worker'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[2], env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._output, self._errors = queue.Queue(), []

        def read_output():
            for item in self.process.stdout:
                self._output.put(item)
            self._output.put(None)

        def read_errors():
            for item in self.process.stderr:
                self._errors.append(item)
                self._errors[:] = self._errors[-20:]

        self._threads = [threading.Thread(target=read_output, daemon=True),
                         threading.Thread(target=read_errors, daemon=True)]
        for thread in self._threads:
            thread.start()
        try:
            if self._request('init', algorithm=algorithm, frozen=frozen, seed=seed,
                             updates=updates, schema=self.schema.to_data(), change_balanced=change_balanced,
                             latest_update=latest_update) is not True:
                raise ValueError('invalid initialization acknowledgment')
        except Exception:
            self.close()
            raise

    def _exchange(self, request):
        if self._closed:
            raise RuntimeError('worker is closed')
        try:
            self.process.stdin.write(json.dumps(request, allow_nan=False) + '\n')
            self.process.stdin.flush()
            line = self._output.get(timeout=self.timeout)
        except (queue.Empty, BrokenPipeError, OSError) as error:
            self.close()
            raise RuntimeError('learner timeout/pipe failure') from error
        if line is None:
            raise RuntimeError('learner exited: ' + ''.join(self._errors))
        return json.loads(line)

    def _request(self, command, **fields):
        request_id = self._next_request
        self._next_request += 1
        response = self._exchange({'command': command, 'request_id': request_id, **fields})
        if type(response) is not dict or type(response.get('ok')) is not bool:
            raise ValueError('invalid worker reply envelope')
        expected = {'ok', 'request_id', 'worker_cpu_seconds', 'result' if response['ok'] else 'error'}
        _fields(response, expected, 'worker reply')
        cpu = response['worker_cpu_seconds']
        if (type(response['request_id']) is not int or response['request_id'] != request_id or
                type(cpu) not in (int, float) or not math.isfinite(cpu) or cpu < 0):
            raise ValueError('invalid reply request/timing binding')
        self.worker_cpu_seconds += cpu
        if not response['ok']:
            if type(response['error']) is not str:
                raise ValueError('invalid worker error value')
            raise ValueError(response['error'])
        return response['result']

    def choose(self, frame, goal, actions, history=(), *, failed_attempts=()):
        frame = _frame(frame)
        if type(goal) is not Goal or set(vars(goal)) != {'id', 'kinds', 'equal', 'sizes', 'relations'}:
            raise ValueError('goal must have the exact Goal type')
        goal = Goal.from_dict(goal.to_dict())
        goal.validate_handles(frame.handles)
        if type(actions) not in (list, tuple) or not actions:
            raise ValueError('explicit nonempty action surface required')
        for action in actions:
            _action(action, frame, self.schema)
        failed_attempts = _failed_attempts(failed_attempts, frame, self.schema)
        reply = self._request('choose', frame=frame.to_dict(), goal=goal.to_dict(),
            actions=[a.to_dict() for a in actions], history=history_dump(history),
            failed_attempts=history_dump(failed_attempts), budget=self.budget)
        _fields(reply, {'action', 'forecast', 'nodes'}, 'choice result')
        action = Action.from_dict(reply['action'])
        forecast = parse_prediction(reply['forecast'])
        if (action not in actions or type(reply['nodes']) is not int or
                not 0 < reply['nodes'] <= self.budget['limit']):
            raise ValueError('invalid learner action or planning count')
        if (forecast.handles != frame.handles or forecast.parent != frame.parent or
                forecast.relations.keys() != frame.relations.keys()):
            raise ValueError('forecast observation scope/reference mutation')
        return action, forecast, reply['nodes']

    def learn(self, event_id, before, action, after, history=()):
        before, action, after, history = _transition(before, action, after, history, self.schema)
        result = self._request('learn', event_id=event_id, before=before.to_dict(),
            action=action.to_dict(), after=after.to_dict(), history=history_dump(history))
        if type(result) is not bool:
            raise ValueError('invalid learn acknowledgment')
        return result

    def snapshot(self):
        value = self._request('snapshot')
        _check_wrapped(value, self.algorithm, self.frozen, self.schema)
        return value

    def restore(self, snapshot):
        if type(snapshot) is dict and snapshot.get('format') == FORMAT:
            _check_wrapped(snapshot, self.algorithm, self.frozen, self.schema)
        else:
            _check_raw(snapshot, self.algorithm, self.schema)
        if self._request('restore', snapshot=snapshot) is not True:
            raise ValueError('invalid restore acknowledgment')

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=10)
        for thread in self._threads:
            thread.join(timeout=2)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            pipe.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


if __name__ == '__main__':
    serve()
