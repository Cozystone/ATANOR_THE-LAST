"""Runner for one course seed on the reef, one of the island's five places: isle_run with this place's name.
Usage: python -m atanor_os.eval.reef_run <seed> <out_dir>
"""
import json
import sys

from . import isle_run


def run(seed, out_dir):
    return isle_run.run('reef', seed, out_dir)


if __name__ == '__main__':
    print(json.dumps(run(int(sys.argv[1]), sys.argv[2]), indent=1))
