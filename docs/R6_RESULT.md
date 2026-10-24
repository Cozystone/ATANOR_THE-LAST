# R6 — fresh local capability RED (preserved, no retry)

2026-09-17; frozen candidate/preregistration `d7f79cc`. DEV 8/8 did not replicate.

| Strategy | Fresh task successes | Acquisition actions | Task actions | Actions/success | CPU s |
|---|---:|---:|---:|---:|---:|
| Predicted-intermediate coverage | 40/64 | 88 | 96 | 4.60 | 100.734375 |
| Uncertainty sampling | 34/64 | 256 | 108 | 10.705882 | 83.40625 |
| Random | 21/64 | 256 | 112 | 17.523810 | 74.1875 |
| No acquisition | 32/64 | 0 | 96 | 3.00 | 41.65625 |

Lift against no-acquisition .125, lower bound 0.0; against uncertainty .09375,
lower bound -.125. Success-rate, no-acquisition lift, active non-regression and
acquisition-charged economy gates FAIL. Other gates pass. Do not reinterpret the
thresholds or call 40>32 a confirmed gain. No production promotion.

Independent stdlib reexecution reproduced 256 tasks and 600 acquired transitions,
regenerated configurations from registered seeds, verified actual-only learner
rows, compared all native frames and recomputed counts/LCBs: PASS. This was a real
candidate limitation, not an evaluator error. It is still trusted in-process
research, not independent external judging or hostile-process isolation.

366 tests pass / one known expired transfer-deadline failure / two skips. Three
new lookahead tests ensure predictions remain queries, cannot enter acquisition
as actual Frames, and query budget overflow fails closed. No full-suite GREEN.

## Post-result diagnosis (not a fresh rerun or candidate fix)

All 48 chosen steps in the 24 failed selective tasks had exact one-step forecasts:
the system correctly foresaw emptying but selected a bad plan (empty twice).
Separate temporary native replay of the already-known feasible unlink->empty
sequence found unlink exact 24/24; empty-after-unlink wrong applicable program in
20 and decision-tree routing away from available programs in 4. Thus checking
only whether SOME program fits a role footprint does not establish a correct
prediction at the actual intermediate state. Next research must address residual
effect-hypothesis ambiguity and real routing, not keep tweaking curiosity weights.

Acquisition/task action counts exclude operator fixture construction and held-out
measurement-data preparation (138 validation actions per arm). CPU includes this
runner overhead. No general compute-efficiency claim. Task-phase learning was
frozen for all arms; a future stronger comparison should include learning from
ordinary work without separate acquisition.

## Preservation

Raw rows in `evidence/r6-sealed/raw-evidence.zip`, receipt/checkers/regression beside
it. R0–R5 preserved separately, main/Claude unchanged, production OFF, no push.
- report SHA256 `debbc5e24c8a696f1dfa32c23780e04d1975895880606292a6f31dd587b034d3`
- rows SHA256 `ca5f8415449d9e97560d7e1112d95742f9bfd51d1401f99195080faf747234c9`
- archive SHA256 `671b04fed21be709dc340f39d23524b5a9980cba5a4a5eb564b94d3e6de00ad3`
