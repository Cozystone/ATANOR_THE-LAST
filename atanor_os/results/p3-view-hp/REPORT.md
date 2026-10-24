# P1 결과 — 동일 경험 시험

판정: **REPLICATION**  · 2차(D−C): n/a

protocol: `{"version": 1, "body": "view", "frozen_at": "2026-10-24T09:40:00", "hypothesis": "H3 (transfer): the learner, planner and acquisition policy that produced the filesystem results, with no body-specific code, acquire the view body's tool rules from 600 exploration steps and act on unseen test tasks (target panel p3, extensions md/log/json and key ext as goals, a busier start screen) at least as well as exact-signature retrieval (B).", "primary": "C strict completion vs B, paired by (seed, task)", "primary_pair": ["C", "B"], "primary_metric": "completion", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "decision": "VALID_BOUNDED_GAIN / VALID_NO_GAIN (C-B <= 0) / VALID_INCONCLUSIVE exactly as in protocol.json v3. Expectation stated before the run, from the dev split (seed 1: A = B = C = 12/12): completion saturates on this body, so VALID_NO_GAIN is the likely verdict and the transfer claim rests on the secondary measures below, frozen here before any test task is run.", "secondary": {"rule_agreement": "per (seed, condition) the frozen model is checked against the evaluator's true semantics on fresh train-distribution situations, >= 20 per (tool, true outcome) cell (eval.oracle.rule_agreement): fp = predicted success where the tool really failed, fn = predicted failure where it succeeded, eff = wrong predicted attributes. A tool counts as learned when fp = fn = eff = 0. Transfer claim for the body: C has >= 5 of 6 tools learned in >= 4 of 5 seeds; A (documentation only) is expected to show fp > 0 on filter/group/compare/sort and B to answer from documentation on a large share of fresh situations.", "waste": "no-op real actions per episode, C vs A and C vs B (A acts on optimistic documentation and is expected to waste actions)", "cost": "exploration 600 steps per seed, model build seconds, wall seconds per episode, journal bytes"}, "conditions": "A, B, C + ORACLE (D omitted as in v3)", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 600, "policy": "contrast-kind", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity tests not run or failed", "unreachable task", "label != pre-registered", "source changed during the run (sha256 of the package at start != at end)"], "known_limits": ["value objects ext:md/log/json, key:ext and panel p3 exist in the exploration universe (as md existed in the filesystem POOL); what is new in test are the tasks: target p3, those extensions and key as goals, two open panels with one filtered at the start, 7 focus / 7 regroup / 6 compare", "the documentation given to every condition is nearly complete for this body (missing: all preconditions, compare's inherited filter/sort), so A can succeed by trial and error within 20 actions; completion is therefore not expected to separate conditions", "tasks need at most 3 actions; the body does not test deep planning", "dev-split results (A = B = C = 12/12, seed 1) and dev coverage of the policies novelty/contrast-role/contrast-kind were seen before freezing; no test task was run", "learner v3 (type groups), v4 (effect language: copies of any attribute) and the contrast-kind policy were developed on this body's dev split after the v3 filesystem runs; the filesystem C episodes were re-checked bit-identical under v4 (DECISIONS.md)"], "iteration_cap": "one pre-registered run; any change after seeing test results goes to protocol_view.json version 2"}`

환경: `{"python": "3.13.17", "platform": "Windows-10-10.0.19045-SP0", "machine": "DESKTOP-N6RR73M", "cpus": 8, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 600, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast-kind", "body": "view", "learner_version": 4, "source_sha256": "6ac1457be2fcf22c", "source_files": 37, "git": "unavailable: FileNotFoundError", "source_sha256_at_start": "6ac1457be2fcf22c"}`

검사: `{"label": "replication-hp", "policy": "contrast-kind", "body": "view", "semantics_ok": true, "semantics_seed": 4189725752, "semantics_cells": {"open:success": 20, "open:failure": 20, "close:success": 20, "close:failure": 20, "filter:success": 20, "filter:failure": 20, "sort:success": 20, "sort:failure": 20, "group:success": 20, "group:failure": 20, "compare:success": 20, "compare:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "learner_tests_passed": true, "unreachable": 0, "source_changed_during_run": false, "protocol_file": "C:\\Users\\test\\ATANOR\\dev4\\atanor_os\\protocol_view.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.700 | 0.700 | 0.925 | 0 | 8.25 | 5.60 | 0 | 0 | 30 | 0 | 590/825 | 1.00 | 26.063 | 25.997 | 127472 | 1033.3 |
| B | 100 | 0.820 | 0.820 | 0.955 | 0 | 5.98 | 2.33 | 0 | 0 | 18 | 0 | 233/598 | 0.53 | 1.600 | 1.558 | 7611 | 54.0 |
| C | 100 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/265 | 0.00 | 0.239 | 0.225 | 4125 | 9.2 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 2.65 | 0.00 | 0 | 0 | 0 | 0 | 0/53 | 0.00 | 0.151 | 0.138 | 4125 | 7.4 |

## 템플릿별 완수율

| 조건 | compare | focus | regroup |
|---|---:|---:|---:|
| A | 0.00 | 1.00 | 1.00 |
| B | 0.40 | 1.00 | 1.00 |
| C | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +18.0 | 6/14/0 | 5/5 | 1:+20, 2:+20, 3:+10, 4:+10, 5:+30 |
| B-A | +12.0 | 6/14/0 | 5/5 | 1:+10, 2:+10, 3:+20, 4:+20, 5:+0 |
| C-A | +30.0 | 6/14/0 | 5/5 | 1:+30, 2:+30, 3:+30, 4:+30, 5:+30 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측)

| seed | 조건 | 정확 도구 | 어떤 도구 | 검사 | fp | fn | eff | 설명서 답 |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 1 | A | 0/6 | - | 240 | 120 | 0 | 20 | 240 |
| 1 | B | 2/6 | close open | 240 | 52 | 0 | 2 | 94 |
| 1 | C | 6/6 | close compare filter group open sort | 240 | 0 | 0 | 0 | 0 |
| 1 | ORACLE | 6/6 | close compare filter group open sort | 240 | 0 | 0 | 0 | 0 |
| 2 | A | 0/6 | - | 240 | 120 | 0 | 20 | 240 |
| 2 | B | 2/6 | close open | 240 | 57 | 0 | 0 | 95 |
| 2 | C | 6/6 | close compare filter group open sort | 240 | 0 | 0 | 0 | 0 |
| 3 | A | 0/6 | - | 240 | 120 | 0 | 20 | 240 |
| 3 | B | 2/6 | close open | 240 | 46 | 0 | 2 | 88 |
| 3 | C | 6/6 | close compare filter group open sort | 240 | 0 | 0 | 0 | 0 |
| 4 | A | 0/6 | - | 240 | 120 | 0 | 20 | 240 |
| 4 | B | 2/6 | close open | 240 | 66 | 0 | 1 | 97 |
| 4 | C | 6/6 | close compare filter group open sort | 240 | 0 | 0 | 0 | 0 |
| 5 | A | 0/6 | - | 240 | 120 | 0 | 20 | 240 |
| 5 | B | 1/6 | close | 240 | 53 | 0 | 7 | 108 |
| 5 | C | 4/6 | close compare filter open | 240 | 1 | 1 | 0 | 0 |

## 예측 근거와 탐색 정지 이유

- A: status `{"documented": 825}`  stops `{"found": 825}`
- B: status `{"retrieved": 280, "documented": 318}`  stops `{"found": 598}`
- C: status `{"learned": 265}`  stops `{"found": 265}`
- ORACLE: status `{"oracle": 53}`  stops `{"found": 53}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": {"build_s": 2.2300002456177026e-05}, "B": {"build_s": 0.02465469999879133}, "C": {"build_s": 0.0643357000008109}, "ORACLE": {"build_s": 6.800000846851617e-06}}, "2": {"A": {"build_s": 2.179999864893034e-05}, "B": {"build_s": 0.02377659999910975}, "C": {"build_s": 0.051729999999224674}}, "3": {"A": {"build_s": 1.4099998224992305e-05}, "B": {"build_s": 0.02225660000112839}, "C": {"build_s": 0.06366939999861643}}, "4": {"A": {"build_s": 2.1699997887481004e-05}, "B": {"build_s": 0.02511670000239974}, "C": {"build_s": 0.05821300000388874}}, "5": {"A": {"build_s": 3.1400006264448166e-05}, "B": {"build_s": 0.022456400001829024}, "C": {"build_s": 0.048623000002407935}}}`
저장(journal bytes, seed→조건): `{"1": {"A": {"journal_bytes": 724992, "model_json_bytes": 23}, "B": {"journal_bytes": 548864, "model_json_bytes": 44}, "C": {"journal_bytes": 249856, "model_json_bytes": 14220}, "ORACLE": {"journal_bytes": 249856, "model_json_bytes": 46}}, "2": {"A": {"journal_bytes": 724992, "model_json_bytes": 23}, "B": {"journal_bytes": 561152, "model_json_bytes": 44}, "C": {"journal_bytes": 249856, "model_json_bytes": 13965}}, "3": {"A": {"journal_bytes": 724992, "model_json_bytes": 23}, "B": {"journal_bytes": 417792, "model_json_bytes": 44}, "C": {"journal_bytes": 249856, "model_json_bytes": 14479}}, "4": {"A": {"journal_bytes": 724992, "model_json_bytes": 23}, "B": {"journal_bytes": 421888, "model_json_bytes": 44}, "C": {"journal_bytes": 249856, "model_json_bytes": 15160}}, "5": {"A": {"journal_bytes": 724992, "model_json_bytes": 23}, "B": {"journal_bytes": 708608, "model_json_bytes": 44}, "C": {"journal_bytes": 249856, "model_json_bytes": 13288}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
