# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): n/a

protocol: `{"version": 1, "part_of": "protocol_h4.json", "role": "control", "body": "fs", "frozen_at": "2026-10-24T12:40:00", "hypothesis": "H4 control run on the fs body: policy contrast-kind", "primary": "per-run verdict = C vs B strict completion (unchanged harness rule); the H4 decision is cross-run, see protocol_h4.json", "primary_pair": ["C", "B"], "primary_metric": "completion", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "policy": "contrast-kind", "conditions_list": ["B", "C"], "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity gate not run or failed", "unreachable task", "label != pre-registered", "source changed during the run", "protocol parameter mismatch"]}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast-kind", "body": "fs", "learner_version": 4, "source_sha256": "0d580bbad1819684", "source_files": 41, "git": "not a repository (snapshot copy)", "source_sha256_at_start": "0d580bbad1819684"}`

검사: `{"label": "pre-registered", "policy": "contrast-kind", "body": "fs", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"mkdir:success": 20, "mkdir:failure": 20, "copy:success": 20, "copy:failure": 20, "move:success": 20, "move:failure": 20, "delete:success": 20, "delete:failure": 20, "convert:success": 20, "convert:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "tests_gate": "not learning and not timing and not view", "learner_tests_passed": true, "protocol_mismatch": [], "unreachable": 0, "source_changed_during_run": false, "protocol_file": "atanor_os\\protocol_h4_fs_control.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B | 100 | 0.360 | 0.360 | 0.389 | 0 | 16.71 | 15.13 | 0 | 0 | 64 | 0 | 1531/1671 | 0.92 | 13.745 | 13.607 | 53025 | 36.6 |
| C | 100 | 1.000 | 1.000 | 1.000 | 0 | 5.57 | 0.32 | 0 | 0 | 0 | 0 | 32/557 | 0.00 | 5.795 | 5.741 | 120608 | 124.2 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/105 | 0.00 | 3.385 | 3.325 | 102426 | 58.3 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| B | 0.46 | 0.67 | 0.00 |
| C | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +64.0 | 16/4/0 | 5/5 | 1:+60, 2:+80, 3:+60, 4:+60, 5:+60 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측, unk=효과 미정, near=성공과 인자 하나 차이인 실패)

| seed | 조건 | 정확 도구 | 엄격 도구 | 어떤 도구(정확) | 검사 | fp | fn | eff | unk | near 검사 | near fp | 설명서 답 | 셀 충족 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | B | 2/5 | 2/5 | delete mkdir | 200 | 22 | 0 | 20 | 0 | 100 | 22 | 35 | True |
| 1 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 1 | ORACLE | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 2 | B | 1/5 | 1/5 | mkdir | 200 | 27 | 0 | 20 | 0 | 100 | 27 | 44 | True |
| 2 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 3 | B | 2/5 | 2/5 | delete mkdir | 200 | 18 | 0 | 20 | 0 | 100 | 18 | 40 | True |
| 3 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 4 | B | 0/5 | 0/5 | - | 200 | 36 | 0 | 15 | 0 | 100 | 36 | 59 | True |
| 4 | C | 5/5 | 4/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 20 | 100 | 0 | 0 | True |
| 5 | B | 2/5 | 2/5 | delete mkdir | 200 | 24 | 0 | 20 | 0 | 100 | 24 | 46 | True |
| 5 | C | 4/5 | 4/5 | copy delete mkdir move | 200 | 1 | 0 | 0 | 20 | 100 | 1 | 0 | True |

## 예측 근거와 탐색 정지 이유

- B: status `{"documented": 1541, "retrieved": 130}`  stops `{"found": 1671}`
- C: status `{"learned": 557}`  stops `{"found": 557}`
- ORACLE: status `{"oracle": 105}`  stops `{"found": 105}`

학습 비용(모델 구축 s, seed별): `{"1": {"B": {"build_s": 0.00756800000090152}, "C": {"build_s": 0.017417099996237084}, "ORACLE": {"build_s": 6.500020390376449e-06}, "explore": {"explore_s": 6.866485400008969, "targeted_steps": 0, "steps": 300, "first_success": {"copy": 3, "move": 7, "mkdir": 9, "delete": 11, "convert": 121}}}, "2": {"B": {"build_s": 0.006869999982882291}, "C": {"build_s": 0.01742540000122972}, "explore": {"explore_s": 6.159926699998323, "targeted_steps": 0, "steps": 300, "first_success": {"move": 1, "delete": 2, "mkdir": 3, "copy": 28, "convert": 174}}}, "3": {"B": {"build_s": 0.005868100008228794}, "C": {"build_s": 0.014690899988636374}, "explore": {"explore_s": 6.709089300013147, "targeted_steps": 0, "steps": 300, "first_success": {"delete": 3, "copy": 10, "mkdir": 26, "move": 96, "convert": 110}}}, "4": {"B": {"build_s": 0.006208799983141944}, "C": {"build_s": 0.015837099985219538}, "explore": {"explore_s": 6.133519700000761, "targeted_steps": 0, "steps": 300, "first_success": {"mkdir": 0, "delete": 4, "move": 9, "copy": 33, "convert": 210}}}, "5": {"B": {"build_s": 0.007177100022090599}, "C": {"build_s": 0.01593039999715984}, "explore": {"explore_s": 6.7060861000209115, "targeted_steps": 0, "steps": 300, "first_success": {"mkdir": 0, "delete": 5, "copy": 43, "move": 44, "convert": 162}}}}`
저장(journal bytes, seed→조건): `{"1": {"B": {"journal_bytes": 1179648, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6624}, "ORACLE": {"journal_bytes": 413696, "model_json_bytes": 28}}, "2": {"B": {"journal_bytes": 1253376, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6620}}, "3": {"B": {"journal_bytes": 1155072, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 6618}}, "4": {"B": {"journal_bytes": 1204224, "model_json_bytes": 44}, "C": {"journal_bytes": 446464, "model_json_bytes": 6530}}, "5": {"B": {"journal_bytes": 1196032, "model_json_bytes": 44}, "C": {"journal_bytes": 446464, "model_json_bytes": 6528}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
