# ATANOR_THE-LAST — ATANOR OS research log

This repository mirrors the `atanor_os/` package of the ATANOR OS research (charter v0.1, 2026-10-24):
a small system that learns tool preconditions and effects from its own experience and is compared,
under pre-registered protocols, against documentation-only (A) and retrieval-only (B) baselines.
Each commit here corresponds to one commit of the private development repository (`Source:` line).

- Start here: [`atanor_os/README.md`](atanor_os/README.md)
- Reports: [`atanor_os/P1_REPORT.md`](atanor_os/P1_REPORT.md), [`atanor_os/P2_P4_REPORT.md`](atanor_os/P2_P4_REPORT.md)
- Every decision and its reason, in order: [`atanor_os/DECISIONS.md`](atanor_os/DECISIONS.md)
- Frozen protocols: `atanor_os/protocol*.json`; raw results: `atanor_os/results/`

Run (Python ≥ 3.9, standard library only): `python -m pytest atanor_os/tests -q`, then see the README.

Nothing in this repository is evidence of AGI, consciousness or general intelligence. Results are on
small generated workspaces; see each report's "아직 주장할 수 없는 것" (what cannot be claimed yet).
