# Authorized validation — final sealed result

**WHOLE_MIND_V0_VALID_CAPABILITY_FAIL**

Frozen cognition: `a890256`. Protocol/preflight commit: `f112616`.
Worktree: `D:/ATANOR-experiments/2026-09-19/developmental-research`, branch
`codex/whole-mind-integration`. No cognition/bridge/packages changes;8 source
hashes match before/after. Earlier invalid trial remains untouched.

## Valid fixture and native semantics

Actual primitives: `mkdir` calls Path.mkdir; `empty` calls write_bytes(b'');
`unlink` calls Path.unlink. No directory-removal/rename actuator was added.
Exact Founder layout: (1,1,0,0,1,1,0,0) -> (2,0,1,2,2,0,1,2), protected manifest.
Native9-transition preflight + evaluator-only BFS: reachable, shortest10 actions.
Baseline with n7 forced to file:11. Enumerated1770 possible five-action prefixes;
forcing n7 to FILE preserves every still-solvable prefix. Worst recovery12,
verified total bound5+12=17, same34-action cap for all arms. No solution path was
given to the worker. Unsolvable agent-created prefixes were explicitly separated.

## One execution per arm

| Arm | Completed | Final conditions | Actions | No-op actions | n7 recovered | Native replay |
|---|---:|---:|---:|---:|---|---|
| Full |0/1|7/8|34|22|yes|GREEN|
| No memory |0/1|1/8|34|31|no|GREEN|
| No planning |0/1|2/8|34|20|no|GREEN|

All manifests byte-identical. Each arm paused after exactly5 native actions;
evaluator forced n7 to FILE; worker exited cleanly; a different process restored
the same model digest, Self, goal and world. Full represented n7 ABSENT before
and FILE after reobservation, then repaired it to DIRECTORY. One goal per arm.
Observation/result/prediction types stayed separate; saved experience exactly
matches real pre/post records. Preview checkpoint hashes matched before/after.

## First decisive failure

**Action-selection failure: Full's action5 was mkdir(n6), although n6's final
goal was FILE.** This made n6 DIRECTORY, irrecoverable with the frozen actions.
It occurred BEFORE the evaluator's n7 disturbance. Full's exact post-disturbance
state was therefore unreachable because of its own prior choice, not the event;
both controls' exact post-disturbance states were reachable. No fixture repair or
cognition change was used to rescue Full. It eventually satisfied every condition
except n6. The initially reachable mission failed, not the integration plumbing.

## Causal evidence and limits

Same-frame, same-record-prefix read-only decision comparisons reproduced all
recorded Full decisions: removing memory changed20/34 choices; removing planning
changed30/34. No extra native execution or fourth arm. Full's7/8 vs1/8 and2/8 is
a bounded partial-progress advantage, not mission completion or a generality
claim. Memory/planning affected action, but did not prevent an irreversible bad
exploration choice. No Whole Mind V0 success, AGI or consciousness claim.

## Evaluation corrections disclosed

Harness originally stopped immediately at action34 without requesting the normal
terminal check. Frozen verifier correctly rejected its unfinished durable goal.
Original receipts/journals/database snapshots are preserved in each arm's
`pre_finalization/`; original aggregate is `PRE_FINALIZATION_STATUS.json`.
Finalization called only the unchanged supervisor terminal path under guards
forbidding body.step/client.choose: zero new native actions or learning. Appended
only pre_decision OBSERVE, goal_end OBSERVE, GOAL_END; all earlier events/model
states identical. First finalizer expected one observation instead of two and
halted after Full's append; it resumed idempotently without stepping Full again.
These are disclosed harness corrections, not mission retries or cognition tuning.
After finalization the unchanged verifier, with evaluator-only external-event
replay adapter, independently verified all102 native learner actions.

64 focused tests PASS, including native preflight, absent/file/directory external
event replay and zero-action terminal finalization. Not full repository testing.

## Preservation and stop

Evidence: `evidence/whole-mind-v0-valid/`; verdict `FINAL_STATUS.json`.
Raw previews, native final states, interventions, journals, thoughts and receipts
retained. Owned bodies at
`C:/Users/anseo/AppData/Local/Temp/atanor_whole_mind_valid_5ivsbp5e/` may be cleared
by OS cleanup; committed native replay evidence does not depend on their survival.
No active workers. No next experiment, source repair, actuator extension, push or
main merge. Rollback/inspection point remains `a890256`; old results unchanged.
