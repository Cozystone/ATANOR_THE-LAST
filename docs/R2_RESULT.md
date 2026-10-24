# R2 final: bounded proposal-to-planning pipeline GREEN

2026-09-17. Discovery/corpus commit `441a211`; fresh candidate/prereg `7ffca42`.
One discovery proposal and one registered fresh planning attempt. No retries.

The proposer detects old-view contradictory native successors, not a manually
supplied collateral label. Among anonymous comparisons it selected column 3 eq
(audit mapping: inode). Training ambiguity 16 -> 0; separate held-out validation
ambiguity 16 -> 0. The independent gate supplied a content-named channel
`r_eb62ec5d3e6817d6`, then a new model was trained from 176 native transitions.

| New fresh planning cohort | ON | Same learner/planner, channel removed |
|---|---:|---:|
| Exact-byte task success | 64/64 | 32/64 |
| Any intermediate collateral sibling change | 0/64 | 32/64 |
| Native actions | 96 | 96 |
| OS worker CPU seconds | 112.96875 | 112.3125 |

Lift +0.50; one-sided 95% block bootstrap LCB +0.50; controls both 32/32.
All 12 registered gates pass. The interval is within this two-condition generator,
not uncertainty across unseen mechanics. ON is NOT cheaper per overall trial.
Parent episode CPU 13.078125 / 11.234375s; replay CPU 2.046875 / 1.859375s.
Trial wall 276.4148646s. Discovery/validation uses 64 additional native actions;
its cost is not hidden as free lifetime knowledge.

## Independent checks

- Seven new refinement tests pass: no-conflict no-proposal, anonymous-column
  permutation, fake score/accepted/verified/source metadata rejection, changed
  corpus versus prebound manifest rejection, held-out rejection without promotion.
- R1 broad regression remains 342 pass / one pre-existing expired deadline failure /
  two skips. R2 changes the new proposal/gate and opt-in harness parameters, not
  the sealed shared learner/planner algorithms; no full-suite-green claim.
- A stdlib-only audit verified all 64 observed discovery transitions against
  retained native files and independently recomputed both ambiguity reductions
  and the registration's projection binding: PASS.
- A stdlib-only verifier independently regenerated the fresh environments from
  registered RNG, reexecuted all 128 episodes, compared native observations/bytes,
  checked raw scores and bootstrap: PASS.

## What advanced and what did not

The explicit offline chain now works: contradictory experience -> generic bounded
feature proposal -> independent held-out decision -> new shared model -> changed
plans -> exact native success. No operator chose the inode column or passed the
proposer task labels. The grammar and raw stat sensor remain human-supplied.

This is still an OFFLINE representation epoch. No live WorldSession schema or old
memory was silently rewritten. Experiments, corpus and goals remain operator
chosen. It is not autonomous lifelong ontology birth, sensor invention, broad
generality or RSI. A local gate object is not claimed as hostile-host access
control; proposal code is separated by process/API, not OS security.

An exposed next-scope probe found a real limit: sealed R1 solves a two-alias group
but fails the same all-empty objective with three/four aliases. The current unique
neighbour/wildcard grouping is a candidate structural cause. This is DEV evidence
for R3, not a fresh R2 result or a reason to rewrite R2's score.

## Preservation

All raw rows, discovery datasets, projection receipt, training, checker code/results
and 128 SQLite journals are preserved in this branch. R0/R1 seals remain in their
own worktrees. Main/Claude code unchanged; production OFF; no push.

- report SHA256 `fe356c769b90e2924c9e97487c47fe079fedb8b627d3673f60d432f7a3e04b65`
- rows SHA256 `b02a55d8b5b60731b36fba25c2fa6db7a9c2eabf5df243a1e2126a02edef2e45`
- archive SHA256 `5c867340665f7022665a2d12eb27391be3bbd6648a1703586ea6e63d97bba45b`
