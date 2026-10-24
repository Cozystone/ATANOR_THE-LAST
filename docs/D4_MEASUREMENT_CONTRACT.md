# D4: one local known-mechanics capability comparison

This document precedes the fresh run. Exact candidate/data/environment hashes
and the independent DEV audit are generated into D4_PREREG_V1.json and committed
before execution. The script rejects an uncommitted protocol, changed source,
changed checkpoint, or a second use of the protocol, even with a different output.

## Question and boundary

Does a learned conditional joint-effect model, inside the same persistent
native-action world as the controls, solve subsequent goals at lower cost?
Does retaining online model updates contribute beyond its frozen counterpart?
These are separate claims. There is no AGI, autonomous ontology invention,
new-mechanics transfer, natural-language capability, or RSI claim in this trial.

All learners get the same observations, allowed actions, protected reference,
512 native random-action training transitions, action budget and common planner.
The strong primary comparator is full-action-context neural, updates=3 with
change-balanced/latest-update sampling. It is randomly initialized and locally
trained, **not a commercial/pretrained language model**. Retrieval is a secondary
comparison and cannot replace the primary after seeing results.

## Fixed design

- 64 life clusters, seeds 914800 through 914863. Each arm restarts its own
  pretrained checkpoint for every life; no cross-life evaluation learning.
- Four arms: relational, full_context, retrieval, frozen relational.
- Each life uses one persistent native filesystem across two learning goals
  followed by two evaluation goals. Arm execution order rotates by life index.
- Five supplied locators: immutable reference, parent, nested child, spare,
  auxiliary. Paths, handles and file content vary; parent absent/present is
  balanced. This is new configuration of the same five native operations.
- Goals: child equals reference; move-equivalent conjunction to spare; reverse
  conjunction to child; spare plus auxiliary equal reference with child absent.
  The learner receives only declarative goals, not the hand-written native
  reachability witness that exists solely in tests.
- Eight actual actions per goal, 32 per life. Planning horizon 2, width 8,
  limit 4096 state-action predictions, .2 observed-no-change repeat penalty.
- Failed goals cost eight in the penalized metric, while actual action counts
  remain separately reported. Self-inflicted unreachable states are failures,
  not excluded or repaired by an evaluator. No target is replaced after viewing.

## Numerical decision

Paired life-cluster bootstrap: 4000 draws, PCG64 seed 91377, linear quantiles.
One-sided 95% bounds; all arms are resampled using the same life indices.

| Gate | Fixed threshold |
|---|---|
| Strong baseline validity | At least 50% target success |
| Candidate target success | At least 75% |
| Candidate minus baseline success LCB | At least −5 percentage points |
| Penalized target-action cost ratio | Point ≤.80; UCB ≤.90 |
| Whole-pipeline CPU ratio | Point ≤1.00; UCB ≤1.10 |
| Online contribution | Frozen-minus-online target cost LCB >0; success LCB ≥−5pp |

All utility gates must pass. If utility passes without the online contribution,
the result is PARTIAL_NO_ONLINE_LIFT, not proof of useful continual learning.
Otherwise numerical failure is NO_GO. Invalid inputs/controls are separately
reported, not counted as a scientific negative or repaired by rerunning.

## Evidence and accounting

Predictions stay hypotheses. Completion comes from native bytes/kinds and
protection checks. Every life is independently replayed and its goal/action
counts re-read from the journal. Initial checkpoint binding is checked against
the preregistered raw checkpoint; all frozen inner models must remain identical.
Online/frozen first decisions must match in all 64 lives.

CPU includes local training, acquisition, model restore, interpreter startup,
search, online updates, serialization, native execution/replay, digest checks,
and allocated common execution overhead. Worker time uses the OS process
counter, not a caller's claimed timing. Only final cross-arm bootstrap/report
emission is outside the cutoff; its exclusion is explicit, not called inference.
Development engineering/earlier DEV runs are research costs, not hidden parts
of the per-alternative execution comparison. Peak worker RAM, decision latency,
actual calls and journal size are also recorded; no brain-like energy claim.

The independent DEV audit authenticates outcomes/model bindings and rechecks
arithmetic, not the past OS timing counter. Evaluation is local, by this research
harness; it is not an external E5/E6 judge or evidence of broad generality.
