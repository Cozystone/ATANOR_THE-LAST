# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): n/a

protocol: `{"version": 1, "part_of": "protocol_h4.json", "role": "target", "body": "view", "frozen_at": "2026-10-24T12:40:00", "hypothesis": "H4 target run on the view body: policy contrast-pair", "primary": "per-run verdict = C vs B strict completion (unchanged harness rule); the H4 decision is cross-run, see protocol_h4.json", "primary_pair": ["C", "B"], "primary_metric": "completion", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 600, "policy": "contrast-pair", "conditions_list": ["B", "C"], "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity gate not run or failed", "unreachable task", "label != pre-registered", "source changed during the run", "protocol parameter mismatch"]}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 600, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast-pair", "body": "view", "learner_version": 4, "source_sha256": "0d580bbad1819684", "source_files": 41, "git": "not a repository (snapshot copy)", "source_sha256_at_start": "0d580bbad1819684"}`

검사: `{"label": "pre-registered", "policy": "contrast-pair", "body": "view", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"open:success": 20, "open:failure": 20, "close:success": 20, "close:failure": 20, "filter:success": 20, "filter:failure": 20, "sort:success": 20, "sort:failure": 20, "group:success": 20, "group:failure": 20, "compare:success": 20, "compare:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "tests_gate": "not learning and not timing and not fs", "learner_tests_passed": true, "protocol_mismatch": [], "unreachable": 0, "source_changed_during_run": false, "protocol_file": "atanor_os\\protocol_h4_view_target.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B | 100 | 0.760 | 0.760 | 0.940 | 0 | 7.09 | 3.16 | 0 | 0 | 24 | 0 | 316/709 | 0.57 | 1.288 | 1.250 | 8382 | 56.7 |
| C | 100 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/265 | 0.00 | 0.145 | 0.133 | 4125 | 8.6 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/53 | 0.00 | 0.099 | 0.083 | 4125 | 7.2 |

## 템플릿별 완수율

| 조건 | compare | focus | regroup |
|---|---:|---:|---:|
| B | 0.20 | 1.00 | 1.00 |
| C | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +24.0 | 6/14/0 | 5/5 | 1:+30, 2:+30, 3:+10, 4:+20, 5:+30 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측, unk=효과 미정, near=성공과 인자 하나 차이인 실패)

| seed | 조건 | 정확 도구 | 엄격 도구 | 어떤 도구(정확) | 검사 | fp | fn | eff | unk | near 검사 | near fp | 설명서 답 | 셀 충족 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | B | 2/6 | 2/6 | close open | 246 | 29 | 0 | 7 | 0 | 120 | 24 | 86 | True |
| 1 | C | 6/6 | 6/6 | close compare filter group open sort | 246 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 1 | ORACLE | 6/6 | 6/6 | close compare filter group open sort | 246 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 2 | B | 2/6 | 2/6 | close open | 243 | 22 | 0 | 1 | 0 | 120 | 20 | 69 | True |
| 2 | C | 6/6 | 6/6 | close compare filter group open sort | 243 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 3 | B | 2/6 | 2/6 | close open | 250 | 32 | 0 | 3 | 0 | 120 | 22 | 82 | True |
| 3 | C | 6/6 | 6/6 | close compare filter group open sort | 250 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 4 | B | 2/6 | 2/6 | close open | 251 | 23 | 0 | 3 | 0 | 120 | 18 | 66 | True |
| 4 | C | 6/6 | 6/6 | close compare filter group open sort | 251 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 5 | B | 2/6 | 2/6 | close open | 242 | 25 | 0 | 1 | 0 | 120 | 25 | 66 | True |
| 5 | C | 6/6 | 6/6 | close compare filter group open sort | 242 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |

## 예측 근거와 탐색 정지 이유

- B: status `{"retrieved": 304, "documented": 405}`  stops `{"found": 709}`
- C: status `{"learned": 265}`  stops `{"found": 265}`
- ORACLE: status `{"oracle": 53}`  stops `{"found": 53}`

학습 비용(모델 구축 s, seed별): `{"1": {"B": {"build_s": 0.01382940000621602}, "C": {"build_s": 0.034757900022668764}, "ORACLE": {"build_s": 6.799993570894003e-06}, "explore": {"explore_s": 6.1770258999895304, "targeted_steps": 27, "steps": 600, "first_success": {"sort": 7, "filter": 15, "open": 16, "close": 17, "group": 25, "compare": 110}}}, "2": {"B": {"build_s": 0.01613779997569509}, "C": {"build_s": 0.04207660001702607}, "explore": {"explore_s": 7.594999199995073, "targeted_steps": 23, "steps": 600, "first_success": {"close": 9, "open": 38, "filter": 39, "sort": 61, "group": 131, "compare": 151}}}, "3": {"B": {"build_s": 0.017324999993434176}, "C": {"build_s": 0.038814500003354624}, "explore": {"explore_s": 7.517032000003383, "targeted_steps": 23, "steps": 600, "first_success": {"close": 12, "sort": 20, "open": 29, "filter": 85, "compare": 162, "group": 202}}}, "4": {"B": {"build_s": 0.011801500018918887}, "C": {"build_s": 0.04121999998460524}, "explore": {"explore_s": 7.034233800019138, "targeted_steps": 21, "steps": 600, "first_success": {"close": 11, "open": 53, "sort": 54, "compare": 69, "group": 98, "filter": 101}}}, "5": {"B": {"build_s": 0.01694809997570701}, "C": {"build_s": 0.040393899980699643}, "explore": {"explore_s": 7.729985199985094, "targeted_steps": 29, "steps": 600, "first_success": {"close": 5, "open": 6, "sort": 85, "filter": 92, "compare": 112, "group": 170}}}}`
저장(journal bytes, seed→조건): `{"1": {"B": {"journal_bytes": 733184, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 13754}, "ORACLE": {"journal_bytes": 258048, "model_json_bytes": 46}}, "2": {"B": {"journal_bytes": 704512, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 14832}}, "3": {"B": {"journal_bytes": 434176, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 14847}}, "4": {"B": {"journal_bytes": 573440, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 14377}}, "5": {"B": {"journal_bytes": 733184, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 13299}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
