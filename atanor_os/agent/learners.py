"""Which learner runs: the baseline core (generation-1 closeout core + G + H1), or one of its switch settings.
Chosen by the environment variable ATANOR_LEARNER; one process runs one learner.
The frozen copies of earlier learners (g35-g44) were removed from the current code on 2026-10-28 (ARCHIVE_INDEX.md);
each is at its commit (snapshot FROZEN.txt) and in git history up to e7c4f12c."""
import os


# REBUILD_RESULTS.md stage 5 (2026-11-08): the default is the new decision module without questions (next_noask).
# It passed stages 2-4 of REBUILD_PLAN.md on the final seeds 931-933; questions had no measured effect, so they stay off.
# The baseline core is still ATANOR_LEARNER=current.
DEFAULT = 'next_noask'


def name():
    return os.environ.get('ATANOR_LEARNER', DEFAULT)


def after_course(world_dir, mind_dir, body, seed):
    """What a learner does between a course and its evaluation: next_explore practises in lab copies of a practice world
    of its body (rebuild/practice.py, EXPLORE_PLAN.md next stage); every other learner does nothing."""
    if name() != 'next_explore':
        return None
    from ..rebuild.practice import practice
    return practice(world_dir, mind_dir, body, seed)


def make(home, mind_dir, **kw):
    from .grounding import Grounder
    if name() == 'core':                                   # CLOSEOUT_CHECK_PROTOCOL.md: generation 1 + the capability fix
        return Grounder(home, mind_dir, **kw, modifier_slot=False)
    if name() == 'core_m':                                 # ... + the modifier-slot rule
        return Grounder(home, mind_dir, **kw, modifier_slot=True)
    if name() == 'g57':                                    # GEN3_H1_PROTOCOL.md: the current core without H1
        return Grounder(home, mind_dir, **kw, same_doing=False)
    if name() in ('next', 'next_nolab', 'next_noask', 'next_explore'):       # REBUILD_PLAN.md stage 4: the new decision module
        from ..rebuild.learner import NextGrounder
        return NextGrounder(home, mind_dir, **kw, lab=name() != 'next_nolab', ask=name() not in ('next_noask', 'next_explore'))
    if name() != 'current':
        raise ValueError(f'unknown learner {name()!r}: frozen copies live at their commits (ARCHIVE_INDEX.md)')
    return Grounder(home, mind_dir, **kw)
