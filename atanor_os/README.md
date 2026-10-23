# ATANOR OS — P1 최소 수직 구현

**첫 보고: [P1_REPORT.md](P1_REPORT.md)** (v1·v2 사전등록 결과, HP 복제, 독립 검토, 실패 원인, 다음 가설). 결과 원본은 `results/`.

상태 표기: **구현됨** = 코드가 있고 실행된다 · **시험됨** = 명세 테스트 또는 실측 결과가 있다 · **가설** = 아직 증거 없음 · **막힘** = 승인/자원 필요.
이 디렉터리의 어떤 것도 AGI·의식·일반 지능의 증거가 아니다.

## 무엇인가
헌장(2026-10-24 v0.1) §9 P1. 생성된 작은 파일 작업 공간에서 다음 경로를 끝까지 연결한다.

    관측 → 실제 실행 → 기록 → 행동 모델 갱신 → 새 과제 계획 → 실제 결과로 평가

네 비교군을 같은 명령·같은 예산·같은 경험으로 돌린다 (EXPERIMENT_PROTOCOL.md).
- **A 고정 지식**: 설명서(효과만, 전제조건 없음)로만 계획. 갱신 없음.
- **B 경험 검색**: A + 같은 상황 서명의 과거 경험을 그대로 재사용. 규칙 유도 없음.
- **C 규칙 학습**: B + 성공/실패 대조로 도구별 전제조건·효과 규칙을 유도.
- **D 의결(MAGI형)**: 같은 경험을 3등분해 가진 C 3개의 다수결. 2차 비교군(의결이 C보다 나은가).

기존 Whole Mind(`packages/`, `scripts/`)와 분리. 이 패키지는 그 코드를 import하지 않는다(`tests/test_leakage.py`).

## 실행 (저장소 루트에서, Python ≥3.9, 외부 의존성 없음)
```
python -m pytest atanor_os/tests -q
python -m atanor_os semantics --k 20 --seed 7        # 평가기 진실 모델 vs 실제 파일시스템, 도구×결과 셀당 20회
python -m atanor_os explore  --seed 1 --steps 200 --out atanor_os/runs/x1
python -m atanor_os evaluate --split dev --seed 1 --experiences atanor_os/runs/x1/experiences.jsonl --conditions A,B,C,D --tasks 20 --out atanor_os/runs/e1
python -m atanor_os pilot    --split test --seeds 1,2,3,4,5 --tasks 20 --steps 200 --out atanor_os/results/<name>
```
`pilot`은 seed마다 탐색 → A/B/C 평가 → ORACLE(진단) 순으로 돌고 `metrics.json`, `REPORT.md`, `records.jsonl`, 경험 로그를 남긴다.
`protocol.json`이 동결되어 있지 않으면 판정은 `EXPLORATORY`로만 기록된다.

## 구성 (책임 경계이지 기관 목록이 아님)
| 경로 | 책임 | 상태 |
|---|---|---|
| `world/fs_world.py` | 실제 파일시스템 관측·도구 실행·capability 차단·경로 격리 | 구현됨 |
| `core/types.py`, `core/journal.py` | 데이터 계약, durable 행동 기록(의도→실행→검증) | 구현됨 |
| `agent/bootstrap.py` | 사람이 준 사전지식(도구 서명·효과 설명) | 구현됨 |
| `agent/lift.py` | 관측을 역할 변수로 들어올리는 표현(제공된 것) | 구현됨 |
| `agent/models.py`, `agent/rule_learner.py` | A/B/C 모델, 규칙 유도 | 구현됨 |
| `agent/planner.py`, `agent/loop.py` | 예산 제한 탐색, 의사결정·실행·재관측 루프 | 구현됨 |
| `eval/` | 과제 생성(분할·seed), 진실 모델(평가기 전용), 탐색 정책, 판정, 지표 | 구현됨 |

## 지금 주장할 수 없는 것
- 자유로운 언어 이해, UI, 자기 코드 수정 — P3 이후.
- 실제 사용자 자료 — 별도 승인.
- HP 노트북 설치·운용 — P4, 별도 승인.
