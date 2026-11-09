"""Live one life: python -m atanor_os.life.run <self_dir> --seed N [--bodies b ...] [--sessions K] [--until-stage M]
Each stage runs in a process of its own. Run it again (after a stop or a kill) and the same life continues.
--one-stage: this process lives the next stage and exits (what the loop below runs).
"""
import argparse
import subprocess
import sys

from .host import BODIES, Life

DEV_SEEDS = range(1, 6)


def one_stage(a):
    life = Life(a.self_dir, a.seed, list(a.bodies), a.sessions)
    n = life.next
    if a.until_stage is None or n < a.until_stage:
        done = life.run_stage()
        print('over' if done is None else f'stage {done}', flush=True)
    life.close()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('self_dir')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--bodies', nargs='+', default=list(BODIES), choices=BODIES)
    ap.add_argument('--sessions', type=int, default=15)
    ap.add_argument('--until-stage', type=int, default=None, help='stop before this stage')
    ap.add_argument('--one-stage', action='store_true')
    a = ap.parse_args(argv)
    if a.seed not in DEV_SEEDS:
        ap.error('this step is development: seeds 1-5 only')
    if a.one_stage:
        return one_stage(a)
    while True:
        cmd = [sys.executable, '-m', 'atanor_os.life.run', a.self_dir, '--seed', str(a.seed), '--bodies', *a.bodies,
               '--sessions', str(a.sessions), '--one-stage'] + ([] if a.until_stage is None else ['--until-stage', str(a.until_stage)])
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode:
            sys.stderr.write(p.stderr)
            return p.returncode
        if p.stdout.strip() in ('over', ''):
            return 0
        print(p.stdout.strip(), flush=True)


if __name__ == '__main__':
    sys.exit(main())
