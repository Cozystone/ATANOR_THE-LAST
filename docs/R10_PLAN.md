# R10 — current-state experiment synthesis

Authorized goal begins 2026-09-19T09:39:51Z. Eight-hour feasibility decision due
2026-09-19T17:39:51Z; hard cap 2026-09-21T01:39:51Z (40 elapsed hours).
Base: 5a93b338a37260aad54175122b9eb612870d2604. Separate local branch/worktree;
main ATANOR and all R0–R9 source/evidence remain unchanged. No push, activation,
new model organ, domain-specific solver, or central LLM.

## Prior-attempt census

All local branches/logs/stashes in the D repository checked before starting.
R0–R9 branches exist; no R10/menu-free experiment synthesis commit found; stash
list empty. R4 improved prediction but hurt utility. R6 intermediate coverage
failed fresh. R8 actual discrimination gained accuracy but lost economy. R9
stopping changed no behavior and added CPU. Do not retune those heuristics.
Main-repo repair work is unrelated and is not merged here.

## Required difference, not an easier substitute

Candidate receives current observed Frame, opaque operation schema, permitted
actions/handles, actual history, learned model and task goals. It does NOT receive
a catalog of resettable experiment states. It constructs bounded action sequences
using the existing predictor/planner/effect-hypothesis machinery. After each
real action it reobserves and replans. Forecasts are hypotheses only, never learner
rows. Native supervisor alone authorizes operations and checks outcomes.
If the reusable engine cannot support this within the cap, report no-go rather
than reverting to menu selection and calling it synthesis.

## Numerical decision contract (fixed before candidate implementation)

- Four arms: synthesis; online task learning with no extra exploration;
  random current-state exploration with the same maximum action budget;
  unchanged R8 menu-based discrimination plus online task learning.
- Fresh cohort: 8 paired blocks × 8 tasks × 4 arms. Same initial model/experience,
  task order, native starting configurations and task completion predicates per
  block; arm order counterbalanced. Cluster bootstrap over 8 blocks, 10,000 draws.
- Acquisition cap 32 native actions/block, task-plan execution cap 2/task for all
  arms. Candidate/random may use acquisition allowance only on current native
  states; no uncharged candidate rollback/reset. Every executed exploration or
  repair action is charged, including failed actions.
- Accuracy: candidate success >=87.5%; lift over no-extra-exploration >=25pp with
  one-sided 95% bootstrap LCB >=10pp; noninferiority to random/menu LCB >=-5pp.
- Economy: total native actions/success at least 10% below EVERY comparator;
  one-sided 95% upper bound of paired block-bootstrap ratio <=1.00 against each.
  Undefined denominator (no successes) is reported explicitly, not silently
  removed; no-success comparator has infinite actions/success.
- Compute: whole-arm CPU/success point ratio <=1.25 against each successful
  comparator; wall time, peak memory and setup/reset/verification cost reported
  separately. No artificial action↔CPU conversion. Overall success requires
  accuracy AND economy AND compute, not accuracy alone.
- Hard gates: no candidate reads of native truth, no action-ID special cases,
  protected data preserved, strict action/query budgets, actual-only training,
  pre-action predictions recorded, source/data hashes unchanged, native replay
  and numerical recomputation independently checked.
- New seeds of known hardlink mechanics are NOT unseen-mechanics transfer.
  Transfer remains UNMEASURED unless a separately specified structurally new
  body/effect is included before freeze; do not add one post-result for a win.

## Implementation/measurement boundary

First inspect R5/R8 runner, actual acquisition/reset accounting, model hypothesis
API and supervisor. Write a feasibility result by 8h. Before implementing any
candidate, fix current-state/goal schedule and query caps in a protocol addendum;
the numerical gates above cannot be softened. Before fresh execution, commit a
new immutable registration with candidate/source/schema hashes, explicit cohort
generation seed, outcome schema, cost denominators, bootstrap code and exclusive
attempt marker. No fresh result inspection before freeze. One attempt only;
partial/crashed attempts remain evidence and cannot be silently retried.

DEV is exposed and separate; no inference of capability from unit tests. If a
feasibility/no-go decision stops the unit, preserve evidence and explain remaining
requirements. No invented success probability or AGI completion statement.

Rollback: do not merge; base commit above and previous worktrees remain intact.
Commit each coherent change locally. No reset/overwrite of original artifacts.

## Status

Plan and prior-attempt inspection only. No candidate implementation, no new
capability execution, no transfer claim. Next: inspect actual run_arm in
scripts/representation_r5_dev.py and establish current-state sequence feasibility.
