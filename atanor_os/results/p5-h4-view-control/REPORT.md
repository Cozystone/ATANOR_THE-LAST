# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): n/a

protocol: `{"version": 1, "part_of": "protocol_h4.json", "role": "control", "body": "view", "frozen_at": "2026-10-24T12:40:00", "hypothesis": "H4 control run on the view body: policy contrast-kind", "primary": "per-run verdict = C vs B strict completion (unchanged harness rule); the H4 decision is cross-run, see protocol_h4.json", "primary_pair": ["C", "B"], "primary_metric": "completion", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 600, "policy": "contrast-kind", "conditions_list": ["B", "C"], "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity gate not run or failed", "unreachable task", "label != pre-registered", "source changed during the run", "protocol parameter mismatch"]}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 600, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast-kind", "body": "view", "learner_version": 4, "source_sha256": "0d580bbad1819684", "source_files": 41, "git": "not a repository (snapshot copy)", "source_sha256_at_start": "0d580bbad1819684"}`

검사: `{"label": "pre-registered", "policy": "contrast-kind", "body": "view", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"open:success": 20, "open:failure": 20, "close:success": 20, "close:failure": 20, "filter:success": 20, "filter:failure": 20, "sort:success": 20, "sort:failure": 20, "group:success": 20, "group:failure": 20, "compare:success": 20, "compare:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "tests_gate": "not learning and not timing and not fs", "learner_tests_passed": true, "protocol_mismatch": [], "unreachable": 0, "source_changed_during_run": false, "protocol_file": "atanor_os\\protocol_h4_view_control.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B | 100 | 0.820 | 0.820 | 0.955 | 0 | 5.98 | 2.33 | 0 | 0 | 18 | 0 | 233/598 | 0.53 | 1.173 | 1.140 | 7611 | 53.8 |
| C | 100 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/265 | 0.00 | 0.159 | 0.143 | 4125 | 8.8 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/53 | 0.00 | 0.097 | 0.087 | 4125 | 7.3 |

## 템플릿별 완수율

| 조건 | compare | focus | regroup |
|---|---:|---:|---:|
| B | 0.40 | 1.00 | 1.00 |
| C | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +18.0 | 6/14/0 | 5/5 | 1:+20, 2:+20, 3:+10, 4:+10, 5:+30 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측, unk=효과 미정, near=성공과 인자 하나 차이인 실패)

| seed | 조건 | 정확 도구 | 엄격 도구 | 어떤 도구(정확) | 검사 | fp | fn | eff | unk | near 검사 | near fp | 설명서 답 | 셀 충족 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | B | 2/6 | 2/6 | close open | 246 | 26 | 0 | 6 | 0 | 120 | 23 | 80 | True |
| 1 | C | 6/6 | 6/6 | close compare filter group open sort | 246 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 1 | ORACLE | 6/6 | 6/6 | close compare filter group open sort | 246 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 2 | B | 2/6 | 2/6 | close open | 243 | 26 | 0 | 1 | 0 | 120 | 24 | 68 | True |
| 2 | C | 6/6 | 6/6 | close compare filter group open sort | 243 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 3 | B | 2/6 | 2/6 | close open | 250 | 32 | 0 | 0 | 0 | 120 | 25 | 68 | True |
| 3 | C | 6/6 | 6/6 | close compare filter group open sort | 250 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 4 | B | 2/6 | 2/6 | close open | 251 | 27 | 0 | 3 | 0 | 120 | 20 | 76 | True |
| 4 | C | 6/6 | 6/6 | close compare filter group open sort | 251 | 0 | 0 | 0 | 0 | 120 | 0 | 0 | True |
| 5 | B | 2/6 | 2/6 | close open | 242 | 35 | 0 | 10 | 0 | 120 | 34 | 87 | True |
| 5 | C | 5/6 | 5/6 | close compare filter open sort | 242 | 0 | 1 | 0 | 0 | 120 | 0 | 0 | True |

## 예측 근거와 탐색 정지 이유

- B: status `{"retrieved": 280, "documented": 318}`  stops `{"found": 598}`
- C: status `{"learned": 265}`  stops `{"found": 265}`
- ORACLE: status `{"oracle": 53}`  stops `{"found": 53}`

학습 비용(모델 구축 s, seed별): `{"1": {"B": {"build_s": 0.014460300008067861}, "C": {"build_s": 0.04077130000223406}, "ORACLE": {"build_s": 6.500020390376449e-06}, "explore": {"explore_s": 4.079216499987524, "targeted_steps": 0, "steps": 600, "first_success": {"open": 18, "filter": 25, "close": 36, "sort": 92, "group": 104, "compare": 114}}}, "2": {"B": {"build_s": 0.020465000008698553}, "C": {"build_s": 0.045610400004079565}, "explore": {"explore_s": 4.867173899983754, "targeted_steps": 0, "steps": 600, "first_success": {"open": 16, "close": 33, "group": 57, "sort": 60, "compare": 68, "filter": 88}}}, "3": {"B": {"build_s": 0.017856599995866418}, "C": {"build_s": 0.04306180001003668}, "explore": {"explore_s": 4.929801999998745, "targeted_steps": 0, "steps": 600, "first_success": {"close": 31, "open": 36, "group": 39, "filter": 61, "sort": 107, "compare": 129}}}, "4": {"B": {"build_s": 0.017017200007103384}, "C": {"build_s": 0.04111499999999069}, "explore": {"explore_s": 4.668725399998948, "targeted_steps": 0, "steps": 600, "first_success": {"open": 21, "compare": 25, "filter": 37, "close": 42, "group": 48, "sort": 96}}}, "5": {"B": {"build_s": 0.015082500001881272}, "C": {"build_s": 0.0379143999889493}, "explore": {"explore_s": 4.389378699997906, "targeted_steps": 0, "steps": 600, "first_success": {"open": 16, "close": 20, "group": 84, "sort": 88, "filter": 99, "compare": 158}}}}`
저장(journal bytes, seed→조건): `{"1": {"B": {"journal_bytes": 561152, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 14220}, "ORACLE": {"journal_bytes": 258048, "model_json_bytes": 46}}, "2": {"B": {"journal_bytes": 569344, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 13965}}, "3": {"B": {"journal_bytes": 430080, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 14479}}, "4": {"B": {"journal_bytes": 434176, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 15160}}, "5": {"B": {"journal_bytes": 716800, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 13288}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
