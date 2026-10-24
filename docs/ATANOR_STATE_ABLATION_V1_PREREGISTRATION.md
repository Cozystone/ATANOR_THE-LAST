# Persistent-state ablation v1 — exposed-cohort diagnostic ONLY

User approved six arms.1h total budget, single execution10min cap. No new native
mechanism, capability pilot or architecture edits. Candidate remains de6b7fc.
Same original four passiveA1024 checkpoints; exact counterexample-v1 trials,
probes, counts0/1/2/4/8 and stable acquisition threshold reused unchanged.
Exposed cohort for cause exploration, NOT a fresh held-out replication claim.

## Interventions fixed before outcomes

- Fresh: original same-seed initialization.
- Full: original complete Experienced checkpoint, original RNG/history included.
- Weights: learned model tensors only; initial Adam/empty replay/initial RNG.
- Replay: initial weights/Adam with old replay INCLUDING detached hidden caches
  and its old sampler RNG. Not pure raw-data-only intervention.
- Optimizer: initial weights/empty replay/initial RNG with old Adam moments/steps.
  Artificial transplant, not a naturally aligned optimizer continuation.
- Head reset: all learned tensors except output.weight/output.bias reset to
  same-seed initial values; initial Adam/empty replay/initial RNG. All tensors
  remain trainable, no frozen encoder. Not proof of semantic abstraction.

Bookkeeping counters fresh exceptFull; counters never affect update algorithm.
Body working hidden resets identically. Fresh/weights/optimizer/head-reset have
45 optimizer steps at8, replay/full48 due original first-update replay behavior.
No changes to original learn/forecast logic or old artifacts. Composition unit
test verifies exact chosen components, no alias mutation and all states runnable.

## Fixed reporting / gates

Fresh andFull ALL320 probability vectors must exactly reproduce previous diagnostic,
not just thresholds. Any mismatch: stop and report instrumentation inconsistency.
Every arm predicts same native actual counterexamples and same held-outinstances,
no probe teaching; source/oldcheckpoint hashes invariant and restart forecasts equal.

Primary per-law stable acquisition unchanged: >=75%changed-consequence exact and
>=50%perlife at a sampled count and ALL remaining checkpoints through8. None is
censored/unknown, not equality. Report whole-state results and individual lives.
SETNULL observed benefit retained by arm if threshold<=4 and<Fresh8; report each
arm without selecting or tuning a winner. Cross-law behavior reported separately.
Single-component sufficiency here is NOT necessity, exclusive causality or proof
of representation invention. Head-reset failure could be output relearning cost;
optimizer transplant failure not proof optimization irrelevant. If no singlearm
retains effect, interactions remain possible, not identified by this nonfactorial
design. No pairwise component combinations added after outcome.

Independent raw aggregate/threshold audit, native witness replay, retained original
control comparisons. Save all traces/checkpoints. No push/main/production changes.
Stop after diagnosis; a genuinely new cohort needed before broader validation.
