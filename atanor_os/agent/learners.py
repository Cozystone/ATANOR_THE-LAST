"""Which learner runs (DESK_EVAL2_PROTOCOL.md): the current one, or the frozen generation-1 copy for comparison.
Chosen by the environment variable ATANOR_LEARNER ('g35' ... 'g39' for a frozen copy); one process runs one learner."""
import os


def name():
    return os.environ.get('ATANOR_LEARNER', 'current')


def make(home, mind_dir, **kw):
    if name() == 'core':                                   # CLOSEOUT_CHECK_PROTOCOL.md: generation 1 + the capability fix
        from .grounding import Grounder
        return Grounder(home, mind_dir, **kw, modifier_slot=False)
    if name() == 'core_m':                                 # ... + the modifier-slot rule
        from .grounding import Grounder
        return Grounder(home, mind_dir, **kw, modifier_slot=True)
    if name() == 'g35':
        from .grounding_g35 import Grounder
        kw.pop('caps', None)                               # generation 1 granted itself the body's capabilities
    elif name() == 'g36':
        from .grounding_g36 import Grounder
    elif name() == 'g37':
        from .grounding_g37 import Grounder
    elif name() == 'g38':
        from .grounding_g38 import Grounder
    elif name() == 'g39':
        from .grounding_g39 import Grounder
    elif name() == 'g41':
        from .grounding_g41 import Grounder
    else:
        from .grounding import Grounder
    return Grounder(home, mind_dir, **kw)
