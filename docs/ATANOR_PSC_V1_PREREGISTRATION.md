# PSC-v1: first controlled-predictive-state feasibility gate

Approved direction: user attachment c36f61db-fcbc-4847-93ff-84ca30ea6b42.
Research worktree only; legacy Mind/history/native implementations unchanged.

## Theoretical prior and limits

Studied original [Littman/Sutton/Singh](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf)
and [McCracken/Bowling online discovery](https://proceedings.neurips.cc/paper_files/paper/2005/file/c3008b2c6f5370b744850a98a95b73ad-Paper.pdf).
PSR state predicts action-observation tests; discovering tests and estimating their
probabilities are separate problems. The online paper enforces probability
constraints and discovers additional tests from independence of predictive columns.
Its prediction results do not establish ATANOR control gains. Unidentified recent
papers in the pasted text are NOT treated as verified supporting evidence.

Here: bounded empirical controlled-predictive partition, not an implementation of
the full linear-PSR gradient algorithm. Begin with no semantic relations/tests.
Actual conflicting futures justify tests of length1..3; minimum2 examples per side,
max32dimensions/4096records, no silent forgetting. Current observation is the
empirical history anchor. This is an explicit estimator limitation: aliased hidden
states or new observations may require a recurrent estimator; splitting cannot
create inaccessible information. Same-anchor mixed outcomes remain unresolved.

No made-up ontology, relation list, hand-coded SQL policy or future-value access.
The legacy raw state sensor, actions, equality goal predicate and BFS are developer
provided. Exact observation/test storage can still be memorization; therefore the
exact-transition lookup baseline is mandatory. A win over empty-state ablation
alone is insufficient for broad abstraction or new intelligence claims.

## Frozen execution

Code/docstrings in developmental_psc_eval.py define all seeds,16tasks, budgets,
thresholds and128step continuation. Training is the192archived SQL observations,
reexecuted against actual SQLite before ingest. Native evaluation is one attempt,
three arms, before/after sequential learning as a predeclared paired comparison.
Eight actions/task, horizon4/4096queries; total180s cap. Source hashes and separate
native trace replay required. No learning from evaluations, no retry/tuning on
results. Save both checkpoints, actual traces, birth witnesses and negative gates.

Required: born dimensions; witnessed contradictory futures; >=4task advantage over
ablated; >=12/16fresh task successes and no fewer than exact lookup; restart equality;
no previously solved task lost, no correct archived prediction lost and no wrong
prediction increase after continuation. All gates must pass for second native
mechanism testing. Otherwise report limits of this estimator, not PSR impossibility.

Fresh instances are known SQL mechanics, not unseen laws; n5 is beyond n4 training.
Existing203record filesystem Self remains intact. PSC is not installed in production.
Method-unit cap: this first one-shot gate, no repeated small coverage improvements.
