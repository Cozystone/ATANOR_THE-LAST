# Terminal bookkeeping correction, not another trial

The three arms each executed their34 actions once. The validation worker stopped
at the action cap before calling the frozen supervisor's terminal check, leaving
active goal0 and omitting GOAL_END. Frozen verifier correctly returned
durable_world_mismatch. Initial receipts/status remain preserved under
pre_finalization/ and PRE_FINALIZATION_STATUS.json.

Correction is terminal-only finalization of these SAME journals/native bodies.
Require steps==cap; forbid body.step and client.choose using raising guards;
call unchanged WorldSession.step exactly once. Require zero added actions, exact
same model, and appended events ONLY OBSERVE(pre_decision), OBSERVE(goal_end),
GOAL_END. The first finalizer expected one observation and halted after full's
terminal append; inspection established the two frozen supervisor polls. Full
was not stepped again; finalization resumed for controls, preserving all prefixes.
Reverify native replay.
Synthetic terminal fixture proves this before finalization. No mission retry,
no updated seed/goal/budget, no cognition change. Full already entered an
irreversible wrong directory at action5, so terminal correction cannot make it pass.

Post-event exact reachability was false for Full because action5 had already
made n6 DIRECTORY when its goal was FILE. The external event at n7 did not cause
this. Both controls' exact post-event states were reachable. This distinguishes
a valid mission's agent-created dead end from the prior invalid initial fixture.
