# R0 final: feasibility GREEN; no planning capability claim

2026-09-17. Implementation/preregistration commit: `74f77cb`.
One registered native run, no retries or post-result tuning.

## Result

| Frozen predictor | Fresh correct / total | Accuracy |
|---|---:|---:|
| Generic raw-channel comparison search | 128 / 128 | 100% |
| Old Frame majority | 64 / 128 | 50% |
| Search with selected raw channel removed | 64 / 128 | 50% |

32 training transitions, then 128 fresh transitions (64 matched pairs). All eight
registered gates pass. The selected expression is equality of anonymous column 2;
supervisor audit maps that column to `st_ino`. The selection was not hardcoded in
the learner. Native files were kept alive, and training/fresh native IDs are
disjoint. Both members of each matched pair have identical original Frames and
opposite observed collateral effects. Both cases have matching native link counts
(2 through 5), so merely having multiple links is not the answer.

Before every native dispatch the raw observation, prediction and before evidence
were flushed to the event journal. Target labels are observed changes to the
other file's SHA-256, not caller `verified` flags or generator class labels.
An independently implemented read-only verifier (no candidate imports) checked
all 160 raw rows, chronological journal pairing, predictions, native files after
execution, train/fresh ID disjointness, source hashes and metric arithmetic: PASS.
This is local trusted-supervisor evidence, not external attestation.

Run wall time 1.426951600 s, supervisor CPU 0.84375 s. These are a tiny cohort's
measurement, NOT a whole-Mind efficiency comparison.

## Tests and preservation

New focused tests: 12 passed, including actual native side effects, reversed target
role, malformed/caller-metadata input rejection and channel permutation.
Broader tests: **335 passed, 1 failed, 2 skipped**. The failure is
`TransferHarnessTests.test_wrong_independent_digest_does_not_spawn_or_consume_attempt`:
old transfer evaluator raises its already-expired 2026-09-14T11:19:00 UTC hard cap
before the expected digest error. The identical failure was reproduced on the
unchanged D4 `62ed442` worktree. No deadline or test was weakened. Full suite is
NOT described as green. Both JUnit files are preserved beside raw evidence.

No changes to `packages/action_core` or `packages/shared_world` versus D4. Main
Claude repository untouched. Production OFF; no push. Native roots retained at
`D:/ATANOR-experiments/temp/atanor_r0__55rs007` (temporary storage, not guaranteed
permanent); raw journal/rows/trained model/report are committed under
`evidence/r0-v1/`, so their record does not depend on keeping the original output
directory. Native byte readback requires retained roots; do not call hashes alone
proof that those files still exist.

Report SHA-256:
`da86c75f55c5cee1d914bf432907244c7bfcf81a586aead4342b1cd8d38ffa11`

Rows SHA-256:
`fd5384d1a808121bdf3974b726d283a78a006fa98f38fd4d09b55fc119f9ba83`

Events SHA-256:
`60f039c6a8471df6df2c1355fcc344aa8a3ce7bcc95e37ea127e7bb987933874`

## What this actually changes

It establishes a concrete blind spot in the D4 observation contract and shows a
very cheap candidate remedy at the SENSOR/FEATURE level. We should not spend
40-80 hours building an elaborate feature invention engine for this particular
counterexample: simple feature search already solves its outcome discrimination.

The sensor upgrade is supplied by humans, and exposes native file identity. Thus
this does NOT demonstrate spontaneous invention of object identity, superiority
over simple search, self-chosen experiments, new mechanics, planning improvement,
the August LinkGraph gate being repaired, or AGI. It is not a statistical estimate
over real-world tasks. The grammar/target/cohort are designed by the developer.

## The actual next bottleneck (not implemented here)

The shared learner's `_bindings` and `_features` enumerate only `parent`/`equal`.
`Frame`, `Forecast`, persisted observations and the worker boundary encode that
fixed vocabulary. Appending an inode test beside the planner would create another
side organ, not repair the shared world. Encoding identity as content equality or
parent would silently change existing semantics and is rejected.

The coherent next unit is an explicit, versioned relation channel in the shared
world, usable by generic effect induction AND imagined rollouts. Real observations
must remain distinct from predictions. The relation's future state must be learned
from native transitions, not assumed forever constant: rename/unlink/copy can
invalidate a relationship. No `if hardlink` branch or handwritten safe-action
policy belongs in the cognition code.

Proposed next bounded gate: on fresh tasks, an induced relation changes a complete
plan and raises independently verified task success/reduces collateral damage,
versus the SAME learner/planner with that relation removed. Include interventions
that invalidate it and controls where extra features provide no advantage. Charge
learning, search and actions. Compare to the simple R0 feature search rather than
claiming novelty from a complicated implementation.

Rough implementation/diagnostic estimate: 8-16h, checkpoint 4h, confidence low to
medium; not a claim of guaranteed capability. Exact fresh cohort and numerical
gates must be registered before that measurement, after the observation/dynamics
contract is settled. Stop if success needs domain-specific policies, oracle
future relations, or unsafe weakening of the shared authority boundary. That is
the route to testing a larger leap; R0 alone has not made the leap.
