# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): n/a

protocol: `{"version": 1, "part_of": "protocol_h4.json", "role": "target", "body": "fs", "frozen_at": "2026-10-24T12:40:00", "hypothesis": "H4 target run on the fs body: policy contrast-pair", "primary": "per-run verdict = C vs B strict completion (unchanged harness rule); the H4 decision is cross-run, see protocol_h4.json", "primary_pair": ["C", "B"], "primary_metric": "completion", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "policy": "contrast-pair", "conditions_list": ["B", "C"], "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity gate not run or failed", "unreachable task", "label != pre-registered", "source changed during the run", "protocol parameter mismatch"]}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast-pair", "body": "fs", "learner_version": 4, "source_sha256": "0d580bbad1819684", "source_files": 41, "git": "not a repository (snapshot copy)", "source_sha256_at_start": "0d580bbad1819684"}`

검사: `{"label": "pre-registered", "policy": "contrast-pair", "body": "fs", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"mkdir:success": 20, "mkdir:failure": 20, "copy:success": 20, "copy:failure": 20, "move:success": 20, "move:failure": 20, "delete:success": 20, "delete:failure": 20, "convert:success": 20, "convert:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "tests_gate": "not learning and not timing and not view", "learner_tests_passed": true, "protocol_mismatch": [], "unreachable": 0, "source_changed_during_run": false, "protocol_file": "atanor_os\\protocol_h4_fs_target.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B | 100 | 0.410 | 0.410 | 0.442 | 0 | 16.28 | 14.58 | 0 | 0 | 59 | 0 | 1481/1628 | 0.92 | 14.617 | 14.477 | 57446 | 35.7 |
| C | 100 | 0.940 | 0.940 | 0.940 | 0 | 5.01 | 0.28 | 0 | 6 | 0 | 0 | 34/501 | 0.07 | 6.215 | 6.161 | 105343 | 126.3 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/105 | 0.00 | 3.374 | 3.328 | 102426 | 58.2 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| B | 0.46 | 0.83 | 0.00 |
| C | 1.00 | 1.00 | 0.83 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +53.0 | 16/4/0 | 5/5 | 1:+40, 2:+60, 3:+60, 4:+50, 5:+55 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측, unk=효과 미정, near=성공과 인자 하나 차이인 실패)

| seed | 조건 | 정확 도구 | 엄격 도구 | 어떤 도구(정확) | 검사 | fp | fn | eff | unk | near 검사 | near fp | 설명서 답 | 셀 충족 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | B | 2/5 | 2/5 | delete mkdir | 200 | 32 | 0 | 20 | 0 | 100 | 32 | 76 | True |
| 1 | C | 4/5 | 4/5 | copy delete mkdir move | 200 | 10 | 0 | 20 | 0 | 100 | 10 | 30 | True |
| 1 | ORACLE | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 2 | B | 1/5 | 1/5 | mkdir | 200 | 24 | 0 | 20 | 0 | 100 | 24 | 48 | True |
| 2 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 3 | B | 1/5 | 1/5 | mkdir | 200 | 32 | 0 | 15 | 0 | 100 | 32 | 49 | True |
| 3 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 4 | B | 2/5 | 2/5 | delete mkdir | 200 | 23 | 0 | 20 | 0 | 100 | 23 | 49 | True |
| 4 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 5 | B | 1/5 | 1/5 | mkdir | 200 | 26 | 0 | 20 | 0 | 100 | 26 | 53 | True |
| 5 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |

## 예측 근거와 탐색 정지 이유

- B: status `{"documented": 1492, "retrieved": 136}`  stops `{"found": 1628}`
- C: status `{"learned": 467, "documented": 34}`  stops `{"found": 501, "nodes": 6}`
- ORACLE: status `{"oracle": 105}`  stops `{"found": 105}`

학습 비용(모델 구축 s, seed별): `{"1": {"B": {"build_s": 0.005539099976886064}, "C": {"build_s": 0.012077099992893636}, "ORACLE": {"build_s": 6.299989763647318e-06}, "explore": {"explore_s": 7.315107899979921, "targeted_steps": 10, "steps": 300, "first_success": {"mkdir": 11, "delete": 13, "move": 15, "copy": 27}}}, "2": {"B": {"build_s": 0.006839400011813268}, "C": {"build_s": 0.016311399987898767}, "explore": {"explore_s": 7.167446899984498, "targeted_steps": 16, "steps": 300, "first_success": {"move": 1, "delete": 2, "mkdir": 3, "copy": 45, "convert": 91}}}, "3": {"B": {"build_s": 0.0067337999935261905}, "C": {"build_s": 0.012468300003092736}, "explore": {"explore_s": 6.466846499999519, "targeted_steps": 11, "steps": 300, "first_success": {"delete": 8, "mkdir": 24, "copy": 46, "move": 88, "convert": 120}}}, "4": {"B": {"build_s": 0.006461799988755956}, "C": {"build_s": 0.015894199983449653}, "explore": {"explore_s": 6.643004299985478, "targeted_steps": 14, "steps": 300, "first_success": {"mkdir": 0, "delete": 4, "move": 9, "copy": 19, "convert": 87}}}, "5": {"B": {"build_s": 0.006842799979494885}, "C": {"build_s": 0.015203199989628047}, "explore": {"explore_s": 7.001079400011804, "targeted_steps": 7, "steps": 300, "first_success": {"mkdir": 0, "delete": 5, "copy": 41, "move": 78, "convert": 262}}}}`
저장(journal bytes, seed→조건): `{"1": {"B": {"journal_bytes": 1253376, "model_json_bytes": 44}, "C": {"journal_bytes": 241664, "model_json_bytes": 5168}, "ORACLE": {"journal_bytes": 413696, "model_json_bytes": 28}}, "2": {"B": {"journal_bytes": 1167360, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6620}}, "3": {"B": {"journal_bytes": 1191936, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6616}}, "4": {"B": {"journal_bytes": 1130496, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6618}}, "5": {"B": {"journal_bytes": 1146880, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6616}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
