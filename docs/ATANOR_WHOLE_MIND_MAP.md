# Whole Mind integration map

Audit opened 2026-09-20. **IN PROGRESS, not an integration or capability PASS.**
Authority: Founder attachment cff40ac2-ef95-47e2-8264-ba5d300da8ee.
No cognition implementation during the initial audit. Closed experiments stay closed.

## Source boundaries

- H = `C:/0.ASKIM ALL-VIN/27., ATANOR DEMO`, HEAD `1f577f65`,
  branch `run/dw0b-gate`. Dirty concurrent source/data is NOT ours to change.
- R = `D:/ATANOR-experiments/2026-09-19/developmental-research`,
  baseline `570b510`, integration branch `codex/whole-mind-integration`.
  This is a separate repository: do not assume H history is present in R.
- H API, H Open Life, and R WorldSession are separate state owners. None is
  established as the canonical runtime for the proposed integrated mission.
- Evidence below distinguishes source inspection and historical receipts from
  present execution. No historical experiment has been rerun by this audit.

## Capability inventory

| Function / demonstrated scope | Implementation | Evidence and present survival | Integration decision / replacement comparison |
|---|---|---|---|
| Persistent estate, testimony, vocabulary, rules and epistemic history | H `packages/mind/open_life.py::save_estate/load_estate` | Source retains atomic estate replacement and serializers; H `docs/ATANOR_CURRENT_RESEARCH_2026-09-12.md` records estate1160 preserved after resource failure. Current daemon NOT checked. | Stronger breadth than R checkpoint. Does not serialize a continuing native workspace or whole active CoreStore; not a drop-in WorldSession replacement. |
| Real multi-system learned goal achievement | H `packages/mind/goal_world.py::model_agent`, `CoreStore`, `plan_agent` | H `data/mind/goal_gate2_artifact.json` and `docs/ATANOR_goal_crosssystem_verdict.md`: 30/30 filesystem and SQLite, random0/30, median8/13. Source survives; Open Life calls CoreStore/plan_agent. Historical result is enumerable state-space scope. | Primary older planning candidate. BFS follows learned transitions, not an authored action sequence; however parent/slot ontology and categorical context assumptions require scrutiny. Newer R is not demonstrated superior on this venue. |
| Construction learning and reuse | H `packages/mind/construction_mind.py`, `construction.py`, `goal_world.py::CoreStore` | Historical ledger reports feature/generalization gates; CoreStore source directly instantiates ConstructionMind. Final carry receipt H `data/mind/screen/fallback_eval_20260910_215526/report.json` FAIL: only Mountain qualifies. | Preserve learner, do not import broad transfer claim. Select only after checking categorical prediction path and persistence. |
| Executable induced rules | H `packages/mind/rules.py::RuleBook/Rule` | Source implements IDENT/CONST/MAP/CTXMAP and composed LIKE; Open Life injects rulebook. Rules fitted from lived records, authored grammar. | Existing candidate; not autonomous unrestricted algorithm invention. Inspect actual mission contribution before enabling. |
| Arithmetic program induction | H `packages/reasoning_vm/procedure_induction.py` | Source searches bounded repeat programs over S/P and grown basis, checks supplied held-out examples. Existing tests; not rerun here. | Not evidence of general digital mission planning. No reason to add arithmetic solely to claim VM integration. |
| Graph precondition reasoning / belief retraction | H `packages/reasoning_vm/precondition_planner.py`; `packages/truth_maintenance/jtms.py`; `packages/mind/reintegration_smoke.py` | Existing smoke connects MinimalMind events to triples, JTMS withdrawal, and planner abstention. Source inspected; current map records prior passing regression. | Already partially integrated, contrary to 'nothing ever connected'. Requires explicit requires/must_be facts; bridge must not author mission solution through those facts. |
| Self-language | H `packages/mind/selflang.py`; ConstructionMind word channel | H `docs/ATANOR_selflang_payoff_prereg.md`: authored vocabulary, ungated1520 vs no-vocabulary1535; gated1535. Source survives and Open Life owns vocabulary. | Existence is not positive payoff. Preserve, not mandatory for V0. Do not treat this as natural-language competence. |
| Epistemic action history / testimony separation | H `packages/mind/rules.py::Ledger`, `bench.py::Knowledge`, `goal_world.py::plan_agent` | Source keeps paid/wasted observations; own outcomes override claims and contradict sources. Open Life wires these into same store. | Candidate provenance/verification organ. World-local keys and stale beliefs cannot be silently relabelled as R native evidence. |
| Machine-shop candidate execution | H `packages/mind/machine_shop.py::Shop/GateAdapter`; `open_life.py::shop_cycle` | Typed bounded programs and opt-in call sites survive. H current research closure corrects s16 broad claim to random planner bypass. | Preserve substrate; no automatic promotion or GA restart. No established need for new synthesis in V0. |
| Real digital bodies | H `workspace_world.py`, `sql_world.py`, `redis_world.py`, `couch_world.py`, `mountain.py`, `render_world.py` | Open Life selects and calls them. Workspace source actually uses temp repo, Git, py_compile, SQLite integrity_check and real peer edits. Service availability for Redis/Couch NOT checked. | Workspace strongest initial mission candidate: files+Git+database in one owned sandbox. Its database operations concern file integrity, not arbitrary SQL task understanding. |
| Recent persistent world and independently checked authority | R `packages/shared_world/runtime.py::WorldSession/verify_world` | R `docs/ATANOR_SUBJECT_LOOP_V1_RESULT.md`, `evidence/persistent-subject-loop-v1`: full3/3 vs frozen2/3 vs no-prediction0/3; native replay, one intent, restart and disturbance. Source survives. | Stronger explicit event/goal/replay contract; narrowly exact Sandbox-bound. Not proof of stronger general cognition than Open Life. |
| Recent prediction, actual learning, sequence search | R `scripts/developmental_persistent_client.py`; `developmental_effect_families.py`; `packages/shared_world/cost_ordered_search.py` | Same recent receipt; learned actual records influence actions. Small authored grammar and file frame. | Preserve as comparator/candidate, not default winner because newest. |
| Developmental neural plasticity | R developmental-core scripts; archived result docs | Prior broad acquisition gain with retention collapse; anchoring/latent-cause line closed. | Historical evidence ONLY. Not reopened by whole-mind integration. |
| GWIP shared interaction and rule transfer | H `docs/ATANOR_GWIP_ARC_I0_FINAL_STATUS_2026-07-28.md`; frozen candidate `51de7aad`, evidence `796c1df3` | Historical mechanism/capability GREEN, generated cohort,12 gates. No public ARC/independent E5 claim. Final closure inspected; full candidate source pending. | Preserve authority/interaction contracts as a comparison. Synthetic rule transfer is not evidence that it already plans in native Git/SQL. |
| Evidence-answer discrimination | H `docs/ATANOR_EAD3_RESULT_2026-07-26.md`; candidate digest819e0ff07cfb968109d7d219e6bb86c35c9b2c21565af8263b13c3486d6f0425 | Fixed synthetic single-hop answer/evidence pairs: wrong-source24/24 to2/24, unknown12/12 to0/12. | Existing bounded verification ability, not a general native action verifier. No reason to put an answer classifier in an action authority path. |

### Corrections that change organ selection

H `docs/ATANOR_core_curve_verdict.md` initially reported144/144 versus143/144,
53.5 median acts saved and slope-0.48. Its audit addendum explicitly corrects
the attribution: planning read episodic per-cell modes, not invented structures.
The result supports learned memory-backed planning and substrate parity, NOT
causal benefit from ConstructionMind abstraction. Do not copy only its headline.

The old planning loop already distinguishes inferred belief from observed
experience: `goal_world.py::plan_agent` writes `store.put` only when `observed`,
and tags stale pre-state transitions with `fresh=False`. This is useful preserved
behavior. It is not the same as R's supervisor-acquired pre/post action evidence.

WorkspaceWorld's `keep` bundles add+commit; `mend` can restore a tracked file in
one operation. Consequently 'make all files clean' risks a trivial repetitive
repair test, not the required multi-step mission. Do not choose that objective
merely because its native components sound broad. Existing GitWorld exposes
create/add/commit separately and is a better sequencing candidate, but its tiny
fixed file slots do not by themselves establish a broad workspace capability.

## Exact barriers found so far

1. **World ownership:** H `open_life.segment` creates a new native world and
   CoreStore each segment; standing_goals replaces completed goals. R persists
   one authorized native body and intent. Starting Open Life is not this mission.
2. **Body contract:** R `_validate_body` requires `type(body) is Sandbox`, binds
   operation schema, paths, sensors; replay also constructs Sandbox. H bodies use
   `config/state/do`, categorical tuples, parent dependencies, and action strings.
   Removing the exact-type guard alone would discard independently checked authority.
3. **Prediction representation:** H uses `(context,state,verb)->category`; R uses
   handle frames with kinds/sizes/relations. Equal integer values are NOT equal
   semantics. No generic translation has yet been established.
4. **Persistence:** Open Life estate includes knowledge/rules/language/ledger/shop/
   carry, but current active native world and CoreStore are segment-local. Must
   verify complete snapshot coverage before using it for a continuing mission.
5. **Epistemic source:** observations, inherited testimony, forecasts and verified
   outcomes must remain distinct. H historical carry failures demonstrate that
   simply sharing keys across bodies is unsafe.
6. **Mission safety:** WorkspaceWorld's destructive native verbs operate only on
   its freshly created temp repo. Never point this adapter at the user's project.

## Audit still required before architecture selection

Trace full CoreStore learning/snapshot state, categorical planner assumptions,
ConstructionMind evidence and current clean source revisions; inspect strongest
July reasoning/GWIP evidence without rerunning; select a single world authority and
mission contract. Check source dependencies before importing any old organ.
Do not label this partial census complete or declare Mind V0.
