"""Pre-run validity check of the P8b drift (true models only; no learned representation is evaluated)."""
import pathlib
import tempfile

from atanor_os.eval.p8b import DRIFT, DriftOracle, _run, _set_drift, drift_task, situation_agreement

root = pathlib.Path(tempfile.mkdtemp())
for body in ('fs', 'view'):
    ok_new = ok_old = 0
    for t in range(20):
        ws, goal, meta = drift_task(body, t, root / f'{body}_n{t}')
        ok_new += _run(ws, goal, DriftOracle(body, DRIFT[body]), root / f'{body}_n{t}.sqlite', t, meta)['completed']
        ws2, goal2, meta2 = drift_task(body, t, root / f'{body}_o{t}')
        _set_drift(ws2, frozenset())
        ok_old += _run(ws2, goal2, DriftOracle(body, frozenset()), root / f'{body}_o{t}.sqlite', t, meta2)['completed']
    print(body, 'drift tasks: changed world + true model', ok_new, '/20 | original world + original model', ok_old, '/20')
    for name, m in (('true-new', DriftOracle(body, DRIFT[body])), ('true-old', DriftOracle(body, frozenset()))):
        a = situation_agreement(m, body, DRIFT[body], True, 20, 1, root / f'sa_{body}_{name}', set())
        b = situation_agreement(m, body, DRIFT[body], False, 20, 2, root / f'sb_{body}_{name}', set())
        print('  ', name, 'changed situations', a['checks'], round(a['accuracy'], 3), a['cells'],
              '| unchanged', b['checks'], round(b['accuracy'], 3), b['cells'])
