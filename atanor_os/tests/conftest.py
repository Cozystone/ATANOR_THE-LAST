import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    for m in ('learning: learner-performance assertion (not part of a run\'s validity gate)',
              'timing: wall-clock dependent process test (not part of a run\'s validity gate)',
              'fs: filesystem-body specific', 'view: view-body specific'):
        config.addinivalue_line('markers', m)
