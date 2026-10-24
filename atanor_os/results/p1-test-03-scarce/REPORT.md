# P1 결과 — 동일 경험 시험

판정: **INVALID**  · 2차(D−C): n/a

protocol: `{"version": 3, "frozen_at": "2026-10-24T08:26:35", "supersedes": "v2.1 (kept in results/p1-test-02/protocol_used.json). v3 keeps every v2.1 rule and adds the H1 acquisition-policy question.", "hypothesis": "H1: a fixed acquisition policy that prefers tools with few successes and, within a tool, untried signatures one literal away from a known success ('contrast') yields rules that fix C's sort/backup failures; 'scarce' (tool weighting only) is the ablation.", "primary": "C strict completion under policy=contrast vs C under policy=novelty (results/p1-test-02), paired by (seed, task); same test split, seeds, budget, 300 steps; computed by `python -m atanor_os compare`", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "decision": "H1 GAIN if C(contrast)-C(novelty) >= min_gain_pp and seeds_ge >= 4; NO GAIN if <= 0; else INCONCLUSIVE. Secondary: same for scarce; C-B inside each run; rule exactness per tool from model_C.json (known from the dev coverage check: contrast gives exact convert rules in 4/5 seeds).", "conditions": "A, B, C + ORACLE (D omitted: its question was answered in v2 and it costs ~10x)", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity tests not run or failed", "unreachable task", "label != pre-registered"], "known_limits": ["blocked is structurally 0 (the planner never proposes capability-gated tools)", "B is exact-signature retrieval and therefore coverage-limited; C-B mixes rule induction with generalization beyond the explored signatures (docs_share column makes this visible)", "md objects already occur during exploration (POOL); what is new in test: object and directory names, 3-4 files, extensions log/json, depth-2 target chains, more required steps", "the dev coverage check used the same exploration seeds as the test run, so rule-exactness outcomes were seen before freezing; test-task completion was not"], "iteration_cap": "P2 allows at most 3 single-hypothesis changes (H1 is the first)"}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "scarce", "source_sha256": "3238a5257007582b", "source_files": 37, "git_head": "2cbd24f", "git_atanor_os_untracked_or_modified": true}`

검사: `{"label": "pre-registered", "policy": "scarce", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"mkdir:success": 20, "mkdir:failure": 20, "copy:success": 20, "copy:failure": 20, "move:success": 20, "move:failure": 20, "delete:success": 20, "delete:failure": 20, "convert:success": 20, "convert:failure": 20}, "semantics_mismatch": 0, "tests_passed": false, "learner_tests_passed": true, "unreachable": 0}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.200 | 0.200 | 0.200 | 0 | 19.20 | 18.70 | 0 | 0 | 80 | 0 | 1890/1920 | 1.00 | 6.378 | 6.242 | 23708 | 10.8 |
| B | 100 | 0.360 | 0.360 | 0.387 | 0 | 16.66 | 15.12 | 0 | 0 | 64 | 0 | 1530/1666 | 0.93 | 9.478 | 9.291 | 50152 | 37.4 |
| C | 100 | 1.000 | 1.000 | 1.000 | 0 | 5.65 | 0.40 | 0 | 0 | 0 | 0 | 40/565 | 0.00 | 3.957 | 3.895 | 120854 | 124.9 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/105 | 0.00 | 2.269 | 2.215 | 102426 | 58.4 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| A | 0.00 | 0.67 | 0.00 |
| B | 0.46 | 0.67 | 0.00 |
| C | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +64.0 | 16/4/0 | 5/5 | 1:+60, 2:+60, 3:+60, 4:+60, 5:+80 |
| B-A | +16.0 | 4/16/0 | 5/5 | 1:+20, 2:+20, 3:+20, 4:+20, 5:+0 |
| C-A | +80.0 | 16/4/0 | 5/5 | 1:+80, 2:+80, 3:+80, 4:+80, 5:+80 |

## 예측 근거와 탐색 정지 이유

- A: status `{"documented": 1920}`  stops `{"found": 1920}`
- B: status `{"documented": 1545, "retrieved": 121}`  stops `{"found": 1666}`
- C: status `{"learned": 565}`  stops `{"found": 565}`
- ORACLE: status `{"oracle": 105}`  stops `{"found": 105}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": 1.1600001016631722e-05, "B": 0.007058699993649498, "C": 0.010153099981835112, "ORACLE": 7.90000194683671e-06}, "2": {"A": 1.1299998732283711e-05, "B": 0.004404700011946261, "C": 0.010130000009667128}, "3": {"A": 1.300001167692244e-05, "B": 0.0048006999713834375, "C": 0.00978309998754412}, "4": {"A": 1.3300013961270452e-05, "B": 0.007614700007252395, "C": 0.010890200006542727}, "5": {"A": 1.1199997970834374e-05, "B": 0.00512489999528043, "C": 0.009842900006333366}}`
저장(journal bytes, seed→조건): `{"1": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1155072, "model_json_bytes": 44}, "C": {"journal_bytes": 401408, "model_json_bytes": 3568}, "ORACLE": {"journal_bytes": 405504, "model_json_bytes": 28}}, "2": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1179648, "model_json_bytes": 44}, "C": {"journal_bytes": 434176, "model_json_bytes": 3435}}, "3": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1175552, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 3436}}, "4": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1134592, "model_json_bytes": 44}, "C": {"journal_bytes": 409600, "model_json_bytes": 3436}}, "5": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1294336, "model_json_bytes": 44}, "C": {"journal_bytes": 434176, "model_json_bytes": 3436}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
