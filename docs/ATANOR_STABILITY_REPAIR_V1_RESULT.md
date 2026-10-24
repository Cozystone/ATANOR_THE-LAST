# Stability repair v1: REPAIR_NO_GO

2026-09-20. Frozen e6eeec9 before one76.612s execution. Isolated research only.
Rollback7941319. No production, graph, staging or prior Self changes; no push.

## Candidate and scope
Frozen A teacher, eight evenly spaced actual autobiographical replay anchors,
unit-weight KL preservation term added to original plastic weights+Adam updates.
No law-conditioned learner, probe training, oracle unchanged-transition mask or
new primitive. This is limited anchoring, NOT a complete fast/slow consolidation
architecture. Extra teacher memory and eight anchor evaluations per update cost
more compute. No coefficient/anchor sweep. Exposed six-law/eight-history panel,
not fresh validation. Only prediction snapshots persisted; teacher+anchor resume
is not implemented or claimed. Original80% adequacy gate retained unchanged.

## Results
| Metric | Original weights+Adam | Anchored candidate |
|---|---:|---:|
| Mean capped acquisition score |4.7917|4.4583|
| Median |4|4|
| Post16 unchanged-transition macro accuracy |16.73%|22.09%|
| Previously correct predictions lost, denominator396 |234|200|

Both start at39.19% retention accuracy. Original baseline predictions reproduced
exactly on1152 probe rows; candidate disk reload identical on1152 rows. New cost
score remains below6 and severe-negative-transfer gates pass. Macro preservation
(no more than2pp loss) and each-law preservation (no more than5pp loss) FAIL.
All original three retention gates still FAIL. Thus REPAIR_NO_GO, not breakthrough.
Frozen teacher tensors remain exact and gradient-free; unchanged source hashes.

Per-law retention before -> after:
- unique_link60.42% ->68.33%
- broadcast_unlink16.37% ->15.48%
- steal_link41.07% ->11.25%
- attached_insert27.60% ->32.81%
- cleanup_delete20.94% ->4.69%
- parent_insert68.75% ->0%

Independent raw-count audit:1088 paired common transition probes,196 kept correct,
200 correct->wrong,48 wrong->correct,644 always wrong. Baseline coverage and actual
regression remain distinct defects. Old acquisition score uses17 for censored
after16; scores are not literal mean sample counts. One zero-shot law remains.

## What this establishes / does not
Sparse teacher anchoring can partly reduce regression without removing adaptation
advantage here, but fails the requested preservation criterion substantially.
It does not establish that all fast/slow designs fail, that more anchors fix it,
or that gradient interference is the only cause. Nor is stability-plasticity the
only remaining AGI problem. No autonomous experience selection, cross-mechanism
transfer or lifelong accumulation established.

Do not sweep regularizer coefficients. Next architectural question is whether a
learned boundary can keep new-law updates local while deciding when old predictions
remain applicable, WITHOUT receiving law IDs or evaluator common masks. That is
an untested research question, not a implemented or guaranteed solution.

Evidence: evidence/stability-repair-v1/{attempt,report,audit}.json,probes.jsonl,
288 predictor checkpoints.11 pre-run tests passed (one candidate invariance test,
ten existing panel/suite tests); not a full repository regression claim.
Stop at this frozen candidate verdict; no retry or production promotion.
