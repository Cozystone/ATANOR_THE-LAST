# Predictive interference v1: conditional architecture audit

2026-09-20. User requests attached expandable predictive factor proposal.
Do its prerequisite audit first; no factor implementation without supporting
evidence. Budget2h, one execution20min. Old repair lineage closed, no tuning.

All396 previously correct shared state-changing probes of original six-law panel,
including234 later lost,162 retained. Not a fresh cohort, not independent396laws.
Actual checkpoint0->16 parameter displacement, old-loss gradient evaluated at0
(ensemble NLL, zero body activation, exact original categorical sensor). Harmful
dot product means displacement has positive first-order old-loss sensitivity.
Remove only its positive projection onto that initial gradient from final weights.
Compare same-L2 deterministic random removal. Both interventions use frozen
models, no optimization. This is ORACLE diagnostic: old probe truth and action
are explicitly used to test causal sensitivity. Never usable as capability or
learner allocation evidence; never leaked into future learners.

Prerequisite supported only if ALL: >=75% lost cases harmful dot; >=20% of lost
whole predictions rescued; rescue exceeds random by10pp; >=25% aggregate old NLL
damage removed; damage reduction exceeds random by20pp. Report retained cases
too. Thresholds are engineering screening criteria, not statistical confidence.
No law/initialization independence claim. Random control one seed per probe;
no seed tuning. Exact0/16 predictions must reproduce original raw labels.

If unsupported, stop architecture implementation and report INCONCLUSIVE:
nonlinear long-step interactions can defeat initial tangent approximation, so
this does NOT refute all interference or all expandable models. If supported,
only permission to investigate expandable substrate, not proof it will succeed.
Whole-core rollback would trivially restore old predictions and is NOT evidence.

Theoretical context, not a recipe or proof:
Farajtabar et al., Orthogonal Gradient Descent, AISTATS2020,
https://proceedings.mlr.press/v108/farajtabar20a.html
Grossberg, Adaptive Resonance Theory review,
https://sites.bu.edu/steveg/files/2016/06/ART.pdf
No inference that these solve ATANOR's task-free allocation or cumulative capability.
