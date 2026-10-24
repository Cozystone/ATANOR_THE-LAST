# R10 schedule and bounded search — fixed before candidate implementation

2026-09-19. Numerical gates and eight-task horizon in R10_PLAN unchanged.

## Shared start and costs

Each block has one disposable native acquisition surface from the existing
configuration(count=3, coupled_full). All arms begin with identical fresh models.
Six seeded uniformly sampled permitted native actions are performed sequentially
on that surface, without resetting, and learned as actual transitions. All arms
receive this SAME actual transcript and post-bootstrap state, and all are charged
six actions plus independently measured bootstrap CPU/wall costs. These are not
claimed to be hypothesis-directed; they establish initial learned candidates.
The no-exploration arm means NO ADDITIONAL exploration after this common bootstrap.
Report this distinction prominently; do not compare its figures to old cold R8
figures as though starts were identical.

Remaining acquisition allowance is26 (total32 including bootstrap). Synthesis
and random act on the continuing acquisition surface, without researcher resets,
restoration, config access or native-success peeking. Menu control uses unchanged
R8 select_discriminating with supplied 2/3-alias candidate fixtures; its fixture
construction CPU/setup and native actions are separately reported. This asymmetry
is the dependency being measured, not hidden free autonomy for the candidate.
Safety permits are supplied by Sandbox; irreversible changes within the disposable
surface are allowed, protected reference must remain intact. No new link primitive.

Then all arms face the SAME eight fresh task configurations of the existing two
goal forms, with cap2 task actions each and actual-only online task learning.
Acquisition changes do not modify these task initial states. The learner receives
no native post-action truth except actual observations. Setup/reset accounting is
reported separately, never presented as overall PC efficiency.

## Candidate contract

Inputs: learned model, current observed Frame, current permitted Action list,
remaining acquisition budget. No prepared Frame menu, config, native paths,
goal answer or operation-name cases. Model revision and snapshot stay unchanged
during selection. A plan is a proposal, not execution authority.

The target predicate is surviving expressions predicting DIFFERENT observable
values for the same output cell under an action. Reuse R7 inspect_effects.
NO_LEARNED_OPERATION and no routed hypothesis are explicit unsupported statuses,
not invented disagreement. A bounded deterministic forward reachability search
finds a prefix to a state satisfying that hypothesis-derived predicate. This is
not symbolic inverse-solving or proof of global shortestness.

Max total intervention length3 (up to2 prep +1 discriminating action), width32
per preparation layer, max2048 inspected action/state questions per selection.
Prefer shortest length; within that length prefer more disagreeing cells, then
stable action order. Keep exact deterministic single-outcome preparatory forecasts
only; unsupported/soft/mixture prep is reported/skipped, not converted to fact.
Terminal report contains predicted cell alternatives and the proposed prefix.
Execute ONLY first action then obtain actual observation and replan. Every action
is charged, including redundant prep and failure. No tuning of this ordering after
DEV. Exhaustion returns an explicit budget status, not a no-disagreement proof.

Per-arm CPU hard limit120 seconds/block (checked at bounded search/step boundaries)
for every arm including random/menu/no-extra exploration; boundary overshoot is
reported. Enforce the global40h cap. No hidden uncharged planning retries.

## DEV feasibility decision

Use exposed seed119031 only before freeze. GO requires at least one agent-proposed
intervention after the common bootstrap whose terminal cell has distinct surviving
predictions, a fully native executed prefix, and an actual terminal outcome that
removes at least one previously possible value on the SAME pre-action query.
If none is found within the registered bounds, record bounded NO-GO with the
specific limitation; do not relabel native handwritten witnesses as agent ability.
DEV utility is descriptive, not fresh capability. Fresh seed/source hashes and
independent audit protocol must still be sealed before any fresh execution.
