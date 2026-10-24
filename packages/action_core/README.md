# Action core — opt-in development only

No production import/wiring. No pretrained model. No central LLM. No AGI claim.
The 17,583 parameters are three randomly initialized shared GRU predictors on CPU.
The only current body is a new, owned temporary filesystem with public structured
observations and four exposed operation schemas. Perception and action vocabulary
are provided, not discovered. This is not a domain-general interface implementation.

`world.Frame` is an actual structured observation. `model.Forecast` is a separately
tagged probability hypothesis, rejected as a learner observation. `planner.Goal`
is supervisor-owned; model probability never establishes completion. The body
reads native file bytes for equality and SHA-256 evidence.

`worker.Client` provides a JSON learner subprocess with a timeout. This is an
API/data boundary, NOT protection against arbitrary hostile Python/native code.
The body forbids path escape, unknown handles, protected destination writes and
symlink/reparse paths, before mutation. No arbitrary code execution is supported.

`episode.Episode` persists a single goal, observed history, forecasts as forecasts,
model checkpoint, action budget and pending dispatch in SQLite. Pending interruption
is reobserved and stopped; there is no OS-level atomicity between SQLite and file
operations or guarantee of exactly-once recovery. The independent verifier
replays recorded actions on a fresh body from externally fixed initial conditions,
and compares real observations and completion. It does not independently establish
the learning algorithm's correctness from a model's claimed revision/digest.

The recurrent history is three events, replay 512 records, pair prediction is
quadratic in visible objects. These bounds do NOT implement lifetime memory,
brain-like efficiency or `N grows, k remains small`.

Run isolated mechanism tests (root pytest has unrelated data-writing fixtures):

    C:\ProgramData\miniconda3\python.exe -B -m unittest discover -s packages/action_core/tests -v

DEV tool, **not a command to automatically run a fresh capability attempt**:

    C:\ProgramData\miniconda3\python.exe -B -m packages.action_core.dev --output <new-output-directory>

The optional `--change-balanced` learner balances observed changed/unchanged
strata, not operator rules. The option is preserved in snapshots; default is OFF.
The dev runner refuses to overwrite an existing output directory.

Results through2026-09-11 (earlier receipts retained, not overwritten):

- First DEV neural1/8; change-balanced2/8; same-record retrieval6/8.
- Corrected typed-goal planning/actual updates/root coverage eventually8/8 DEV.
- Fresh-v2 known-filesystem configurations: neural56/64, retrieval42/64,
  cold8/64, frozen49/64; all256 native replays. Numeric local-utility gates pass.
  Case-order randomization deviated from the original prose; see the pre-result
  disclosure and ACTION_CORE_FRESH_RESULT.md in the containing experiment folder.
  This is not new mechanics, AGI, external E5 or full protocol-conformance.
- D: continuation copy adds Life agenda/global budget/checkpoint and body resume.
  On16 exposed tasks carry/reset/frozen all16/16, actions24/28/28; real learner
  process replacement preserves the preselected trace. Mechanism, not fresh lift.
- Optional observed-revisit cost0.1 failed its exposed DEV readiness gate and
  stays default0. It is not enabled by the continuity experiment.
- Continuity fresh-v1 REGRESSION:later-task carry49/64 vs reset57/64,
 261 vs215 charged actions;256 native replays/32 learner restarts and independent
 arithmetic PASS. Life mechanics work but unfiltered cross-episode parameter
 carry harms capability. See CONTINUITY_FRESH_RESULT.md in the experiment folder.
 Do not promote carry or skip this result when planning the next stage.

This D: source copy has NOT been merged into the original C: worktree. C: had
insufficient space; unrelated sources and measured C: candidate were left intact.
No push, no downloaded model, no production imports or automatic activation.
