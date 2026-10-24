# P1 결과 — 동일 경험 시험

판정: **EXPLORATORY**  · 2차(D−C): n/a

protocol: `null`

환경: `{"python": "3.13.12", "platform": "Windows-11-10.0.26200-SP0", "machine": "ANSEOK-9950X3D", "cpus": 32, "env_version": "fsworld-1/py3.13/win32", "budget": {"actions": 20, "predictions": 400000, "nodes": 600, "depth": 12, "seconds": 180.0}, "steps": null, "tasks": 2, "seeds": [1], "split": "dev", "adapt": false, "policy": null, "body": "fs", "learner_version": 4, "source_sha256": "f55f4d6ab689b5b0", "source_files": 37, "git_head": "2cbd24f", "git_atanor_os_untracked_or_modified": true}`

검사: `{"unreachable": 0, "label": "exploratory", "body": "fs"}`

## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)

| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | 2 | 1.000 | 1.000 | 1.000 | 0 | 3.00 | 0.00 | 0 | 0 | 0 | 0 | 0/6 | 0.00 | 0.041 | 0.016 | 923 | 0.0 |
| CT | 2 | 1.000 | 1.000 | 1.000 | 0 | 3.00 | 0.00 | 0 | 0 | 0 | 0 | 0/6 | 0.00 | 0.040 | 0.016 | 923 | 0.0 |
| E | 2 | 1.000 | 1.000 | 1.000 | 0 | 3.00 | 0.00 | 0 | 0 | 0 | 0 | 0/6 | 0.00 | 0.161 | 0.133 | 2044 | 0.0 |

## 템플릿별 완수율

| 조건 | backup | convert |
|---|---:|---:|
| C | 1.00 | 1.00 |
| CT | 1.00 | 1.00 |
| E | 1.00 | 1.00 |

## Paired 비교 (완수율, 퍼센트포인트)

| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |
|---|---:|---|---|---|
| E-C | +0.0 | 0/2/0 | 1/1 | 1:+0 |
| E-CT | +0.0 | 0/2/0 | 1/1 | 1:+0 |
| CT-C | +0.0 | 0/2/0 | 1/1 | 1:+0 |

## 규칙 일치 — 고정 모델 vs 진실 의미론 (seed별 새 상황, 셀당 ≥ 20; fp=성공 오예측, fn=실패 오예측, eff=효과 오예측)

| seed | 조건 | 정확 도구 | 어떤 도구 | 검사 | fp | fn | eff | 설명서 답 |
|---|---|---:|---|---:|---:|---:|---:|---:|
| 1 | C | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 1 | CT | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |
| 1 | E | 5/5 | convert copy delete mkdir move | 200 | 0 | 0 | 0 | 0 |

## 예측 근거와 탐색 정지 이유

- C: status `{"learned": 6}`  stops `{"found": 6}`
- CT: status `{"learned": 6}`  stops `{"found": 6}`
- E: status `{"learned": 6}`  stops `{"found": 6}`

학습 비용(모델 구축 s, seed별): `{"1": {"C": {"build_s": 0.0023951000184752047}, "CT": {"build_s": 0.00343440001597628, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 1.8482913000043482}}, "E": {"build_s": 0.003656299988506362, "train_phase": {"episodes": 20, "completed": 20, "experiences": 76, "wall_s": 1.8482913000043482}, "macros": 5, "macro_extraction_s": 0.0005402000097092241}}}`
저장(journal bytes, seed→조건): `{"1": {"C": {"journal_bytes": 36864, "model_json_bytes": 6734}, "CT": {"journal_bytes": 36864, "model_json_bytes": 6735}, "E": {"journal_bytes": 36864, "model_json_bytes": 7466}}}`

## 주장할 수 없는 것

- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.
- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.
- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.
- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.
- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).
