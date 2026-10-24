# Plastic life v1 — real bounded task gain; developmental gate NO-GO

2026-09-20. Protocol/candidate frozen in de6b7fc before the only execution.
Read alongside ATANOR_PLASTIC_LIFE_V1_PREREGISTRATION.md. No retuning/rerun.

## Actual result

Each cell is successes / 16 paired held-out tasks, then mean penalized actions.
Failure at32 actual actions costs33; successful episodes cost their actual actions.
Four independent initial model/life seeds, four tasks each. These are NOT 144
independent tasks: the same held-out task instances recur in checkpoint branches.
Canonical life never sees their observations, goals, updates or evaluation results.

| Life actions | Fresh | Passive random life | Internally selected life |
|---|---|---|---|
| 0 | 1/16;32.50 | 1/16;32.50 | 1/16;32.50 |
| 256 | 1/16;32.50 | 2/16;29.75 | 3/16;29.75 |
| 1024 | 1/16;32.50 | 16/16;4.6875 | 16/16;4.4375 |

This is task capability, unlike the previous +158 ancillary-field result. Every
life at1024 beats its fresh control. Four-node actual training supports later
five/six-node actual goal solving, without operation-effect rules in the learner.
All groups can continue learning during the task; unknown predictions never veto
externally permitted sandbox actions. Success is actual SQLite state, not model
confidence, a predicted trace or a caller assertion.

It is NOT evidence of learning-to-learn across new dynamics. New tasks use the
SAME SQLite laws. Better prior knowledge/model alone can explain the benefit.
No separate zero-shot vs adaptation ablation; no learned representation causality
or autonomous concept birth asserted. No LLM/pretrained weights. Human priors
remain: sensor coding, graph architecture, supervised update rule, one-step goal
selection, fixed exploration heuristic. Not a completed persistent AGI Self.

## Why the preregistered verdict remains NO-GO

- Active vs random cost gain only5.33%, below frozen20% requirement.
- Per-life active/random total task costs:16/18,22/23,15/15,18/19. One tie violates
  strict benefit in every life. Random experience already solves all16 tasks.
- Age256 active successes3, below required4 for nonvacuous retention gate. All
  three ARE retained (lost successes0); do not misreport this as observed forgetting.
- Fresh-cost lift, age improvement, success comparison, native replay, persistence
  and source integrity gates pass. Failed gates are not relaxed post hoc.

Therefore retain the learned-dynamics capability finding but reject an assertion
that this uncertainty-driven developmental candidate is superior. No immediate
second-mechanism run under this protocol. Do not extend life length until GREEN.

## Costs and actual trace

Per-arm lifetime learning:4096 actions total across four lives. CPU totals through
age1024: passive31.359375s, active34.828125s. Active additionally queries the ensemble
for16 actions each step (196608 model/action forecasts across four lives). Checkpoint
verification adds48 reported queries per life; it is not learned experience.
Latest16 task CPU totals: fresh4.71875s, passive0.734375s, active0.703125s. Timing is
single-run descriptive and noisy, not hardware/general efficiency benchmark.
Lifetime cost exceeds savings on these16 tasks: no total-compute break-even claim.
Whole experiment wall107.568s,4 test passes before execution. No GPU required.

Real example life0/task0/active1024, new n5 body:
- Initial kinds[1,2,1,1,1], desired[0,1,1,1,0].
- Unlink row1 -> [1,1,1,1,1], native accepts.
- Delete anchor0 -> [0,1,1,1,1], native accepts.
- Attempt link row1 -> unchanged, native rejects (exploration wastes one action).
- Delete row4 -> [0,1,1,1,0], goal observed, stop after4 actions.
Operator names here decode opaque action IDs for the human reader. No such solution
was supplied to the learner. Do not hide the failed action to make trace look better.

## Integrity and preservation

evidence/developmental-plastic-life-v1/ contains original attempt, report, all144 task
episode traces (including pre-action predictions),8192 chronological lifetime
events,16 serialized checkpoints and audit.json SHA256 manifest.11788 actual
transitions independently reexecuted against new SQLite bodies. Source hashes
unchanged. Checkpoint reload forecasts equal; unit test checks optimizer/RNG and
next-update equivalence. Separate raw audit verifies counts, goals, action lengths,
continuity and headline aggregates without trusting report success flags.
Learned whole-state argmax correctness on chosen age1024 transitions: passive62/75,
active61/71. These DIFFERENT action trajectories do not establish comparative model
accuracy. Task success is not perfect prediction or epistemic calibration.

Main repository, existing203-record Self, production defaults and graph unchanged.
Research branch only; no push. Rollback boundary994016c; research freeze de6b7fc.

## Next decision, not implemented

Do not add more curiosity organs on this evidence. The cheap random-experience
control is a serious baseline, not an inferior method to discard. A subsequent
distinct protocol should separate retained knowledge from improved adaptation:
same learning algorithm and matched budget on changed native mechanics, with
fresh/passive-trained controls and causal learned-state ablation. Only then can
we say history makes a BETTER LEARNER rather than a better-informed controller.
The current result warrants preserving the substrate, not proclaiming a new Mind.
