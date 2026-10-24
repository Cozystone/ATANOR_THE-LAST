# R8 — accuracy gain, overall RED because acquisition economy fails

2026-09-17, candidate/preregistration `1a7055f`. One new trial, no DEV retuning or
retry; unchanged eight-task horizon and numerical criteria.

| Arm | Success | Acquisition | Task actions | Actions/success | CPU s |
|---|---:|---:|---:|---:|---:|
| Finite hypothesis discrimination + online | 64/64 | 116 | 96 | 3.3125 | 132.0625 |
| R6 coverage + online | 44/64 | 88 | 96 | 4.181818 | 110.796875 |
| Ordinary work learning, no acquisition | 32/64 | 0 | 96 | 3.0 | 50.765625 |
| Frozen no acquisition | 32/64 | 0 | 96 | 3.0 | 44.671875 |

Accuracy lift versus ordinary work learning .50, paired lower bound .50. Versus
R6+online .3125, lower bound .1875. All success/nonregression/hard evidence gates
pass. Acquisition-charged economy fails (3.3125>3.0); overall verdict remains RED.
This is meaningful narrow task accuracy evidence, NOT combined capability/economy
GREEN. CPU is also higher; no general efficiency claim.

Independent stdlib reexecution of256 tasks/204 acquisition actions passes, including
actual-only pre/post learner rows for online controls, seeded native configurations,
native bytes/relations and arithmetic/LCBs.375 tests pass, one unchanged expired
transfer deadline failure, two skips. No full-suite GREEN or external E5 claim.

Question selection retains query values and detects residual effects, rather than
pretending a role footprint is enough. Still asks about every permitted first and
second action, including knowledge irrelevant to the supplied goal. Next bounded
hypothesis: stop acquisition when the GIVEN goal has an agreeing finite-hypothesis
plan. Do not lengthen the task horizon, lower thresholds, use hidden outcome labels,
or retroactively relabel this result. Goal-aware stopping needs its own fresh trial.

Operator resets/fixtures and138 held-out measurement actions per arm are excluded
from agent action costs; runner CPU includes measurement overhead. Native mechanics
and task forms are exposed; new seeds are new instances, not new-world generality.
Production remains OFF; main/Claude and previous seals untouched; no push.

- report SHA256 `a7bb46e6ae386afa033727036c1a53a8b1c0388ebfecf74b12cd1683da48b7ed`
- rows SHA256 `52fb7a9b36ad29749965d7c136160a021838a92aed7267ba5bc3d1fd6e3a5e08`
- archive SHA256 `97a3187406606dacb738b37efe292a512b1ff70e73b334d3e7489ec1b05d334c`
