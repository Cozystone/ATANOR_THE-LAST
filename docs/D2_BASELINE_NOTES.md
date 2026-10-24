# D2 sufficient-action-context neural baseline

This is a synthetic-verified implementation candidate, not a capability result.
No fresh cohort, native environment, hyperparameter sweep, old-checkpoint migration,
or production activation is part of this change.

## Exact information-path change

The legacy role vector has 25 observed features per node: kind/size, supplied
parent and equality summaries, and relationships to the action arguments. Its
nodewise GRU can miss context surrounding a different argument. The new input is:

`own role[25] + argument-0 role[25] + argument-1 role[25] + opaque operation[4]`.

Absent argument slots are zero-filled. The new input width is 79 rather than 29.
Each argument's full existing context is broadcast to every output node; no new
sensor information is introduced. The supplied maximum arity remains two. All
operation identifiers use the same feature and model code. No operation-specific
precondition or effect is encoded.

Three recurrent members, width 24, output heads, SGD learning rate 0.04, clipping,
legacy change-balanced/latest-update options, replay sampling, history length 3,
and the 512-transition replay limit are preserved. The extra 50 GRU inputs add
10,800 parameters across three members. Thus this is **not parameter/compute
matched** to the old predictor. Any later comparison must disclose parameter count,
training exposure, update budget and measured compute; a widened local-only
predictor is a distinct possible compute-capacity control, not implemented here.

## Interface and boundary

`FullContextLearner` / `Learner` retain `predict`, `learn`, `snapshot`, `restore`.
Prediction accepts exact `Frame` observations and exact `Forecast` hypotheses for
rollouts. Learning and supplied history accept only the observed `Frame` shape.
Unknown operations, wrong arities/handles, extra attributes, augmented histories,
unsupported checkpoint fields/formats and nonfinite/shape-invalid weights fail
closed. Empty prediction action lists retain the old `[]` behavior.

These are shape/schema checks, **not evidence authentication**: a caller can still
construct an apparently valid Frame from invented or future values. The external
body/journal must bind its actual source and time. The baseline receives no goal,
native success bit, path, future observation, or filesystem capability through its
prediction interface. It does not independently prove history chronology.

The baseline still has the legacy fixed Frame view and marginal kind/size/equality
outputs, copies supplied parent relations, and does not solve joint-effect
consistency, changing referents, unbounded history, or autonomous concept invention.
Object reindexing is equivariant only when every relation, action reference and
history frame is reindexed consistently; argument positions are not interchangeable.

## Checkpoints and evidence

Format: `full-action-context-v1`. The architecture is randomly initialized and
rejects the old format; it must be trained afresh on the preregistered common data.
JSON round-trip checks cover weights, replay, RNG state and continued learning.
No optimizer momentum exists in the inherited SGD configuration.

Synthetic tests use opaque operation labels. They prove that the formerly hidden
third-object parent context can affect another argument's output, not that the
network has learned a correct operation. They also cover node/history permutation,
schema-name opacity, forecast separation, exact restore/continued updates, malformed
or extra future data, and absence of native/file access during model operations
after framework initialization. They do not constitute a hostile-process sandbox.

Run only this test file with the isolated repository as `--confcutdir`, Python
`C:/ProgramData/miniconda3/python.exe -B`, and TEMP/TMP under
`D:/ATANOR-experiments/temp`. Keep capability claims pending the separately approved
same-data measurement; this implementation does not execute it.

## Local synthetic verification, 2026-09-13

Initial run: 14 passed in 7.81 seconds. Final run: **16 passed in 3.76 seconds**.
The added contract checks make the parameter delta and duplicate-event binding
rejection explicit. These are repeatable implementation tests, not repeated
capability attempts; no held-out artifact or native environment is opened by this
test file. `git diff --exit-code -- packages/action_core` also reported no legacy
tracked changes at handoff.
