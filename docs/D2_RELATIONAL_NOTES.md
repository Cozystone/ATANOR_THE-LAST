# D2: bounded conditional joint-effect learner

Status: synthetic mechanism implementation only. No native DEV/fresh capability
experiment has been run by this component's implementer. No original/baseline
files, native dispatch, contracts, or evaluation thresholds were modified.

## Interface

`packages/shared_world/relational.py`: `RelationalLearner` (`Learner` alias).

- `learn(event_id, before: Frame, action: Action, after: Frame, history=()) -> bool`
- `predict(frame: Frame | Forecast, actions, history=()) -> [(JointForecast, uncertainty)]`
- `snapshot() -> JSON-compatible dict`; `RelationalLearner.restore(snapshot)`
- Public operation schema IDs and arities are lookup keys only.
- `updates=0` retains learned rows/model while recording newly seen event IDs.
  Revision counts accepted observations, **not** proof that weights changed.

## Actual learned path

1. A real typed transition supplies targets. A fixed role grammar binds argument
   nodes and unique one-edge witnesses from supplied parent/equality channels.
   Non-unique neighbours are NOT arbitrarily bound to an individual.
2. For each role-bound node field and pair group, enumerate only KEEP, COPY from
   a pre-action field, or a constant witnessed in the result. A wildcard group
   must have a single expression fitting every member; native IDs are not stored
   as program destinations. All output assignments belong to one joint program.
3. Greedily intersect compatible expression sets across observed transitions.
   Incompatible transitions create separate program branches. Records are not
   edited to make a program consistent. This is empirical, deterministic program
   induction inside each branch, not proof that eliminated expressions are
   universally false in a noisy or changing world.
4. A small supervised CART learner separates program branches using current
   argument context, both directions of supplied relations, neighbouring kind/
   size aggregates, and three previous observation contexts. Thus a third entity
   that did not itself change can condition every output object.
5. Each selected program reads all right-hand sides from the SAME pre-action
   view. It produces a complete joint outcome, not independently sampled node
   marginals. Indistinguishable branch labels retain an empirical mixture.

The first matching expression order is a simplicity bias: KEEP, COPY, constant.
Condition splits use training labels only, with at most 32 candidate dimensions
and two thresholds per dimension per node. Greedy merging/order is deterministic
but order-sensitive; no globally optimal rule search is claimed.

## Scope and honest limits

- Supplied observations include categorical kinds, scalar sizes, parent and
  equality. This is **conditional model learning**, not ontology/predicate
  invention, raw sensory grounding, or a general model of physical dynamics.
- Fixed parent edges represent this body's locator scope. A transition changing
  them is explicitly rejected; learning structural reparenting is not supported.
- Only exact discrete kind/equality/parent views are executed as symbolic
  programs. Soft forecasts remain unchanged with uncertainty 1; they are not
  argmaxed into observations. The shared planner must expand joint branches.
  Imagined rollouts pass hypothetical current Forecasts while keeping the
  actual history fixed; Forecasts are not accepted as observed history entries.
- Programs that exceed the grammar or 32-rule budget are unsupported. Their
  actual records remain in bounded replay and raise uncertainty. An unseen op
  returns an unchanged-view hypothesis with uncertainty 1, **not** a supplied
  no-op semantic rule or a statement that its true effect is absent.
- Empirical branch weights are not calibrated posterior probabilities.
  Applicable branches are renormalized; omitted inapplicable branch support is
  included in uncertainty. Out-of-scope/generalization confidence is heuristic.
- Defaults: 512 replay records, 32 programs/operation, tree depth 6, 32 referents.
  Program inference includes quadratic pair groups and expression enumeration.
  Per-record candidate/feature derivations are cached without changing choices;
  branch intersection and condition fitting still rebuild after each update.
  Learning, restore, rebuild, and condition fitting costs count in task CPU.
  Seen-event IDs are retained for idempotence and grow with life length; this is
  not an unbounded-lifetime-memory or constant-space claim.
- No native filesystem reads, tool effect tables, operation-name interpretation,
  goals, future result arguments, pretrained network, or commercial LLM exist in
  this module. Prediction itself does not update evidence or learner state.

## Evidence boundary

Exact Frame/Action types and their mutable fields are revalidated. Forecasts,
caller `verified/source` envelopes, malformed Frames, and Frame subclasses are
rejected by `learn`. This detects category/syntax misuse, **not** fabricated
well-formed Frame contents. Native provenance, temporal ordering, supplied
history availability, independent observation binding, and permission are
supervisor responsibilities. Snapshot is model state, not an attestation.

The learner cannot infer timestamp authenticity from legacy Frame fields.
Prospective measurement must freeze the model snapshot used at each decision;
later-learned programs must not retroactively change its prediction score.

## Synthetic tests

`tests/test_relational.py` covers parent-context separability before/after
learning; coupled source/destination effects and empirical joint alternatives;
handle and opaque-operation permutation; JSON restore equality; frozen learning;
past-context conditioning; no predicted self-training; mutable/forged caller
type rejection; scope drift rejection; bounded replay/rule overflow; and soft
relations remaining uncertain. Tests use opaque IDs and synthetic observations;
they are mechanism checks, not native adaptation or capability evidence.

Run only from the isolated repository:

```powershell
$env:TEMP = 'D:\ATANOR-experiments\temp'
$env:TMP = 'D:\ATANOR-experiments\temp'
& 'C:\ProgramData\miniconda3\python.exe' -B -m pytest tests/test_relational.py --confcutdir=. -q
```
