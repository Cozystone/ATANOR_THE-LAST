"""Workbench accounting/initial reachability, no evaluation observations."""
import subprocess
import sys

import pytest

from packages.action_core.world import Action, Sandbox
from packages.shared_world.experiment import make_life, native_cpu_seconds, write_new


@pytest.mark.parametrize('ordinal', [0, 1])
def test_initial_goal_sequence_has_native_solution_without_exposing_it_to_learner(tmp_path, ordinal):
    config, goals = make_life(700 + ordinal, ordinal=ordinal)
    body = Sandbox(tmp_path / 'body', **config)
    ref = next(iter(config['protected']))
    target = goals[0].equal[0][1] if goals[0].equal[0][0] == ref else goals[0].equal[0][0]
    parent = next(body.handles[i] for i, row in enumerate(body.observe().parent)
                  if row[body.handles.index(target)])
    alt = next(h for h, k in goals[1].kinds if k == 1)
    aux = next(h for h, k in goals[3].kinds if k == 1 and h != alt)
    if ordinal == 0:
        assert body.step(Action('mkdir', (parent,)))
    assert body.step(Action('copy', (ref, target)))
    assert goals[0].holds(body.evidence())
    assert body.step(Action('rename', (target, alt)))
    assert goals[1].holds(body.evidence())
    assert body.step(Action('rename', (alt, target)))
    assert goals[2].holds(body.evidence())
    assert body.step(Action('rename', (target, alt)))
    assert body.step(Action('copy', (ref, aux)))
    assert goals[3].holds(body.evidence())


def test_artifact_attempt_is_create_only(tmp_path):
    target = tmp_path / 'result.json'
    write_new(target, {'one': 1})
    with pytest.raises(FileExistsError):
        write_new(target, {'two': 2})


def test_os_cpu_counter_survives_process_exit():
    process = subprocess.Popen([sys.executable, '-B', '-c', 'sum(i*i for i in range(100000))'],
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    process.wait(timeout=20)
    assert native_cpu_seconds(process) > 0
