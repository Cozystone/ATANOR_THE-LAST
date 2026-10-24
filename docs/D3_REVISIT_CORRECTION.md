# D3 integration correction: successful history is not failed experimentation

This is a DEV-discovered candidate/planner defect, **not an evaluator defect**.
The old source is preserved by `46d916c` and the first workbench by `9478d88`.
No fresh capability cohort has been opened. Production remains untouched.

## Reproduction before modification

The planner counts every prior `(same state, action)` as a revisit. D1 correctly
preserves history across successive goals, but D3 then penalizes a successful
action when a later goal needs it again. With an exact deterministic synthetic
model, a one-step successful action scores .965 without history. After one
successful cycle its score becomes .765, and a two-step detour at .930 wins.
This is not prediction error and does not require changing the .2 coefficient.

Independent regression evidence:
`D:/ATANOR-experiments/2026-09-13/d3-revisit-regression-before-v1.xml`.
Five failing tests: one reproduces the semantic error; four require the new
explicit failed-attempt input and its validation. Existing tests are retained.

The DEV v1 first life also illustrates the practical risk: after successful
mkdir/copy and a move, a subsequent goal returns to a previously visited state.
An unnecessary mkdir occupies an auxiliary slot and damages the later task.
This is an illustration, not attribution of every DEV failure to this defect.

## Minimal correction

Keep complete actual learning history. Separately retain bounded observations
of a dispatched action for which BOTH its actual Frame and native evidence
were unchanged at the result. Only these observations enter repeat suppression.
The supervisor computes this from its own before/RESULT pair; it does not trust
the learner to claim that an action was ineffective. It means no change in the
observed scope, not a proof of no effect anywhere in the world.

Do not infer the result from the next history entry: an external actor could
have changed the world between those observations. Do not compare Frame alone:
file contents can change while kind, size and equality patterns remain equal.

Old DEV files stay immutable. A corrected source version gets its own test
evidence and DEV output directory. The old exposure remains disclosed. The
numeric fresh capability criteria, learner definitions, frozen checkpoint,
data collection, task generator, and .2 penalty coefficient are not adjusted
to rescue the old results.

## Other pre-fresh corrections identified independently

The DEV v1 timing cutoff excludes final journal hashing/result serialization.
That cost must be included before a fresh CPU gate. Fresh also requires exact
training-file hashes and BEGIN checkpoint binding; native outcome replay alone
does not demonstrate that the intended model was used. These are harness
corrections, separate from the actual planner defect above.
