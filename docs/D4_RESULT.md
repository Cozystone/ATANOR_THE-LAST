# Shared-world D1–D4 결과 — 64/64 완료 후 중단

2026-09-13. 최종 판정: **CAPABILITY_GATE_GREEN**, 알려진 파일 연산 과제 계열 안의 국소 결과.
사용자 지시대로 이 결과 정리 후 중단한다. 다음 단계, 추가 구현, 재튜닝, 새 평가를 시작하지 않는다.
프로덕션 배선/활성화 및 push 없음. 기존 ATANOR/Claude 작업 경로는 변경하지 않았다.

## 무엇이 완료됐는가

- D1: 감독자가 소유하는 지속 세계, 목표 교체, 실제 관측/예측 분리, 예산, 재시작 및 native 재실행 검증.
- D2: 같은 실측 경험으로 학습한 관계·공동 효과 후보와 전체 action-context 신경망 대조군.
- D3: 공통 제한 계획기, 실제 결과에 따른 모델 갱신, 다음 목표에서도 이어지는 상태/경험.
- D4: 사전등록된 64 life × 4 arm × 4 goal = 1,024개 episode의 단일 실행 및 증거 대조.

기제/평가기 테스트는 219 passed, 0 failures/errors/skips이다. 이는 능력 결과와 별개다.
최종 실행은 256개 arm-life 모두 native 재실행 및 독립 결속 검사를 통과했다.
초기 온라인/동결 후보의 첫 결정 64쌍도 모두 일치했다.

## 원시 결과

성공률과 행동 수는 life당 뒤의 두 평가 목표, 총 128개를 대상으로 한다.
CPU는 사전등록대로 학습비, 앞의 두 학습 목표를 포함한 전체 네 목표 수행,
계획/갱신/실제 실행/검증/직렬화 및 배분된 공통 실행비를 포함한다.
실패는 예산 8을 부과했다. 이번에는 모든 실패가 예산을 소진해 actual과 charged가 같다.

| 방식 | 평가 성공 | 평가 actual / charged 행동 | 전체 CPU 초 |
|---|---:|---:|---:|
| 관계·공동 효과 + 온라인 갱신 | 128/128 (100%) | 224 / 224 | 943.218750 |
| 전체 문맥 신경망: 사전 지정 주 대조군 | 96/128 (75%) | 480 / 480 | 1788.828125 |
| 동일 관계 후보, 모델 갱신 동결 | 128/128 (100%) | 320 / 320 | 1075.703125 |
| 검색 기반 보조 대조군 | 2/128 (1.5625%) | 1011 / 1011 | 6713.156250 |

주 대조군 대비 후보는 평가 행동 53.33%, 전체 CPU 47.27% 감소했다.
동결판도 100%를 풀었으므로 **온라인 갱신의 확인된 기여는 정확도 상승이 아니라
평가 행동 30% 감소**다. 모델 갱신이 아닌 모든 기억/적응을 끈 실험은 아니다.

## 사전등록 기준과 독립 재계산

64 life를 paired cluster로 재표집, PCG64 seed 91377, 4,000회,
linear quantile의 단측 95% 경계. 주 비교군을 사후 교체하지 않았다.

| 기준 | 실측 | 고정 통과선 |
|---|---:|---:|
| 주 대조군 성공률 | .75 | ≥ .50 |
| 후보 성공률 | 1.00 | ≥ .75 |
| 성공률 차이 하한 | .1953125 (+19.53125pp) | ≥ −.05 |
| 평가 행동 비율 point / 상한 | .466666667 / .520383693 | ≤ .80 / .90 |
| 전체 CPU 비율 point / 상한 | .527283050 / .571084119 | ≤ 1.00 / 1.10 |
| 동결판 대비 목표당 행동 절감 point / 하한 | .75 / .6953125 | 하한 > 0 |
| 동결판 대비 성공률 차이 하한 | 0 | ≥ −.05 |

7개 utility gate와 별도 online gate가 통과했다. 별도 검토자가 집계 함수를 호출하지 않고
원시 rows에서 bootstrap과 판정을 재계산하여 전부 일치함을 확인했다.
`report.rows == rows.jsonl`, GOAL_END 1,024개, DISPATCH 3,367개도 대조했다.
이 사후 감사는 산술/저장 journal 대조이며, 정책을 새로 실행한 두 번째 시험이 아니다.

실행 종료 후에도 고정된 60개 소스, 학습 산출물, 환경, preregistration이 일치했다.
저장된 64개 dataset 항목을 봉인된 generator/seed에서 재구성한 값과 비교해 일치했다.

## 비용과 한계

단일 시험 wall time은 10,580.754초, 약 2시간 56분이었다. 연구 구현, DEV 실행,
사후 산술 감사, 이 문서 작성, 보존 archive/git 작업은 배포 실행 비용 비교 밖이다.

| 방식 | 결정 p50 / p95 wall 초 | worker peak MiB |
|---|---:|---:|
| 관계 후보 | 1.0453 / 1.2065 | 516.10 |
| 전체 문맥 신경망 | .5423 / .6544 | 598.88 |
| 동결 관계 후보 | .9506 / 1.1105 | 516.07 |
| 검색 | 2.9911 / 3.4286 | 540.46 |

후보는 **결정 한 번의 지연은 주 대조군보다 길다**. 더 적은 행동으로 성공해 총 CPU를 줄였다.
worker RAM은 감독자 RAM을 포함하지 않는다. 전력을 측정하지 않아 뇌 수준 에너지 효율을 주장하지 않는다.

64 life는 **두 초기 관계 구조 템플릿**의 이름/handle/크기 변형이다. 새로운 mechanics,
64개의 서로 다른 문제 구조, 다른 몸 또는 학습 seed로의 전이가 아니다.
신뢰 경계는 고정 코드와 OS를 신뢰하는 로컬 감독자이며 외부 E5/E6 심판/악성 호스트 격리가 아니다.

목표와 관계 관측, 조건/효과 프로그램의 기본 문법은 제공됐다. 온라인 갱신은 평가 목표 중에도
계속되므로 학습 목표에서 얻은 지식의 무갱신 재사용만 분리한 시험도 아니다.
자율 개념 발명, 새로운 감각 표현, 자발적 목표/실험 선택, 완성된 4D 세계,
자의식, 평생 학습, 일반 전이, RSI 또는 AGI/ASI 도달은 아직 입증하지 않았다.
이 결과로 궁극 목표의 성공 확률을 80% 이상이라고 추정할 근거는 없다.

실제 첫 life의 7행동 기록은 [D4_LIFE_000_TRACE.md](D4_LIFE_000_TRACE.md)에 있다.
DEV에서 발견해 고친 실제 계획 결함과 수정 전 실패 증거는
[D3_REVISIT_CORRECTION.md](D3_REVISIT_CORRECTION.md)에 보존했다. 새 final 재시도는 없었다.

## 보존과 중단 상태

- 후보 소스 기준: `2716257719c0fe90edb107d3af70514c0d3ad834`.
- preregistration 커밋/실행 시작 HEAD: `fe27900ef26812e3d0007f0c9621893a2ca82ba6`.
- 코드가 아닌 중단 한도/첫 trace 문서는 실행 중 추가됐으며 소스는 변경하지 않았다.
- 원래 42개 action_core 파일은 baseline `9999824`와 byte-identical이다.
- 결과·원시 journal·dataset, training, 두 DEV 및 XML 증거를 이 저장소 `evidence/`에 보존했다.
- archive member를 원본과 전부 대조: fresh 1,540개, training 5개, DEV v1 65개, DEV v2 81개 모두 byte-identical.
- 원본 산출물도 삭제/수정하지 않았다. attempt marker도 커밋해 이 preregistration의 재사용을 막는다.
- 실행 프로세스 종료 확인. **64회 완료 후 명시적 중단. 다음 단계 미착수.**
- 실행 종료 시 확인한 계정 사용률 37%로, 사용자 60% 중단 한도에 도달하지 않았다.

원본 결과: `D:/ATANOR-experiments/2026-09-13/shared-world-fresh-v1/report.json`.

### SHA-256

| 항목 | SHA-256 |
|---|---|
| preregistration | `33045a1da2037103d8ad2ff3b1acfc1b7c24dcf899460fb5a98e65c666c32e9f` |
| 원본 report.json | `725d3fcc9edfab050078f6bbd373996458d9b16bfd8a38e22804b4407fac73cd` |
| 원본 rows.jsonl | `0673b3fb4ea921bb4111552cd69ceae3baf39f5874be0ebd09de589b5ef7c6d0` |
| 원본 dataset.json | `d324158fc7534ed12e2817fa9292eff8398d6dcc4186e20403a3c0bd6f209211` |
| evidence/fresh-v1.zip | `3a955d1184ed236f87def00c0c15d75c2bf187c64a62354f737bc7d76f01919c` |
| evidence/training-v1.zip | `f110590291ace952dc45845fe23cc797aa3d4a21555e79037fae453f1c47dc33` |
| evidence/dev-v1.zip | `f53ae1c46427406a9da111d8a4815d5f023a1fd21edb147d8ed4c25631bf13cc` |
| evidence/dev-v2.zip | `8a60958e190c742f33e99aa7213c80aec714e54d836009f4f7081c24bc58fd0a` |
| evidence/shared-world-mechanism-v2.xml | `6919a7513edc0744100fdc7d6eeb8fb5c99a0c068b02a0fc25013fd4812d9ccf` |
| evidence/d3-revisit-regression-before-v1.xml | `3a6fc8e8e908c98f2890cc01f6956faecdc31a2531bfe2f8187ca06a32da02d9` |
| evidence/d3-revisit-regression-after-v2.xml | `7ae612d4d2ceb5a7dea9b0fec7ab0c8a30a6c137b36cdeadb1fcea1c1725ec9e` |
