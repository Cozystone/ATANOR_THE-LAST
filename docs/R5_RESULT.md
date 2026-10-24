# R5 — DEV NO-GO

2026-09-17, candidate `1390e4e`, exposed seed 44017. Nine selector/coverage tests
passed. One DEV run. Four selected native experiments, then stopped as designed.
8 tasks: collective 4/4, selective 0/4, 12 task actions + 4 acquisition = 16 total.
Cost per success 4.0 versus no-acquisition 3.0. No fresh capability trial.

The stopping heuristic was too shallow: selected operations were empty, unlink,
copy, copy, all from all-file initial states. No experiment covered the absent
state after unlink. A two-action plan needs knowledge of an intermediate world,
not merely coverage of the current one. All failed selective tasks instead tried
empty twice. Preserve this as failure, not a gain from selecting fewer examples.

Next hypothesis, without changing the learned effect algorithm: include typed
one-step predicted states as QUESTIONS for selecting real experiments. They must
never become observed training/memory; only native selected experiment outcomes
may train the learner. This connects existing forward prediction to acquisition.
No new domain solver. R4/R5 evidence remains unchanged in their own worktrees.
