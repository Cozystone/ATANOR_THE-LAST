# R7 — mechanism PASS; no capability claim

2026-09-17. Four new tests pass; broad regression 370 passed, one pre-existing
expired transfer deadline failure, two skips. Predictor, planner and production
defaults unchanged. Introspection is opt-in and not live-wired.

Native counterexample: observing empty(existing empty target) leaves KEEP(kind)
and constant(kind=1) both consistent. At an absent target they diverge. Legacy
prediction chooses KEEP and wrongly forecasts continued absence. New read-only
inspection reports RESIDUAL_DISAGREEMENT. Only after actually executing the real
operation does learning eliminate that ambiguity and predict the native effect.
Forecast queries leave the learner snapshot unchanged; caller identified=True
metadata cannot substitute for a typed query.

Post-hoc audit of all 24 R6 failed selective tasks, bound to original raw SHA256:
- 20 RESIDUAL_DISAGREEMENT
- 4 NO_APPLICABLE_ROUTED_BRANCH

No model was updated in that audit, no original result changed and no fresh trial
rerun. This pinpoints a bottleneck; it does not show an autonomous controller can
choose the right discriminating experiments economically. FINITE_SET_AGREEMENT
means only agreement of routed survivors in the bounded grammar, NOT truth,
confidence calibration, complete hypothesis coverage or authority.

Next possible unit is a discriminator-driven experiment selector using these
actual residual hypotheses, not another arbitrary curiosity score. It requires
its own one-shot new registration and ordinary-work-learning control. Do not
reuse R6 test seeds for tuning or call a future result a repaired R6 GREEN.
