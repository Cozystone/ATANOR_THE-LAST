# Final two pairs + fresh-history validation: localized replication, overall NO-GO

2026-09-20. Stage1 design inclconditionalStage2 frozen95be43a. Stage1 result and
selectedStage2runner frozen23dc103. Original learner unchangedde6b7fc. Each ONE run.
No extra combinations, no retrospectivegatechanges, no newmechanismrun.

## Stage1 — last two combinations, exposed cohort

| Arm | SETNULL stableacquisition | CASCADE stableacquisition |
|---|---:|---:|
| Fresh |8|4|
| Full |4|4|
| Weights+oldAdam, nooldreplay |4|4|
| Weights+oldreplay, freshAdam |8|4|

Weights+Adam reproduces4 inALL4SETNULLlives, CASCADEperlife[4,2,2,2] matchingFull.
Weights+Replay SETNULL[8,8,8,8]. Fresh/Fullprobabilityvectors320exactpriorreplication.
Frozen selection rule choosesweights_adam. Replay NOT required for this observed
speedbenefit; prior inference that ENTIREFullstate was necessary was premature.
This identifies a sufficient bundle undertestedinterventions, not solemechanistic
cause nor novellearnedalgorithm. WhichAdamcomponents matter remainsunidentified;
no furthermicro-ablationmatrix authorized/performed. Wholelifelongreplayutility
cannot be rejected on this result. Stage1 wall57.074s; independentrawauditPASS.

## Stage2 — new randomA lives and initializations

Eight NEW seeds810100..810107, each1024actualrandomA actions. OriginalAcheckpoints
not reused. Selectedconfigurationfixed BEFORE newlifedata/results. Fresh/Full/
weights_adam, two laws, sameprovidedcounterexample schedule0/1/2/4/8,32probes each.
Probe geometries samefamily/oftenisomorphic; thisis newHISTORY/INITIALIZATION
replication, not newmechanismor autonomous evidencegathering. No tasksolving here.

### SETNULL: narrow positive replicated

| Counterexamples | Fresh changed/full correct | Full changed/full | Weights+Adam changed/full |
|---|---|---|---|
|0|0/32|0/32|0/32|
|1|5/32|0/32|0/32|
|2|3/32|0/32|0/32|
|4|0/32|30/32|32/32|
|8|24/32|32/32|32/32|

Fresh aggregate stabilitygate NOT reachedwithin8 dueperlife floor;24/32 alone is
insufficient. IndividualFresh[None,8,8,None,8,8,None,8],Full[4,4,8,4,4,4,4,4],
selected[4,4,4,4,4,4,4,4]. Selected earlier in8/8lives, including3censoredFresh.
Do notconvertcensoring to observed9orclaimexact2xrate fromsparsecheckpoints.

### CASCADE: primary speednoninferiority FAILS

Primary changed-consequence thresholdFresh2,Full4,selected4. Gate requiredselected
no laterthanFreshandFull. Failurepreserved. At2,Fresh32/32changed but16/32whole;
selected28/32changed and28/32whole. At4,Fresh32/32changed but0/32whole; selected
32/32both. At8,Fresh32/32changed and13/32whole; selected32/32both.
Differentmetrics favor differentarms. Retainedknowledge remainsuseful but doesNOT
overridepreregisteredprimaryspeedfailure. No posthocclaimchangedmetricdoesn'tcount.

AllotherfrozenvalidationgatesPASS: SETNULLfast,Freshnotbefore8,>=6livesimprove,
nonelifesloweronSETNULL,whole@8noninferiorbothlaws. OverallVALIDATION_NO_GO.
Thus localizedSETNULLadaptationpositive survivesnewhistories; generalnondegrading
two-lawadaptationclaimnotestablished. Newcohort lackedweights-only/Adam-only arms,
so it validatesselectedbundle'seffect, notindependentlyre-establishingallcomponent
causalcomparisons. Exposedcohortcomponentinference remainslimitedaccordingly.

## Integrity/cost/scope

Stage1:640rawprobes,64sharedactualcounterexamples,160checkpoints,96nativeunique
A/Bwitnessreexecutions,rawmetricsandthresholdsaudited. No oldartifactoverwritten.
Stage2:8192actualAlearningtransitionsindependentlyreplayed;128actualBcounterexample
events shared by3arms;960rawprobes,248checkpoints(8A+240B),192uniqueB/Awitness
configurationsreexecuted. Snapshotreloadforecastsidentical; sourcehashesinvariant.
13unit testsPASS includingpaircomposition,selectionpriority,validationgates.
Independentrawauditorverifiedall6validationgatesandheadlines. Wall118.289s.
Checkpointlearningcosts included via fulltraces; no energy/compute-efficiencyclaim.
Candidatearchitecture,mainrepo,old203recordSelf,production unchanged; no push.

Evidence: evidence/developmental-pair-isolation-v1/ and developmental-fresh-history-v1/
originalattempt/report, rawtraces, learnedcheckpoints, independentauditSHA256manifest.
Rollbackfe78302beforethisunit. PreviousNO_GO/positivefindingsretained.

## Decision

Stopcomponentcombinationshereasrequested. Keepweights+Adam as a bounded research
candidate, NOT a productionupgradeoruniversallysuperiorlearner. No replayremoval
fromworkingATANOR. Futuredifferent-law/mechanismtest needs its own fixedprotocol,
withboth changed-part andcomplete-stateerrors visible; not anothersearchonthis
exposedcohort untilGREEN. NeitherAGI,recursiveimprovementnorconsciousnessclaimed.
