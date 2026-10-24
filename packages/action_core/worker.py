"""JSON-only learner process. API isolation, NOT an OS security sandbox."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

from .model import Forecast, Learner
from .planner import Goal, choose
from .retrieval import Retrieval
from .world import Action, Frame
from .schema import bind_schema


def history_dump(history):
    return [[f.to_dict(), a.to_dict()] for f, a in history]


def history_load(history):
    return [(Frame.from_dict(f), Action.from_dict(a)) for f, a in history]


def serve():
    model = None
    for line in sys.stdin:
        try:
            request = json.loads(line)
            command = request['command']
            if command == 'init':
                model = Learner(seed=request['seed'], updates=request['updates'], schema=request.get('schema'))
                result = True
            elif command == 'restore':
                algorithm = request['snapshot'].get('algorithm', 'neural')
                if algorithm not in ('neural', 'retrieval'):
                    raise ValueError('unknown checkpoint algorithm')
                model = (Retrieval if algorithm == 'retrieval' else Learner).restore(request['snapshot'])
                result = True
            elif command == 'snapshot':
                result = model.snapshot()
            elif command == 'learn':
                result = model.learn(request['event_id'], Frame.from_dict(request['before']),
                    Action.from_dict(request['action']), Frame.from_dict(request['after']),
                    history_load(request['history']))
            elif command == 'choose':
                a, forecast, nodes = choose(model, Frame.from_dict(request['frame']),
                    Goal.from_dict(request['goal']), [Action.from_dict(a) for a in request['actions']],
                    history_load(request['history']), **request['budget'])
                result = {'action': a.to_dict(), 'forecast': forecast.to_dict(), 'nodes': nodes}
            else:
                raise ValueError('unknown worker command')
            response = {'ok': True, 'result': result}
        except Exception as error:
            response = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        print(json.dumps(response, allow_nan=False, separators=(',', ':')), flush=True)


class Client:
    def __init__(self, *, seed=1, updates=3, timeout=60, horizon=3, width=3, limit=384, uncertainty_weight=0.5, cover_root=False, revisit_weight=0.0, schema=None):
        if type(revisit_weight) not in (int, float) or not math.isfinite(revisit_weight) or revisit_weight < 0:
            raise ValueError('invalid revisit weight')
        self.timeout = timeout
        self.budget = {'horizon': horizon, 'width': width, 'limit': limit,
                       'uncertainty_weight': uncertainty_weight, 'cover_root': cover_root,
                       'revisit_weight': revisit_weight}
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        self.process = subprocess.Popen([sys.executable, '-B', '-m', 'packages.action_core.worker'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[2], env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._output = queue.Queue()
        self._errors = []
        def read_output():
            for line in self.process.stdout:
                self._output.put(line)
            self._output.put(None)
        def read_errors():
            for line in self.process.stderr:
                self._errors.append(line)
                self._errors[:] = self._errors[-20:]
        self._threads = [threading.Thread(target=read_output, daemon=True),
                         threading.Thread(target=read_errors, daemon=True)]
        for thread in self._threads:
            thread.start()
        try:
            self._request('init', seed=seed, updates=updates, schema=bind_schema(schema).to_data())
        except Exception:
            self.close()
            raise

    def _request(self, command, **fields):
        try:
            self.process.stdin.write(json.dumps({'command': command, **fields}, allow_nan=False) + '\n')
            self.process.stdin.flush()
            line = self._output.get(timeout=self.timeout)
        except (queue.Empty, BrokenPipeError, OSError) as error:
            self.close()
            raise RuntimeError('learner timeout/pipe failure') from error
        if line is None:
            raise RuntimeError('learner exited: ' + ''.join(self._errors))
        response = json.loads(line)
        if not response['ok']:
            raise ValueError(response['error'])
        return response['result']

    def choose(self, frame, goal, actions, history=()):
        reply = self._request('choose', frame=frame.to_dict(), goal=goal.to_dict(),
            actions=[a.to_dict() for a in actions], history=history_dump(history), budget=self.budget)
        if set(reply) != {'action', 'forecast', 'nodes'}:
            raise ValueError('caller-supplied authority or extra result fields')
        action, forecast = Action.from_dict(reply['action']), Forecast.from_dict(reply['forecast'])
        if action not in actions or type(reply['nodes']) is not int or not 0 < reply['nodes'] <= self.budget['limit']:
            raise ValueError('invalid learner action or planning count')
        if forecast.handles != frame.handles or forecast.parent != frame.parent:
            raise ValueError('forecast identity/reference mutation')
        return action, forecast, reply['nodes']

    def learn(self, event_id, before, action, after, history):
        return self._request('learn', event_id=event_id, before=before.to_dict(), action=action.to_dict(),
                             after=after.to_dict(), history=history_dump(history))

    def snapshot(self):
        return self._request('snapshot')

    def restore(self, snapshot):
        self._request('restore', snapshot=snapshot)

    def close(self):
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
