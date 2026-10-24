"""P8b run: learning process, then one separate test process per condition (in parallel), then the verdict.
Usage (repo root): python atanor_os/runs/_scripts/p8b_run.py learn|test|verdict|all"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'atanor_os' / 'results' / 'p8b'
CONDS = ('R1_KEEP', 'R2_P8', 'P8B', 'P8B_NOVERIFY', 'FULL_RAW', 'FULL_STRUCT', 'CASE', 'FIXED')


def git(*a):
    return subprocess.run(['git', '-C', str(ROOT), *a], capture_output=True, text=True).stdout.strip()


def info():
    OUT.mkdir(parents=True, exist_ok=True)
    d = {'source_commit': git('rev-parse', '--short', 'HEAD'),
         'code_dirty': git('status', '--porcelain', '--', 'atanor_os/agent', 'atanor_os/world', 'atanor_os/eval', 'atanor_os/core'),
         'started': time.strftime('%Y-%m-%dT%H:%M:%S')}
    p = OUT / 'run_info.json'
    old = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
    p.write_text(json.dumps(old + [d], indent=1), encoding='utf-8')
    if d['code_dirty']:
        sys.exit(f'refusing to run with uncommitted code changes: {d["code_dirty"]}')
    return d


def learn():
    info()
    t0 = time.time()
    subprocess.run([sys.executable, '-c', 'from atanor_os.eval.p8b import learn; import json; i = learn(); print(json.dumps(i["sizes"]))'],
                   cwd=ROOT, check=True)
    print('learn seconds', round(time.time() - t0))


def test():
    info()
    procs = {}
    for c in CONDS:
        log = open(OUT / f'test_{c}.log', 'w', encoding='utf-8')
        code = (f'from atanor_os.eval.p8b import test, OUT; test({c!r}, OUT / "reps", OUT / "test" / {c!r})')
        procs[c] = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    for c, p in procs.items():
        p.wait()
        print(c, 'exit', p.returncode, flush=True)


def verdict():
    sys.path.insert(0, str(ROOT))
    from atanor_os.eval.p8b import verdict as v
    results = {c: json.loads((OUT / 'test' / c / f'test_{c}.json').read_text(encoding='utf-8')) for c in CONDS}
    li = json.loads((OUT / 'learn_info.json').read_text(encoding='utf-8'))
    overall, per_body = v(results, li)
    (OUT / 'verdict.json').write_text(json.dumps({'verdict': overall, 'per_body': per_body}, indent=1), encoding='utf-8')
    print(overall, json.dumps(per_body, indent=1))


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    for s in (('learn', 'test', 'verdict') if step == 'all' else (step,)):
        globals()[s]()
