# Plastic life v1 — fixed before execution

Question: does continuously updated shared learned dynamics plus internally
selected experience improve later task adaptation over fresh and equally old
random-experience controls? This is a bounded candidate test, not a promise of
self-organizing AGI, learned curiosity, novel primitive invention or RSI.

## Frozen protocol

Four initial random model seeds/lives 610000..610003. Native in-memory SQLite
body n4, prefill2; passive random / developing ensemble disagreement selection.
No pretrained weights, task solutions, semantic action rules or curated lessons.
Human priors: categorical sensor3, schema/actual relation channels, message sums,
GRU width24, three models, Adam0.003, changed/unchanged-balanced supervised loss,
replay capacity256 (one old plus newest event). Full actual life archived.
Per-body hidden activation reset on moving bodies; weights/replay/optimizer persist.
Stale detached replay activations and one-step control are explicit limitations.

Ages0,256,1024; equal actual lifetime actions and learning update counts per arm.
At each age four held-out tasks per life: seeds720000+100*life+task, n5/n6
alternating, prefill1+task//2, native fk_goal(seed+30000,n). Same tasks across ages
are read-only retention measurements. Evaluation checkpoint branches adapt online,
but none of their experience, results or goals returns to canonical life. Fixed
future evaluation is NOT curiosity reward. All arms same goal policy: epsilon0.2,
otherwise maximum predicted fraction of goal kinds. Cap32 actions, failure cost33.
Already satisfied initial goals retained in denominator; no task filtering.
Counterbalanced arm order; all native transitions independently reexecuted.
Pre-action predictions logged. Goal may select action, never enters dynamics/loss.

## Gates, without post-result interpretation changes

All mandatory for BOUNDED_DEVELOPMENTAL_PASS:
- source SHA256 stable, native observation/acceptance replay exact, checkpoint
  serialization restores identical forecasts (unit test covers next-update parity);
- age1024 developing mean penalized actions at least20% below BOTH fresh/passive;
- strict cost advantage over each comparator separately in EACH of four lives;
- developing successes no fewer than either comparator (16 paired tasks total);
- age1024 developing cost at least10% below own age256 cost;
- at least4 successful age256 tasks; no previously successful task lost at1024.

No statistical population claim from four lives. Report all counts and costs,
including additional active-selection computation, failed actions, lifetime learning
and eval learning. Action efficiency does NOT prove total lifetime compute savings.
One exclusive attempt directory, source freeze commit before run, no retries or
retuning after outcomes. Wall hard cap30min. No different-mechanism test on failure.
No claim positive result identifies representation versus data-selection causality:
that requires a separately approved ablation. Existing production unchanged/OFF.
