"""Which learner runs (DESK_EVAL2_PROTOCOL.md): the current one, or the frozen generation-1 copy for comparison.
Chosen by the environment variable ATANOR_LEARNER ('g35' or 'g36' for a frozen copy); one process runs one learner."""
import os


def name():
    return os.environ.get('ATANOR_LEARNER', 'current')


def make(home, mind_dir, **kw):
    if name() == 'g35':
        from .grounding_g35 import Grounder
        kw.pop('caps', None)                               # generation 1 granted itself the body's capabilities
    elif name() == 'g36':
        from .grounding_g36 import Grounder
    else:
        from .grounding import Grounder
    return Grounder(home, mind_dir, **kw)
