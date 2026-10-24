# R1 final — bounded native planning capability GREEN

2026-09-17. Candidate/preregistration `4dbd05a`. One registered attempt, no retries.

| Arm | Native task success | Any collateral sibling change | Actions |
|---|---:|---:|---:|
| Induced relation ON | 64/64 | 0/64 | 96 |
| Same learner/planner, relation OFF | 32/64 | 32/64 | 96 |

Success lift +0.50; paired block bootstrap one-sided 95% LCB +0.50. All 32 blocks
contain the same two structural conditions, so this interval describes this narrow
randomized-instance generator, NOT uncertainty over new mechanics or AGI.
Independent-copy controls: both arms 32/32. All 12 registered gates pass, including
all native replays, frozen inner models, budget bounds and exact predicted relation
changes at every ON executed step. Same action count, different action quality.

Worker OS CPU: ON 114.609375s, OFF 112.578125s. Parent episode CPU: ON 13.171875s,
OFF 10.8125s; separate verification parent CPU: ON 2.109375s, OFF 1.875s. Trial wall
276.5187214s. ON does not demonstrate lower total compute here. Training supplied
the same 176 native transitions to both arms, and R0 discovery/data collection is
additional prior work, not free experience. No energy-efficiency claim.

## What is genuinely integrated

Native observation -> explicit additional relation channel -> common role binding
and learned joint effects -> common hypothetical rollout -> common planner -> JSON
worker -> persistent WorldSession -> native action -> independent native replay.
No hardlink-specific branch was put in the learner or planner. R0's simple selected
comparison is a bound sensor projection. Future relation values are learned, not
copied as immutable identity facts. Legacy empty-relation view serialization is
preserved. New views/goals are versioned; old model checkpoints are not silently
reinterpreted as the new learned relation format.

## Actual episode: r1-2, target n0

1. Three file locators have the same original contents. n0/n1 refer to one native
   object; n2 is a protected independent reference. Goal: n0 empty, n1 preserved.
2. Before acting, the learned model distinguishes the relation and predicts the
   unlink branch with the n0 relation row/column removed.
3. Planner chooses `unlink(n0)`. Native result: n0 absent, n1 still original.
4. Planner chooses `empty(n0)`. Native result: a new empty file at n0, n1 and n2
   retain exact original bytes. The new relation state is independently observed.
5. Supervisor stops `goal_reached` at 2 actions. Native reexecution agrees.

This is a learned change to action sequence, not just another classifier score.
On the matched OFF alias cases, truncating first destroys the sibling's original
bytes; 2 actions cannot satisfy the registered task in the measured executions.

## Verification / regression

The exact broad-suite result is **342 passed, 1 failed, 2 skipped**.
The one failure remains the previously reproduced expired Sept14 transfer-evaluator
deadline test. No new failing test. Seven new relation-channel tests pass, covering
native effect change, checkpoint replay, channel-preserving branch merging,
unknown vocabulary/caller fields, protected-alias denial, size goals, subprocess
execution and rejection of a wrong externally supplied sensor configuration.

Development probe v1 stopped when its reporting code tried reading a deleted
sibling (legitimate baseline failure). Only the DEV reporter was corrected to
count missing files as failure; v2 is explicitly DEV, not a retry of fresh v1.

The frozen evaluator reexecuted all 128 episodes. A second stdlib-only verifier,
with no ATANOR imports, reconstructed every initial configuration from the
registered RNG, replayed actual native actions, checked journal hash chains,
compared native observations and exact bytes, and recomputed scores/bootstrap:
**128/128 PASS**. It was written outside the candidate tree during execution.
Local trusted-host evidence, not independent personnel or external E5.

## Evidence

`evidence/r1-sealed/` preserves report, raw rows, independent checker/result and
an archive of all 128 SQLite journals. 130 persistent archive files were compared
byte-for-byte to raw output: all match. SQLite transient SHM/empty WAL files also
occur in the archive; all archived WAL files are zero length and are not independent
experimental records. Temporary native roots may later be removed by the OS;
registered initial bytes/actions and SQLite journals preserve replay information.

- report SHA256: `148b0080aae880b4134c00485948c718a503a52489bb5f0d1dfac5c87db98501`
- raw rows SHA256: `195de6c17759cd573c8a6211880897da2a5c0195569c67814b69958746636daf`
- archive SHA256: `67f12639c26959b0080c3c2fceb08546ee44ab70f3887bfea22151d649c298b9`

Main/Claude repository unchanged, D4/R0 worktrees preserved. Production OFF; no push.

## Boundary and next bottleneck

Fresh INSTANCES, not unseen mechanics. Privileged stat sensor and grammar are
human-supplied; R0 learned one comparison. Task goals and experience collection
are operator-selected. Vocabulary is fixed per trained model. This does not show
arbitrary concept invention, autonomous experiments, lifelong ontology change,
multiple bodies, or AGI/ASI.

Next coherent question: can conflicting actual experience itself trigger a
representation proposal, with independent validation and provenance-preserving
replay, rather than an operator manually picking the new channel? Do not count
renaming a hand-selected relation as autonomous birth. A failed proposal must not
change authoritative observations or be promoted by its own claimed score.
