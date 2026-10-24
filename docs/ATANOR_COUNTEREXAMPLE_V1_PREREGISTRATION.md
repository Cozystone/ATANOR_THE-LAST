# Counterexample-normalized adaptation v1

User attachment f80124dc requests DIAGNOSIS only. No architecture, curiosity,
consolidation, replay or learner modification. Previous rapid-adaptation NO-GO
and task-reuse positive both remain intact. Budget1h, one execution cap10min.

## Fixed protocol

Original four passive A1024 checkpoints, not B-adapted checkpoints, versus
same-seed fresh. Same original learner/config, optimizer/replay continued as-is.
Two separate native B laws SETNULL/CASCADE. Four paired lives each. Exactly8 actual
contradictions each life; readouts0/1/2/4/8. Both arms learn the SAME actual native
before/action/after. No generated labels, no extra minibatches or repeated fitting.
Each contradiction executes parent deletion in fresh initialized n4 realSQLite,
prefill1+(event_index%3), seed1040000+1000*law_index+20*life+event_index.
Independent original A database must refuse same action with identical observation;
B must accept with different actual successor. Initialization is fixture setup,
not learned/charged actions. This is deliberately provided diagnostic evidence,
NOT autonomous experience choice or a new task capability result.

Each trial a different physical DB: original enter_body resets body working
activation, retains learned weights/optimizer/replay. Fresh has3 optimizer steps
on first event, experienced6; after that6 each. Preserve/report this original
algorithm behavior, no compute-parity claim. No learner tuning from results.

Held-out probes4/life/law: seeds1050000+1000*law_index+20*life+q, n5+q%2,
prefill1+q%3. No probe learning; disposable checkpoint copy and new body context.
Same probes across counts to test observed persistence; no results returned to
canonical learner. Outcomes measured before receiving each probe's actual result.

## Metrics / classification fixed before run

PRIMARY changed-consequence exactness: predicted argmax correct for ALL cells
whose actual A and B successors differ.16probes per arm/law/count. Native-derived
mask used only for external scoring, never learner input/loss. This avoids making
unchanged-cell prior knowledge the main test. Also report complete next-state
exactness, old-law exactness and probability assigned to changed true cells.
Fresh at0 is not assumed to know old law.

Acquisition threshold: first sampled count with >=75% changed-exact overall and
>=50% in EACH life, sustained at every later sampled count through8. Report each
life's own >=75% sustained acquisition as well. Reaching at8 establishes only last
observed endpoint, not unmeasured long-term retention. Never extrapolate stability.

Classify each law: experienced earlier/later/same observed count. If only one
crosses by8, it is faster WITHIN BUDGET. If neither crosses: UNRESOLVED_WITHIN_8,
not equality or proof of inability. Mixed laws stay mixed; no pooled verdict.
Same observed threshold does NOT prove equal algorithms. Faster means bounded
adaptation advantage, not proof learning algorithm evolved. Slower compatible
with interference, not causal proof prior rigidity (weights, old replay and Adam
all differ). Raw curves remain mandatory; no post-hoc threshold adjustment.

Independent reconstruction of all native witnesses, source/checkpoint hashes,
checkpoint reload forecasts, raw count audit required. Existing candidate tests
and environment witnesses must pass before freeze/run. No task reruns, no extra
counterexamples after8, no production/main edits, no push.
