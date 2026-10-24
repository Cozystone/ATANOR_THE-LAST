# Actual first fresh life: relational arm, seed 914800

This is the first life by ordinal, not the best selected after ranking results.
It is a readable rendering of the existing SQLite event journal, not a rerun.
One successful life cannot establish the aggregate capability verdict.

Source: `D:/ATANOR-experiments/2026-09-13/shared-world-fresh-v1/000-relational/world.sqlite`.
World `life:0`, self label `shared-core`, initial model revision 512.
Aliases for reading: R=n3 protected reference file; P=n4 parent locator;
C=n0 child of P; S=n2 spare; A=n1 auxiliary. Initially only R exists.

| Goal | Actual chosen action | Prediction before action | Native outcome | Model revision after learning |
|---|---|---|---|---:|
| C contains the same bytes as R | mkdir(P) | P becomes a directory | Matched | 513 |
| same goal | copy(R,C) | C becomes a file equal to R | Matched; goal complete, 2 actions | 514 |
| C absent, S equal to R | rename(C,S) | C absent and S equal to R jointly | Matched; goal complete, 1 action | 515 |
| C equal to R, S absent | unlink(S) | S becomes absent | Matched | 516 |
| same goal | copy(R,C) | C becomes a file equal to R | Matched; goal complete, 2 actions | 517 |
| C absent; S and A equal to R | copy(R,A) | A equal to R, C retained | Matched | 518 |
| same goal | rename(C,S) | C absent; S, A and R equal jointly | Matched; goal complete, 2 actions | 519 |

All seven transitions have prediction events before dispatch, native result
events afterwards, and a linked learning revision. The same world and learner
continue between goals; no environment reset occurs between these four goals.
The reference remains 21 bytes, SHA-256
`383d1e6e77b90abe0300bf3bf03971f07d81bb190601c6dbc161d304d88ac2ee`.

This trace is not optimal planning: the third goal took two actions although a
correct single rename would suffice. Model revision/digest changes prove that
updates occurred, not that those updates helped. Only the registered frozen
comparison across the full cohort can address their benefit.

The goals were supplied externally. Nothing in this trace demonstrates self-
originating motivation, invented sensory concepts, subjective consciousness,
or recursive self-improvement.
