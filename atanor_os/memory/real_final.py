"""N_REAL_BODIES_PLAN.md: the hybrid on fresh course/evaluation seeds of the six bodies, once.
  python -m atanor_os.memory.real_final <cache_dir> <out_dir> --readers name=path ... --seeds 1701 1702 1703
Refuses to run twice into the same out_dir."""
import argparse
import json
from collections import Counter
from pathlib import Path

from . import hybrid, lobo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache')
    ap.add_argument('out')
    ap.add_argument('--readers', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, required=True)
    ap.add_argument('--tau', type=float, default=0.95)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f'{out} exists: this evaluation runs once')
    out.mkdir(parents=True)
    lobo.CACHE = hybrid.CACHE = a.cache
    for spec in a.readers:
        name, path = spec.split('=', 1)
        print('== reader', name, flush=True)
        hybrid.run(argparse.Namespace(reader=path, out=str(out / name), bodies=list(lobo.BODIES), seeds=a.seeds, ks=[10],
                                      taus=[a.tau], votes=[1], selfcal=None, tau_trusted=[]))


if __name__ == '__main__':
    main()
