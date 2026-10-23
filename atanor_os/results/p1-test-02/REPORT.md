# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): no council gain

protocol: `{"version": 2.1, "frozen_at": "2026-10-24T02:56:13", "supersedes": "v1 (frozen 2026-10-24T01:58:40; kept verbatim as results/p1-test-01/metrics.json['protocol']). v1 results are preserved and reported together with the review findings that motivated v2.", "primary": "C-B strict completion (real end state AND no keep violation on the way) on split=test, learning state frozen", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "secondary": "D-C with the same thresholds, recorded only. D (v2): members vote only when they have evidence; tie = fail; docs fallback only when no member has evidence", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "changes_from_v1": ["convert tasks: output must be content-distinct from every observable file (copy/move cannot satisfy); partial is over literals false at the start", "test split rotates its extension list so md/log/json all occur (v1 never generated json)", "binding search budget = 100000 predictions per plan call (deterministic, identical for all conditions); seconds=180 is a safety guard; stop reason recorded; planner budget exhaustion is reported separately from abstention", "D vote rule: documented-only members abstain (v1 let them vote 'success')", "validity gate: semantics check stratified per (tool, outcome) with >=20 each and a run-derived seed; tests gate excludes learner-performance tests; tests must have run; label must be 'pre-registered'", "primary metric is strict completion; storage per condition; reachability once per task; records written per seed; source sha256 + git state recorded", "v2.1 (before any v2 learner run): prediction cap 100k -> 400k because the evaluator's ORACLE solved only 16/20 test tasks at 100k (depth-2 sort tasks need ~750 actions per expansion); at 400k ORACLE solves 20/20 with 0 budget stops"], "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity tests not run or failed", "unreachable task", "label != pre-registered"], "known_limits": ["blocked is structurally 0 (the planner never proposes capability-gated tools)", "B is exact-signature retrieval and therefore coverage-limited; C-B mixes rule induction with generalization beyond the explored signatures (docs_share column makes this visible)", "md objects already occur during exploration (POOL); what is new in test: object and directory names, 3-4 files, extensions log/json, depth-2 target chains, more required steps"]}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "source_sha256": "83947f41b9fc6dce", "source_files": 28, "git_head": "a812362", "git_atanor_os_untracked_or_modified": true}`

검사: `{"label": "pre-registered", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"mkdir:success": 20, "mkdir:failure": 20, "copy:success": 20, "copy:failure": 20, "move:success": 20, "move:failure": 20, "delete:success": 20, "delete:failure": 20, "convert:success": 20, "convert:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "learner_tests_passed": true, "unreachable": 0}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.200 | 0.200 | 0.200 | 0 | 19.20 | 18.70 | 0 | 0 | 80 | 0 | 1890/1920 | 1.00 | 3.939 | 3.811 | 23708 | 9.0 |
| B | 100 | 0.210 | 0.210 | 0.229 | 0 | 18.37 | 17.63 | 0 | 0 | 79 | 0 | 1784/1837 | 0.96 | 3.578 | 3.458 | 24469 | 9.1 |
| C | 100 | 0.840 | 0.840 | 0.846 | 0 | 7.04 | 2.96 | 0 | 8 | 8 | 0 | 320/704 | 0.18 | 5.255 | 5.177 | 140851 | 77.5 |
| D | 100 | 0.610 | 0.610 | 0.616 | 0 | 8.85 | 6.34 | 0 | 22 | 17 | 0 | 658/885 | 0.14 | 51.928 | 51.521 | 238534 | 122.6 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/105 | 0.00 | 1.434 | 1.399 | 102426 | 36.0 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| A | 0.00 | 0.67 | 0.00 |
| B | 0.00 | 0.70 | 0.00 |
| C | 0.91 | 1.00 | 0.63 |
| D | 0.66 | 1.00 | 0.23 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +63.0 | 16/4/0 | 5/5 | 1:+80, 2:+30, 3:+50, 4:+80, 5:+75 |
| B-A | +1.0 | 1/19/0 | 5/5 | 1:+0, 2:+0, 3:+0, 4:+0, 5:+5 |
| C-A | +64.0 | 16/4/0 | 5/5 | 1:+80, 2:+30, 3:+50, 4:+80, 5:+80 |
| D-C | -23.0 | 0/7/13 | 3/5 | 1:-65, 2:+0, 3:+0, 4:-50, 5:+0 |

## 예측 근거와 탐색 정지 이유

- A: status `{"documented": 1920}`  stops `{"found": 1920}`
- B: status `{"documented": 1771, "retrieved": 66}`  stops `{"found": 1837}`
- C: status `{"learned": 579, "documented": 125}`  stops `{"found": 704, "nodes": 8}`
- D: status `{"council_learned": 760, "council_documented": 125}`  stops `{"found": 885, "nodes": 22}`  의결: {"disagreement": 0.07101601400231482, "no_evidence": 0.07561381806122519}
- ORACLE: status `{"oracle": 105}`  stops `{"found": 105}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": 9.399984264746308e-06, "B": 0.004233599989674985, "C": 0.007529900001827627, "D": 0.0067199000041000545, "ORACLE": 6.300018867477775e-06}, "2": {"A": 5.1000097300857306e-06, "B": 0.005798900005174801, "C": 0.009452399972360581, "D": 0.010398699989309534}, "3": {"A": 7.299997378140688e-06, "B": 0.006158700009109452, "C": 0.009703999996418133, "D": 0.011265000008279458}, "4": {"A": 9.299983503296971e-06, "B": 0.003950100013753399, "C": 0.007567799999378622, "D": 0.006784099998185411}, "5": {"A": 6.700021913275123e-06, "B": 0.004965800006175414, "C": 0.007880099990870804, "D": 0.008127800014335662}}`
저장(journal bytes, seed→조건): `{"1": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1261568, "model_json_bytes": 44}, "C": {"journal_bytes": 434176, "model_json_bytes": 3502}, "D": {"journal_bytes": 651264, "model_json_bytes": 10138}, "ORACLE": {"journal_bytes": 405504, "model_json_bytes": 28}}, "2": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1269760, "model_json_bytes": 44}, "C": {"journal_bytes": 917504, "model_json_bytes": 2836}, "D": {"journal_bytes": 917504, "model_json_bytes": 8921}}, "3": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1286144, "model_json_bytes": 44}, "C": {"journal_bytes": 307200, "model_json_bytes": 2770}, "D": {"journal_bytes": 311296, "model_json_bytes": 9332}}, "4": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1269760, "model_json_bytes": 44}, "C": {"journal_bytes": 434176, "model_json_bytes": 3524}, "D": {"journal_bytes": 585728, "model_json_bytes": 8496}}, "5": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1245184, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 3458}, "D": {"journal_bytes": 479232, "model_json_bytes": 10206}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
