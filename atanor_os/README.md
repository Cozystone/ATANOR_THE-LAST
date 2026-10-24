# ATANOR OS — 최소 수직 구현 (P1 → P4)

**보고서: [P1_REPORT.md](P1_REPORT.md)** (v1·v2 사전등록 결과, HP 복제, 독립 검토) · **[P2_P4_REPORT.md](P2_P4_REPORT.md)** (획득 정책 H1/H4, 스킬 H2, 화면 몸 H3, 감독 루프 P4) · **[P6_REPORT.md](P6_REPORT.md)** (자율 과제 수행: 공개 웹 읽기 전용, 교사는 훈련에서만 — 판정 NO_GAIN) · **[H6_DEV_REPORT.md](H6_DEV_REPORT.md)** (읽기 능력 단계별 개발 실험 — WEAK, 가정 재검토) · **[P7_REPORT.md](P7_REPORT.md)** (언어 모델을 읽기 도구로 둔 결정층 평가 — 도구 포함·모델 끔 모두 NO_GAIN) · **[P8_REPORT.md](P8_REPORT.md)** (경험에서 만든 내부 개념, 재시작 뒤 재사용 — INCONCLUSIVE) · **[P8B_REPORT.md](P8B_REPORT.md)** (근거를 보존하는 수정, 안정·드리프트 — PARTIAL: 화면 PASS, 파일 FAIL) · **[P9_REPORT.md](P9_REPORT.md)** (내부 표현과 영어 명령문의 연결, 교사·Qwen 끔 — LINKED(경계값), 개념 기여 없음, 지연 평가 대기) · [HISTORY_REWRITE.md](HISTORY_REWRITE.md). 결과 원본은 `results/`, 모든 결정과 이유는 `DECISIONS.md`.

상태 표기: **구현됨** = 코드가 있고 실행된다 · **시험됨** = 명세 테스트 또는 실측 결과가 있다 · **가설** = 아직 증거 없음 · **막힘** = 승인/자원 필요.
이 디렉터리의 어떤 것도 AGI·의식·일반 지능의 증거가 아니다.

## 무엇인가
헌장(2026-10-24 v0.1) §9. 실제 작업 공간(파일시스템, 화면 패널 명세)에서 다음 경로를 끝까지 연결하고, 같은 학습기가 **몸(body)을 바꿔도** 그대로 배우는지, 죽어도 되는 운영자로 돌 수 있는지를 본다.

    관측 → 실제 실행 → 기록 → 행동 모델 갱신 → 새 과제 계획 → 실제 결과로 평가

비교군은 같은 명령·같은 예산·같은 경험으로 돌린다 (EXPERIMENT_PROTOCOL.md).
- **A 고정 지식**: 설명서(효과만, 전제조건 없음)로만 계획. 갱신 없음.
- **B 경험 검색**: A + 같은 상황 서명의 과거 경험을 그대로 재사용. 규칙 유도 없음.
- **C 규칙 학습**: B + 성공/실패 대조로 도구별 전제조건·효과 규칙을 유도(학습기 v4: 유형 그룹 선택지, 임의 속성 복사 효과).
- **D 의결(MAGI형)**: 같은 경험을 3등분해 가진 C 3개의 다수결(v2에서 이득 없음으로 답이 나와 이후 생략).
- **CT / E**: C + 스스로 완수한 훈련 에피소드 20개의 경험 / 거기서 뽑은 매크로(스킬)까지. E−CT가 매크로의 기여.
- **ORACLE**: 평가기의 진실 의미론. 진단용(과제 타당성·planner), 학습 성과와 비교 대상이 아님.

기존 Whole Mind(`packages/`, `scripts/`)와 분리. 이 패키지는 그 코드를 import하지 않는다(`tests/test_leakage.py`).

## 실행 (저장소 루트에서, Python ≥3.9, 외부 의존성 없음)
```
python -m pytest atanor_os/tests -q
python -m atanor_os semantics --k 20 --seed 7 [--body view]          # 진실 모델 vs 실제 몸, 도구×결과 셀당 20회
python -m atanor_os explore  --seed 1 --steps 300 --policy contrast --out atanor_os/runs/x1
python -m atanor_os evaluate --split dev --seed 1 --experiences atanor_os/runs/x1/experiences.jsonl --conditions A,B,C --tasks 20 --out atanor_os/runs/e1
python -m atanor_os pilot    --split test --seeds 1,2,3,4,5 --tasks 20 --steps 300 --policy contrast --out atanor_os/results/<name>
python -m atanor_os pilot    --body view --steps 600 --policy contrast-kind --conditions A,B,C --split test --out atanor_os/results/<name>
python -m atanor_os compare  --a <run> --b <run> --cond C [--cond-b CT --metric plan_predicted]
python -m atanor_os supervise --root atanor_os/runs/sup --experiences <jsonl> --episodes 200      # P4 장기 운영자
python -m atanor_os crash     --root atanor_os/runs/crash --experiences <jsonl> --episodes 40      # P4 kill/재시작 시험
```
`pilot`은 seed마다 탐색 → 조건별 평가 → ORACLE(진단) 순으로 돌고 `metrics.json`, `REPORT.md`, `records.jsonl`, 경험 로그, 조건별 `agreement_*.json`(고정 모델 vs 진실 의미론)을 남긴다.
판정은 몸별 프로토콜(`protocol.json`=fs, `protocol_view.json`=view, `--protocol`로 지정)이 **실행 전에** 동결돼 있을 때만 VALID_*. INVALID 조건: 시작·종료 시 소스 sha256 불일치, **프로토콜의 설계 파라미터(split·steps·policy·tasks·seeds·body·budget·train_tasks·conditions_list)와 실행 인자 불일치**, 유효성 게이트 실패(마커 `-m "not learning and not timing and not <다른 몸>"`: 학습 성능 단정·시간 의존 프로세스 시험·다른 몸의 시험은 제외), 의미론 검사 실패, ORACLE < 1. 사전등록 실행은 `runs/_scripts/snap.py`로 만든 스냅샷에서 돌린다.

## 구성 (책임 경계이지 기관 목록이 아님)
| 경로 | 책임 | 상태 |
|---|---|---|
| `world/fs_world.py` | 실제 파일시스템 관측·도구 실행·capability 차단·경로 격리 | 시험됨 |
| `world/view_world.py` | 두 번째 몸: 화면 패널 명세(`view.json`)와 UI 도구(open/close/filter/sort/group/compare) | 시험됨 |
| `core/types.py`, `core/journal.py` | 데이터 계약, durable 행동 기록(의도→실행→검증, 상태 스냅샷, 에피소드) | 시험됨 |
| `agent/bootstrap.py` | 사람이 준 사전지식(도구 서명·효과 설명, 몸별) | 구현됨 |
| `agent/lift.py` | 관측을 역할 변수로 들어올리는 표현·효과 가설 언어(제공된 것) | 시험됨 |
| `agent/models.py`, `agent/rule_learner.py` | A/B/C/D 모델, 규칙 유도(v4) | 시험됨 |
| `agent/skills.py` | 자기 완수 흔적에서 매크로 추출(E) | 시험됨(H2 결과는 보고서) |
| `agent/planner.py`, `agent/loop.py` | 예산 제한 탐색, 의사결정·실행·재관측 루프(재개 가능) | 시험됨 |
| `agent/supervisor.py` | P4 장기 운영자: 의도↔현실 대조, 실제 상태에서 재개, 모델 재구축 | 시험됨(로컬·HP) |
| `ui/renderer.py` | 신뢰된 tkinter 렌더러: 명세 검증 → 순수 레이아웃 → 그리기, 버튼은 허용 행동만 | 시험됨 |
| `lang/korean.py` | 제한된 한국어 지시 → 목표 리터럴(지원 형식 공개, 미지원 보고, 지시어는 질문) | 시험됨 |
| `world/web_world.py` | P6 웹 몸: 읽기 전용 GET, robots 준수, 속도 제한, 관측 보관·재생 | 시험됨 |
| `agent/reader.py`, `agent/autonomy.py` | P6 영어 목표 해석(어휘 학습)·명칭 읽기(학습)·일반 결정 절차(찾기·대조·멈춤·리허설) | 시험됨(평가 NO_GAIN) |
| `teach/` | P6 훈련 전용 교사(평가 프로세스에서 import 차단) | 구현됨 |
| `eval/` | 과제 생성(분할·seed), 진실 모델(평가기 전용), 탐색 정책, 판정, 지표, 규칙 일치, 충돌 시험, P6 진실·과제·봉인 평가 | 시험됨 |

## 지금 주장할 수 없는 것
- 자유로운 언어 이해(문법은 사람이 준 것), 실시간 UI 재구성, 자기 코드 수정(P5, 미착수).
- 실제 사용자 자료 — 별도 승인. HP 노트북에는 사용자 범위 Python과 이 패키지의 복사본만 있다(OS·파티션·권한 무변경).
- 과제는 생성된 소형 작업 공간(파일 3–4개, 패널 ≤4)이며 최대 3–6 행동. 깊은 계획·장기 기억·다중 사용자는 시험하지 않았다.
