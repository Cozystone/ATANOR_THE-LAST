# R4 — uncertainty sampling: do not promote

2026-09-17. DEV only; no fresh capability trial. Frozen candidate `402f18d`.
Four mechanism tests pass. Initial harness stopped before any experience because
temporary parent directories were missing; corrected before the first measured
DEV run (v2). No measured-result tuning or retries.

| Experiences | Active prediction error | Random error | Active task success | Random success |
|---|---:|---:|---:|---:|
| 0 | .082323 | .082323 | 4/8 | 4/8 |
| 4 | .080262 | .081801 | 4/8 | 4/8 |
| 8 | .074421 | .078996 | 4/8 | 4/8 |
| 16 | .055707 | .068990 | 0/8 | 0/8 |
| 32 | .027876 | .052853 | 2/8 | 0/8 |

The script's narrow preregistered DEV readiness predicate is true (mean error
.052668 < .066946, final success not below random). Preserve its literal
R4_DEV_READY result. Overall architectural decision is nevertheless **NO PROMOTION**:
no-acquisition scored 4/8 using 12 actions, active 2/8 using 48 total actions.
This is not useful curiosity yet. No capability or economy GREEN; no large fresh
trial on the strength of the weak DEV predicate. This directly honors the known
Aug30 no-seeking control lesson (`6ccf6fde`).

Post-result read-only inspection on one failed collective task rebuilt the model
from its 32 real acquisitions: empty had NO applicable effect program anywhere
in the cache, not merely a bad decision-tree routing. Unlink had an applicable
program and two unresolved expression slots. The opaque uncertainty heuristic
improved average prediction on 2/3-alias contexts but did not ensure effect
coverage for the 4/5-alias task. Choosing any large uncertainty is insufficient.
That one inspected task is not asserted as the cause of every failure.

Next bounded hypothesis: select experiments whose argument-relative effect-role
signature covers currently unsupported actions in the actual task observation.
This is task-relevant acquisition, not outcome leakage: only BEFORE observations,
permitted action syntax and learner footprint enter the chooser. If tried, compare
against unchanged uncertainty sampling, random and zero-acquisition, charge native
acquisition and downstream actions, and preserve this failed candidate intact.

All work remains isolated on D:, no production/live wiring, no push. Human-provided
resettable context menus are still a limitation, not autonomous experiment design.
