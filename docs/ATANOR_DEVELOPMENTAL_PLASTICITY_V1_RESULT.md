# Developmental plasticity panel v1: acquisition gains, retention failure

2026-09-20. Protocol, environment suite and runner frozen in b92ba90 before the
only execution. Original learner unchanged. Verdict: **PLASTICITY_NO_GO**.

## What was tested

Six new, curated native SQLite laws; prior SET NULL and CASCADE excluded from
primary statistics and retained only as exposed controls. Eight new initializations
and 1,024-action A histories (830200..830207). Fixed weights+Adam configuration vs
same-seed Fresh. Identical directed actual counterexamples, counts0/1/2/4/8/16.
No per-law learning algorithm, optimizer or feature modifications. Law-specific
SQL constraints/triggers and contrast fixtures belong to the environment only.
This is a related-law panel, NOT representative sampling over arbitrary worlds.

New primary acquisition requires exact WHOLE successor, not just changed cells,
>=75% overall and >=50% each life, sustained through remaining sampled counts.
Per-life cost requires>=75% of four probes, similarly sustained. Censoring after16
scored17 as a FIXED FAILURE PENALTY, not seventeen observed necessary examples.
Equal weights across six laws/eight lives. Case shapes/laws correlated; no broad
statistical population confidence asserted. Evidence is deliberately provided.

## Acquisition results

Mean penalized acquisition cost per life:

| New law | Fresh | Weights+Adam |
|---|---:|---:|
| Unique link capacity |16.00|2.25|
| Broadcast unlink |0.75|0.00|
| Transfer reference ownership |16.75|11.00|
| Automatically attach inserted row |16.875|2.00|
| Delete child and clear parent/references |16.875|9.00|
| Parent insertion links existing rows |8.00|4.50|
| **Panel mean** |**12.5417**|**4.7917**|
| **Panel median** |**16**|**4**|

All six law means and all eight history means improve. Severe negative-transfer
cells0/48 under frozen definition (>2x Fresh AND at least4 more); no severe law
mean. Selected model crosses the per-life criterion within16 in all48 cells;
Fresh has **20 censored cells**:6 ownership +7 attached-insert +7 cleanup,
with no other censored new-law cells. These failures are included using the
frozen17 penalty, not treated as successes.

Broadcast unlink is already predicted correctly BEFORE B experience. This is
zero-shot compatibility, NOT evidence of faster updating in that law. Initial A
knowledge can be imperfect/overgeneralized. Do not label every low acquisition
cost as improved learning dynamics. Other five laws still show lower mean costs,
but this panel does not isolate learning algorithm improvement from useful priors.

## Why the complete gate is NO-GO

Retention tested only shared A/B actions with IDENTICAL actual outcomes/acceptance
and a real state change; no-op predictions cannot inflate preservation.
Contradicted A truths not required to coexist with B truths. Identical probes
before and after16 B counterexamples, case/law-equal macro accuracy:

| New law | Before B | After16 B |
|---|---:|---:|
| Unique link |60.42%|36.67%|
| Broadcast unlink |16.37%|11.61%|
| Ownership transfer |41.07%|12.50%|
| Attached insert |27.60%|34.90%|
| Cleanup delete |20.94%|4.69%|
| Parent insert |68.75%|0.00%|
| **Macro mean** |**39.19%**|**16.73%**|

Frozen80% baseline adequacy, <=5pp macro loss and <=10pp any-law loss all FAIL.
The baseline already has poor coverage on these broader common transitions;
do NOT describe every post-training error as loss of previously mastered knowledge.
Separate matched raw diagnostic (not a new gate):1,088 transition-probe pairs,
162 stayed correct,234 went correct->wrong,24 wrong->correct,668 stayed wrong.
Thus **234 of396 previously correct predictions are lost**; a real predictive
regression exists independently of poor baseline coverage. These are test cases,
not396 distinct concepts/skills. No operational task regression measured here.

All six acquisition/negative-transfer gates PASS, all three retention gates FAIL.
Whole-state retention cannot be replaced with aggregate new-law gains. No threshold
adjustment, replay intervention, consolidation module or extra training attempted.

## Scope and decision

Keep narrow observation: fixed learned state supplies useful adaptation priors
across this finite SQL panel, without major primary-cost negative transfer here.
Reject stronger claim: broadly beneficial developmental plasticity with retained
knowledge. The effect is not just one SET NULL result, but it is also NOT a clean
continual-learning solution. There are TWO deficits: weak initial generalization
on the retention probe family, plus measured regression on previously correct
transitions during new-law learning. Exact causes not isolated by this experiment.
Selected arm excludes old replay by earlier sufficiency result; that never proved
replay unnecessary for long-term preservation. Do not infer an architectural fix
from this observation alone or repeat Adam component ablations.

## Evidence integrity

23 unit tests passed before freeze. One run165.177s.8,192 actual A transitions
independently reexecuted;1,024 shared new-law counterexamples,3,072 raw probe rows,
1,280 complete native A/B case/action catalogs independently reconstructed;
776 checkpoints (8A +768readouts). Restart forecasts exact; source hashes stable.
Independent raw audit recomputed all predictions, unchanged-transition membership,
acquisition/censoring scores, medians, negative transfer and retention gates.
Raw artifact manifest in audit.json; retrospective paired counts separately in
retention_diagnosis.json. Evidence under developmental-plasticity-panel-v1/.

Main repository, prior203-recordSelf, existing graph and production defaults
unchanged. No push. Rollback f40963f before this unit. Prior results preserved.
Stop at the approved panel conclusion; no new architecture or further blind search.
