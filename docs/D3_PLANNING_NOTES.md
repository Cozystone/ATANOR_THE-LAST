# D3 shared planner — bounded mechanism, not capability

`packages/shared_world/planning.py` ranks finite action sequences with the same
public `Frame`, `Goal`, and opaque identifier/arity schema for both neural
`Forecast` and relational `JointForecast` learners. No native body is executed
here, and no action-name-specific precondition or effect is built into search.

## Coupling and uncertainty

Every sequence carries a distribution over **whole** forecast states. Each next
action is evaluated across all states of that distribution; choosing a separate
best continuation for each hypothetical branch is not permitted. Only a later
real supervisor observation authorizes replanning. A joint hypothesis can still
contain soft marginal states: their internal conjunction score has the inherited
`Goal.probability` mean-field limitation. Exact discrete branches preserve the
correlation supplied by the model; the planner does not establish calibration.

Exact identical forecast states are merged. At most 32 distinct branches survive
per sequence, in descending mass order with stable input-order ties. Discarded
mass contributes zero goal score and is **never renormalized**. Thus truncation
can under-value a useful sequence. Uncertainty is a conservative heuristic: the
maximum of prior sequence uncertainty and the capped sum of mass-weighted model
uncertainty plus missing mass. It is not a statistically justified error bound.

The score is expected retained goal score minus `0.035 * depth`, minus
`0.1 * sqrt(uncertainty)`, minus `revisit_penalty * matching_no_change_count`.
No-change counts match the exact current observed state and first action in the
separate `failed_attempts=()` input (at most 256 Frame/Action pairs). **Persistent
learning history is never used for this penalty.** The supervisor must construct
these pairs from an immediate dispatched action and its actual RESULT, requiring
both before/after Frame and before/after native evidence equality. The planner
does not infer a result from the next history row or the current Frame: an
external intervention can separate those observations from the actual result.

The API name `failed_attempts` denotes observed no-change, not proof of failure or
of no effect outside the observed scope. A supplied pair's shape does not establish
its provenance; the supervisor owns native evidence binding. This soft heuristic
can still discourage useful stochastic retries or alias distinct hidden contexts.
Default penalty is unchanged at 0.2 and can be disabled with zero.
All these constants are disclosed heuristics, not fresh-tuned capability claims.

## Budget, history, and result contract

- `nodes` counts every **state-action prediction evaluation**, not Python calls.
  The model is called in batches, once per retained state with the full action list.
- Every root action is evaluated. Depth two expands every root across the same
  allowed action surface, even when `width=1`; width first limits the frontier
  entering depth three. Actual joint branching increases the required budget.
- If a requested complete beam depth cannot fit, the planner raises `ValueError`
  before that depth, rather than silently scoring partially evaluated actions.
  Earlier completed depths may already have consumed compute; no native action
  is executed by this function. The supervisor must record/reject planner errors.
- Later hypothetical views may be `Forecast`; **history always remains the same
  supplied actual `Frame`/`Action` sequence**. Model calls receive private copies.
- `failed_attempts` is separately revalidated and is never appended to learning
  history, passed to the predictor as extra experience, or used as authority.
- Returned prediction is the selected first action's **one-step** prediction,
  never the more attractive terminal forecast mislabeled as next observation.
- Deterministic score ties use caller action order and stable model branch order.

Input and output types, fields, finite probabilities, handles, fixed parent scope,
goal scope, bound operation arities, and prediction count are rechecked at runtime.
These checks validate shape/binding only. They do not authenticate a caller-created
`Frame`, authorize an action, or prove success. Native truth and allowed-action
surface must still be checked independently by the supervisor.

## Synthetic verification scope

The test module checks impossible conjunctions, positive correlation, common
action sequences, root coverage, original root receipts, truncation, exact-state
merging, batched budget accounting/rejection, stable opaque-name ties, unchanged
actual history, mutation isolation, revisit behavior, and malformed caller/model
scope. These are mechanism tests only: no native/fresh episode, trained benefit,
calibration improvement, or AGI capability is claimed.

Initial verification: `python -B -m pytest tests/test_shared_planning.py --confcutdir=.
-p no:cacheprovider -q` completed with **29 passed in 3.08s**. Three cases also
instantiate the actual legacy neural, full-context neural, and relational
learners and exercise their prediction interfaces without any training/native
execution. This result validates compatibility and contracts, not task ability.

## Lifetime-history correction (DEV v1 preserved)

The initial planner counted every matching historical state/action as a revisit,
including successful transitions under completed goals. An exact synthetic model
reproduced a correctness/design mismatch without learning or native execution:
`S -> a -> F` succeeded, then `F -> b -> S` restored the state. For a new goal F,
the planner preferred the unnecessary `c -> d` detour (score 0.93) over the known
direct action a (0.965 minus the erroneous 0.2 = 0.765). With empty history it
correctly selected a. This was not evidence for tuning the model or coefficient.

Tests were added before changing package source. The focused run recorded
**5 failed / 29 deselected in 1.87s**: one actual incorrect choice and four missing
API/validation failures. Its immutable JUnit record is outside the candidate tree:
`D:/ATANOR-experiments/2026-09-13/d3-revisit-regression-before-v1.xml`.
The source at that run was planning SHA-256
`4de5883edf172d010e21c43125115d67bf816042690886805da6598a55696716`.

The correction separates supervisor-supplied observed-no-change attempts from
unchanged persistent learning history. Model implementations, score coefficients,
goal rules, beam behavior, and joint-outcome handling are unchanged. Runtime
collection and worker transport are separate integration work, not established
by this planner-only synthetic verification.

After-correction full planner suite: **37 passed in 3.00s**, including all five
pre-fix regression cases and three additional no-change scope/bound cases.
JUnit: `D:/ATANOR-experiments/2026-09-13/d3-revisit-regression-after-v2.xml`.
The before-v1 record was not overwritten. No model training, native execution,
or fresh capability measurement was performed for this correction.
