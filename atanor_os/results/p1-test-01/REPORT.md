# P1 결과 — 동일 경험 시험

판정: **VALID_BOUNDED_GAIN**  (protocol: {"frozen_at": "2026-10-24T01:58:40", "primary": "C-B completion rate on split=test, learning state frozen (no online adaptation)", "min_gain_pp": 10.0, "seeds_ge": 4, "max_cost_ratio": 3.0, "secondary": "D-C with the same thresholds (recorded, no effect on verdict); B-A and C-A reported", "split": "test", "tasks": 20, "seeds": [1, 2, 3, 4, 5], "explore_steps": 300, "budget": {"actions": 20, "nodes": 600, "depth": 12, "seconds": 10.0}, "dev_reference": "atanor_os/runs/dev1: 2 seeds x 12 dev tasks -> A 0.083, B 0.375, C 1.000, D 0.375, ORACLE 1.000", "changes_after_dev": ["planner time cap 5 -> 10 s for all conditions (D hit the cap; cost is still reported)", "council shares one signature computation per prediction (cost only, no semantic change)", "exploration 200 -> 300 steps, signature repeat limit 2 (rare successes were missing at 200)"], "invalid_if": ["env_errors > 0", "ORACLE completion < 1.0", "semantics mismatch > 0", "tests fail", "unreachable task"]})

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "nodes": 600, "depth": 12, "seconds": 10.0}, "steps": 300, "tasks": 20, "seeds": [1, 2, 3, 4, 5], "split": "test", "adapt": false}`

검사: `{"semantics_checked": 300, "semantics_mismatch": 0, "tests_passed": true, "unreachable": 0}`

## 조건별 (평가기가 실제 상태로 판정)

| 조건 | 에피소드 | 완수율 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 예산초과 | 차단 | 예측오류/예측 | wall s | cpu s | 확장노드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 100 | 0.100 | 0.200 | 0 | 19.70 | 19.30 | 0 | 90 | 0 | 1930/1970 | 4.173 | 4.069 | 66.5 | 10.0 |
| B | 100 | 0.190 | 0.322 | 0 | 18.49 | 17.32 | 0 | 81 | 0 | 1732/1849 | 6.208 | 6.099 | 127.3 | 16.0 |
| C | 100 | 0.840 | 0.840 | 0 | 5.91 | 1.80 | 16 | 0 | 0 | 180/591 | 4.256 | 4.207 | 242.7 | 75.4 |
| D | 100 | 0.370 | 0.423 | 0 | 10.69 | 9.22 | 36 | 27 | 0 | 922/1069 | 14.533 | 14.278 | 274.7 | 25.3 |
| ORACLE | 20 | 1.000 | 1.000 | 0 | 5.55 | 0.00 | 0 | 0 | 0 | 0/111 | 2.167 | 2.152 | 240.8 | 38.8 |

## 템플릿별 완수율

| 조건 | backup | convert | sort |
|---|---:|---:|---:|
| A | 0.00 | 0.33 | 0.00 |
| B | 0.26 | 0.33 | 0.00 |
| C | 1.00 | 1.00 | 0.54 |
| D | 0.43 | 0.73 | 0.00 |
| ORACLE | 1.00 | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| C-B | +65.0 | 18/2/0 | 5/5 | 1:+85, 2:+70, 3:+90, 4:+40, 5:+40 |
| B-A | +9.0 | 3/17/0 | 5/5 | 1:+0, 2:+15, 3:+0, 4:+15, 5:+15 |
| C-A | +74.0 | 18/2/0 | 5/5 | 1:+85, 2:+85, 3:+90, 4:+55, 5:+55 |
| D-C | -47.0 | 0/2/18 | 1/5 | 1:-85, 2:-85, 3:-50, 4:-15, 5:+0 |

## 예측 근거 사용 (status 집계)

- A: `{"documented": 1970}`
- B: `{"documented": 1766, "retrieved": 83}`
- C: `{"learned": 495, "documented": 96}`
- D: `{"council_learned": 693, "council_documented": 376}`  의결 불일치율 0.421
- ORACLE: `{"oracle": 111}`

학습 비용(모델 구축 s, seed별): `{"1": {"A": 5.2000104915350676e-06, "B": 0.004709300003014505, "C": 0.007527000008849427, "D": 0.007870000001275912, "ORACLE": 2.5999906938523054e-06}, "2": {"A": 7.700000423938036e-06, "B": 0.004395500000100583, "C": 0.0074939999904017895, "D": 0.007829000009223819}, "3": {"A": 6.199989002197981e-06, "B": 0.004061899991938844, "C": 0.00768960002460517, "D": 0.007209100003819913}, "4": {"A": 1.1600001016631722e-05, "B": 0.003907700011041015, "C": 0.006755799986422062, "D": 0.0075234999821987}, "5": {"A": 9.500014130026102e-06, "B": 0.0037583000084850937, "C": 0.007926400023279712, "D": 0.0075471000163815916}}`
저장: `{"1": {"journal_bytes": 4046848}, "2": {"journal_bytes": 3891200}, "3": {"journal_bytes": 3837952}, "4": {"journal_bytes": 3715072}, "5": {"journal_bytes": 2973696}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
