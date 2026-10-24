# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  · 2차(D−C): n/a

protocol: `{"version": 4, "body": "fs", "frozen_at": "2026-10-24T09:40:00", "supersedes": "v3 (results/p1-test-03-contrast/protocol_used.json; protocol.json stays v3 for the scarce re-execution). v4 keeps every v3 rule and adds the H2 question.", "hypothesis": "H2: macros (pairs of tools whose argument slots are structurally related: same object, or directly under it) extracted from the agent's OWN completed training episodes reduce planning cost on unseen test tasks without losing completion. E = C + 20 training episodes' experience + macros; CT = C + the same training experience without macros, so E-CT isolates the macro effect from the extra experience.", "primary": "planner predictions per episode, E vs CT, paired by (seed, task)", "primary_pair": ["E", "CT"], "primary_metric": "plan_predicted", "max_ratio": 0.7, "max_loss_pp": 2.0, "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "decision": "H2 GAIN (VALID_BOUNDED_GAIN) if mean predictions E / mean predictions CT <= max_ratio, the per-seed ratio is <= max_ratio in >= seeds_ge seeds, and E-CT strict completion >= -max_loss_pp; NO GAIN if the ratio >= 1.0 or the completion loss exceeds max_loss_pp; otherwise INCONCLUSIVE. Secondary: C-B (replication of v3 under the same policy and seeds; expected +58 pp), CT-C (value of the 20 training episodes alone), E-C, and rule agreement per condition.", "conditions": "A, B, C, CT, E + ORACLE", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "policy": "contrast", "train_tasks": 20, "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics check not ok", "validity tests not run or failed", "unreachable task", "label != pre-registered", "source changed during the run (sha256 of the package at start != at end)"], "known_limits": ["macros are pairs of consecutive tools only, with argument-level structure (eq/child) and no attribute values", "training tasks come from the train split generator (indices 100-119) and are acted by C's frozen rules; CT and E therefore see 20 goal-directed episodes that A, B and C do not", "macro instances enlarge the candidate set at every expansion (each instance costs two predictions); whether depth reduction outweighs the larger branching is exactly the question", "C strict completion is already 0.94 under the contrast policy, so completion cannot show a large gain; the primary measure is therefore cost at no loss", "all v3 known limits apply (blocked structurally 0; B coverage-limited; md objects occur in exploration; dev coverage seen before freezing)"], "iteration_cap": "P2: H2 is the second of at most 3 single-hypothesis changes (H1 was the first)"}`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false, "policy": "contrast", "body": "fs", "learner_version": 4, "source_sha256": "6ac1457be2fcf22c", "source_files": 37, "git": "not a repository (snapshot copy)", "source_sha256_at_start": "6ac1457be2fcf22c"}`

검사: `{"label": "pre-registered", "policy": "contrast", "body": "fs", "semantics_ok": true, "semantics_seed": 3244639667, "semantics_cells": {"mkdir:success": 20, "mkdir:failure": 20, "copy:success": 20, "copy:failure": 20, "move:success": 20, "move:failure": 20, "delete:success": 20, "delete:failure": 20, "convert:success": 20, "convert:failure": 20}, "semantics_mismatch": 0, "tests_passed": true, "learner_tests_passed": true, "unreachable": 0, "source_changed_during_run": false, "protocol_file": "atanor_os\\protocol_h2.json"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.200 | 0.200 | 0.200 | 0 | 19.20 | 18.70 | 0 | 0 | 80 | 0 | 1890/1920 | 1.00 | 6.737 | 6.606 | 23708 | 11.0 |
| B | 100 | 0.360 | 0.360 | 0.389 | 0 | 16.71 | 15.11 | 0 | 0 | 64 | 0 | 1531/1671 | 0.92 | 11.516 | 11.380 | 50544 | 35.8 |
| C | 100 | 0.940 | 0.940 | 0.940 | 0 | 5.10 | 0.37 | 0 | 6 | 0 | 0 | 43/510 | 0.06 | 6.194 | 6.149 | 105351 | 127.2 |
| CT | 100 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/525 | 0.00 | 4.465 | 4.426 | 102426 | 61.8 |
| E | 100 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/525 | 0.00 | 8.701 | 8.648 | 37304 | 10.5 |
| ORACLE | 20 | 1.000 | 1.000 | 1.000 | 0 | 5.25 | 0.00 | 0 | 0 | 0 | 0 | 0/105 | 0.00 | 3.051 | 3.009 | 102426 | 59.1 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| A | 0.00 | 0.67 | 0.00 |
| B | 0.46 | 0.67 | 0.00 |
| C | 1.00 | 1.00 | 0.83 |
| CT | 1.00 | 1.00 | 1.00 |
| E | 1.00 | 1.00 | 1.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +58.0 | 16/4/0 | 5/5 | 1:+60, 2:+50, 3:+60, 4:+60, 5:+60 |
| B-A | +16.0 | 4/16/0 | 5/5 | 1:+20, 2:+0, 3:+20, 4:+20, 5:+20 |
| C-A | +74.0 | 16/4/0 | 5/5 | 1:+80, 2:+50, 3:+80, 4:+80, 5:+80 |
| E-C | +6.0 | 6/14/0 | 5/5 | 1:+0, 2:+30, 3:+0, 4:+0, 5:+0 |
| E-CT | +0.0 | 0/20/0 | 5/5 | 1:+0, 2:+0, 3:+0, 4:+0, 5:+0 |
| CT-C | +6.0 | 6/14/0 | 5/5 | 1:+0, 2:+30, 3:+0, 4:+0, 5:+0 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측)

| seed | 조건 | 정확 도구 | 어떤 도구 | 검사 | fp | fn | eff | 설명서 답 |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 1 | A | 0/5 | - | 200 | 100 | 0 | 20 | 200 |
| 1 | B | 0/5 | - | 200 | 49 | 0 | 20 | 62 |
| 1 | C | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 1 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 1 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 1 | ORACLE | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 2 | A | 0/5 | - | 200 | 100 | 0 | 20 | 200 |
| 2 | B | 0/5 | - | 200 | 53 | 0 | 20 | 90 |
| 2 | C | 3/5 | delete mkdir move | 200 | 18 | 0 | 20 | 32 |
| 2 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 2 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 3 | A | 0/5 | - | 200 | 100 | 0 | 20 | 200 |
| 3 | B | 0/5 | - | 200 | 56 | 0 | 20 | 73 |
| 3 | C | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 3 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 3 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 4 | A | 0/5 | - | 200 | 100 | 0 | 20 | 200 |
| 4 | B | 0/5 | - | 200 | 49 | 0 | 20 | 70 |
| 4 | C | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 4 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 4 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 5 | A | 0/5 | - | 200 | 100 | 0 | 20 | 200 |
| 5 | B | 0/5 | - | 200 | 49 | 0 | 20 | 62 |
| 5 | C | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 5 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 5 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |

## 예측 근거와 탐색 정지 이유

- A: status `{"documented": 1920}`  stops `{"found": 1920}`
- B: status `{"documented": 1534, "retrieved": 137}`  stops `{"found": 1671}`
- C: status `{"learned": 481, "documented": 29}`  stops `{"found": 510, "nodes": 6}`
- CT: status `{"learned": 525}`  stops `{"found": 525}`
- E: status `{"learned": 525}`  stops `{"found": 525}`
- ORACLE: status `{"oracle": 105}`  stops `{"found": 105}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": {"build_s": 1.4099990949034691e-05}, "B": {"build_s": 0.007768199982820079}, "C": {"build_s": 0.01196840000920929}, "CT": {"build_s": 0.019748799997614697, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 5.547754500003066}}, "E": {"build_s": 0.017346000007819384, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 5.547754500003066}, "macros": 5, "macro_extraction_s": 0.0016903999785427004}, "ORACLE": {"build_s": 7.299997378140688e-06}}, "2": {"A": {"build_s": 1.9800005247816443e-05}, "B": {"build_s": 0.00593980000121519}, "C": {"build_s": 0.009453600010601804}, "CT": {"build_s": 0.027988299989374354, "train_phase": {"episodes": 20, "completed": 20, "experiences": 146, "wall_s": 25.19705979997525}}, "E": {"build_s": 0.03157600000849925, "train_phase": {"episodes": 20, "completed": 20, "experiences": 146, "wall_s": 25.19705979997525}, "macros": 5, "macro_extraction_s": 0.0027424999861977994}}, "3": {"A": {"build_s": 1.09999964479357e-05}, "B": {"build_s": 0.006281900015892461}, "C": {"build_s": 0.015209400007734075}, "CT": {"build_s": 0.023239399975864217, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.658727100002579}}, "E": {"build_s": 0.0211571000108961, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.658727100002579}, "macros": 5, "macro_extraction_s": 0.002686899999389425}}, "4": {"A": {"build_s": 1.4900026144459844e-05}, "B": {"build_s": 0.006179400021210313}, "C": {"build_s": 0.01742390001891181}, "CT": {"build_s": 0.025322400004370138, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.619639299984556}}, "E": {"build_s": 0.026060500007588416, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.619639299984556}, "macros": 5, "macro_extraction_s": 0.0026818999904207885}}, "5": {"A": {"build_s": 1.4499993994832039e-05}, "B": {"build_s": 0.007224699977086857}, "C": {"build_s": 0.011011900001903996}, "CT": {"build_s": 0.026549200003501028, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.909128799976315}}, "E": {"build_s": 0.016835000016726553, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 6.909128799976315}, "macros": 5, "macro_extraction_s": 0.0015560999745503068}}}`
저장(journal bytes, seed→조건): `{"1": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1163264, "model_json_bytes": 44}, "C": {"journal_bytes": 401408, "model_json_bytes": 6734}, "CT": {"journal_bytes": 401408, "model_json_bytes": 6735}, "E": {"journal_bytes": 401408, "model_json_bytes": 7466}, "ORACLE": {"journal_bytes": 401408, "model_json_bytes": 28}}, "2": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1269760, "model_json_bytes": 44}, "C": {"journal_bytes": 258048, "model_json_bytes": 5172}, "CT": {"journal_bytes": 401408, "model_json_bytes": 6733}, "E": {"journal_bytes": 401408, "model_json_bytes": 7464}}, "3": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1179648, "model_json_bytes": 44}, "C": {"journal_bytes": 401408, "model_json_bytes": 6732}, "CT": {"journal_bytes": 401408, "model_json_bytes": 6735}, "E": {"journal_bytes": 401408, "model_json_bytes": 7466}}, "4": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1159168, "model_json_bytes": 44}, "C": {"journal_bytes": 401408, "model_json_bytes": 6731}, "CT": {"journal_bytes": 401408, "model_json_bytes": 6735}, "E": {"journal_bytes": 401408, "model_json_bytes": 7466}}, "5": {"A": {"journal_bytes": 1302528, "model_json_bytes": 23}, "B": {"journal_bytes": 1175552, "model_json_bytes": 44}, "C": {"journal_bytes": 401408, "model_json_bytes": 6731}, "CT": {"journal_bytes": 401408, "model_json_bytes": 6735}, "E": {"journal_bytes": 401408, "model_json_bytes": 7466}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
