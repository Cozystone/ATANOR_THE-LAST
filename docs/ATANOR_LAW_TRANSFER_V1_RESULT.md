# Native law transfer v1 — reusable capability, rapid law-acquisition NO-GO

2026-09-20. Freeze5b363aa before ONE execution; candidate remains de6b7fc.
Original result, preregistration and all old life checkpoints remain unchanged.

## What was actually changed

Original real SQLite FK refuses deleting a referenced parent. B1 uses native
ON DELETE SET NULL; B2 native ON DELETE CASCADE. All operator implementation
inherited unchanged. Initial sensor frames exactly equal across laws; no law ID
or solution enters learner. Four original random-life1024 checkpoints vs same-seed
Fresh; both receive identical random actual B transitions at ages0,8,32,128,512.
Retain A weights, Adam and replay; reset only per-body working activation.
This tests current continuation contract, not an isolated transfer mechanism.

32 unique held-out tasks total across2laws/4seeds, half changed-consequence goals
and half general goals. Each repeated on disposable copies at5ages and2arms:
320 episodes, NOT320 independent tasks. Online task learning allowed/counts included.
No task observations/results returned to canonical B life. Probe before task learning
separately predicts exactly the newly changed native deletion consequence.
Age0 means no B PRE-TRAINING, not strictly zero-shot entire task execution.

## Outcome split

**Task reuse POSITIVE; rapid new-law acquisition gate NO-GO for BOTH laws.**
Across five ages (equal-weight mean, not linear-time AUC), failure penalized33:

| Law | Fresh mean task cost | Experienced | Changed-cohort fresh | Changed-cohort experienced |
|---|---:|---:|---:|---:|
| SET NULL |20.6500|5.1250|16.675|2.650|
| CASCADE |24.6250|5.2375|22.375|3.225|

All four lives show lower changed-cohort cost for experienced. But goals can be
solved by old transferable procedures, or exploratory actions, WITHOUT correctly
predicting the changed law. Cost lift is NOT enough to establish law-learning speed.

General+changed task successes /16 (Fresh -> Experienced):

| B pre-experiences | SET NULL | CASCADE |
|---|---|---|
|0|4 ->15|2 ->15|
|8|4 ->16|1 ->16|
|32|5 ->15|3 ->16|
|128|8 ->15|5 ->15|
|512|14 ->15|14 ->15|

Exact NEW-law whole-state prediction /16 on frozen pre-task probes:

| B pre-experiences | SET NULL Fresh -> Experienced | CASCADE Fresh -> Experienced |
|---|---|---|
|0|0 ->0|0 ->0|
|8|0 ->0|0 ->4|
|32|4 ->0|0 ->2|
|128|4 ->0|0 ->6|
|512|4 ->16|12 ->16|

All32 experienced entry probes predict old A law correctly, new B law incorrectly.
Thus real law conflict verified. Experienced reaches75%new-law accuracy only at512
for BOTH laws. Fresh reaches75%at512 forCASCADE, never within512 forSETNULL.
Report513 for never is a censoring sentinel, NOT an executed513-experience result.
Frozen gate requires experienced strictly earlier thanFresh AND <=128. Both fail.
Other gates pass. Do not relax timing or re-label overall asPASS because cost isgood.
SETNULL late accuracy advantage is a bounded positive observation, not rapid-transfer
proof. Nonmonotonic curves and final15/16 prevent claims of perfect/sustained mastery.

## Concrete actual episodes and cheap retrospective diagnosis

At entry CASCADE/life0/task0: initial[1,1,1,1,2], desired[0,1,1,1,0]. Experienced
deletes row4, then anchor0: two successful actions using an old-law-compatible path.
Native B could achieve same goal with one parent delete. Task success alone would
falsely suggest B understanding. SETNULL/life0/task0 instead takes parent delete
immediately and succeeds, despite its separate pre-action probe predicting refusal.
Exploration/action choice and accurate world prediction are not interchangeable.

Post-hoc raw-only exposure_diagnosis.json (no extra candidate run): random training
provides only0..2 direct law-changing parent-deletion events per life by128 steps;
2/4 SETNULL lives and1/4 CASCADE lives have ZERO such events by128. At512 there are
5..6 SETNULL or4..5 CASCADE events/life. Both comparators saw identical events.
This explains limited opportunity; it does NOT causally isolate stale A replay,
optimizer inertia, working-state reset, or representational limitations. A model
architecture ceiling and a project-wide no-go are NOT established.

## Costs / integrity / preservation

8192 B training transitions +4344 task transitions =12536 independently replayed
actual SQLite transitions. Raw audit recomputed every headline and gate, verified
paired training identity and source SHA256.80 checkpoints saved, reload forecasts
equal.7 unit tests pass (4 old learner tests,3 native-body witnesses). Wall139.525s.
Fresh has3 fewer optimizer steps on its firstB event because replay is empty;
same algorithm afterward, no claim exactly identical optimizer workload.
B training CPU seconds (four lives total): SETNULL fresh17.84375/experienced17.390625;
CASCADE fresh17.5625/experienced17.078125. All5age task CPU: SETNULL16.8125/4.390625;
CASCADE19.09375/4.3125. Single-run timings noisy; source A experience has additional
1024actions and prior training cost/life, not a total lifetime break-even claim.

Law variants are closely related; no broad unseen-mechanism/meta-learning claim.
New-body hidden reset is retained from candidate: how to preserve context across
bodies/law changes remains unresolved. No autonomous concept creation/RSI claim.
Main repository, prior203-recordSelf, production defaults unchanged; no push.
Evidence: evidence/developmental-law-transfer-v1/{attempt,report,audit,
exposure_diagnosis}.json plus rawJSONL/checkpoints. No retries/retuning.

## Next decision (not executed)

Keep reusable learned dynamics; do not call it a better learning algorithm yet.
Cheapest discriminating next experiment would match informative actual law-change
events, not just total random actions, and compare their learning effects under a
new preregistration. That is a controlled diagnostic, not a manufactured capability
win. Only after that can replay conflict vs genuinely slow adaptation be isolated.
No curiosity module, replay purge, further512+ training or world rewrite performed.
