# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  (protocol: {"frozen_at": "2026-10-24T01:58:40", "primary": "C-B completion rate on split=test, learning state frozen (no online adaptation)", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "secondary": "D-C with the same thresholds (recorded, no effect on verdict); B-A and C-A reported", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "budget": {"actions": 20, "nodes": 600, "depth": 12, "seconds": 10.0}, "dev_reference": "atanor_os/runs/dev1: 2 seeds x 12 dev tasks -> A 0.083, B 0.375, C 1.000, D 0.375, ORACLE 1.000", "changes_after_dev": ["planner time cap 5 -> 10 s for all conditions (D hit the cap; cost is still reported)", "council shares one signature computation per prediction (cost only, no semantic change)", "exploration 200 -> 300 steps, signature repeat limit 2 (rare successes were missing at 200)"], "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics mismatch > 0", "tests fail", "unreachable task"]})

환경: `{"python": "3.13.17", "platform": "Windows-10-10.0.19045-SP0", "machine": "DESKTOP-N6RR73M", "cpus": 8, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "nodes": 600, "depth": 12, "seconds": 10.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false}`

검사: `{"semantics_checked": 300, "semantics_mismatch": 0, "tests_passed": true, "unreachable": 0, "label": "replication-hp"}`

## 조건별 (평가기가 실제 상태로 판정)

| 조건 | 에피소드 | 완수율 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 예산초과 | 차단 | 예측오류/예측 | wall s | cpu s | 확장노드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.100 | 0.200 | 0 | 19.70 | 19.30 | 0 | 90 | 0 | 1930/1970 | 9.765 | 9.648 | 66.5 | 9.5 |
| B | 100 | 0.190 | 0.322 | 0 | 18.26 | 17.09 | 2 | 79 | 0 | 1709/1826 | 14.377 | 14.256 | 118.2 | 15.8 |
| C | 100 | 0.710 | 0.710 | 0 | 4.73 | 1.80 | 29 | 0 | 0 | 180/473 | 3.837 | 3.811 | 101.5 | 38.4 |
| D | 100 | 0.370 | 0.423 | 0 | 9.47 | 8.00 | 41 | 22 | 0 | 800/947 | 16.994 | 16.934 | 82.9 | 13.8 |
| ORACLE | 20 | 1.000 | 1.000 | 0 | 5.55 | 0.00 | 0 | 0 | 0 | 0/111 | 5.056 | 5.013 | 240.8 | 38.7 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| A | 0.00 | 0.33 | 0.00 |
| B | 0.26 | 0.33 | 0.00 |
| C | 1.00 | 1.00 | 0.17 |
| D | 0.43 | 0.73 | 0.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +52.0 | 13/7/0 | 5/5 | 1:+65, 2:+50, 3:+65, 4:+40, 5:+40 |
| B-A | +9.0 | 3/17/0 | 5/5 | 1:+0, 2:+15, 3:+0, 4:+15, 5:+15 |
| C-A | +61.0 | 13/7/0 | 5/5 | 1:+65, 2:+65, 3:+65, 4:+55, 5:+55 |
| D-C | -34.0 | 0/7/13 | 1/5 | 1:-65, 2:-65, 3:-25, 4:-15, 5:+0 |

## 예측 근거 사용 (status 집계)

- A: `{"documented": 1970}`
- B: `{"documented": 1743, "retrieved": 83}`
- C: `{"learned": 377, "documented": 96}`
- D: `{"council_learned": 585, "council_documented": 362}`  의결 불일치율 0.420
- ORACLE: `{"oracle": 111}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": 6.100000973674469e-06, "B": 0.007559900001069764, "C": 0.015722699999969336, "D": 0.01641410000047472, "ORACLE": 2.5000008463393897e-06}, "2": {"A": 5.40000110049732e-06, "B": 0.007419300000037765, "C": 0.01529859999936889, "D": 0.015287900001567323}, "3": {"A": 5.399999281507917e-06, "B": 0.007782599999700324, "C": 0.0156635000003007, "D": 0.015340500000093016}, "4": {"A": 5.300000339047983e-06, "B": 0.00769399999990128, "C": 0.015222999998513842, "D": 0.015301900000849855}, "5": {"A": 5.29999852005858e-06, "B": 0.007607800000187126, "C": 0.014002100000652717, "D": 0.015730899998743553}}`
저장: `{"1": {"journal_bytes": 3637248}, "2": {"journal_bytes": 3543040}, "3": {"journal_bytes": 3620864}, "4": {"journal_bytes": 3661824}, "5": {"journal_bytes": 2973696}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
