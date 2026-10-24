# ATANOR_THE-LAST — ATANOR research repository

This repository mirrors the private development repository of the ATANOR research. Each commit here corresponds
to one development commit (`Source:` line). Until 2026-10-24 only the `atanor_os/` package was mirrored; from the
commit marked `[publish-all]` on, the whole tracked development tree is published.

## Layout
| Folder | What it is |
|---|---|
| [`atanor_os/`](atanor_os/) | **Current work: ATANOR OS** (charter v0.1, 2026-10-24) — learns tool preconditions and effects from its own experience; pre-registered experiments P1–P9. Code: `agent/` (what ATANOR is), `world/` (bodies: files, screen, read-only web), `core/`, `eval/` (evaluator side), `teach/` (training-only teacher material), `tests/`; reports `P*_REPORT.md`; decisions `DECISIONS.md`; frozen protocols `protocol*.json`; raw results `results/`; run scripts and dev-run summaries `runs/` |
| [`packages/`](packages/) · [`scripts/`](scripts/) · [`tests/`](tests/) | Earlier development line (the "Whole Mind" system and its experiment scripts), frozen before ATANOR OS |
| [`docs/`](docs/) | Design and result documents of the earlier line |
| [`evidence/`](evidence/) | Raw evidence of the earlier line's experiments (logs, SQLite files, checkpoints, sealed evidence archives) |

- Start here: [`atanor_os/README.md`](atanor_os/README.md)
- Every decision and its reason, in order: [`atanor_os/DECISIONS.md`](atanor_os/DECISIONS.md)

Run ATANOR OS tests (Python ≥ 3.9, standard library only): `python -m pytest atanor_os/tests -q`, then see its README.

## Not published
- Archived third-party web page texts and raw model responses that may quote them (kept local only).
- Model weights (the local reading-tool model used in P7).
- Generated sandbox workspaces of individual runs, and anything git-ignored in the development repository.
- Sealed evaluation sentences until their run has happened (only their sha256 is published before).

Nothing in this repository is evidence of AGI, consciousness or general intelligence. Results are on small generated
workspaces; see each report's limits section.
