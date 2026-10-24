# BOOTSTRAP_MANIFEST — 학습기에 사람이 미리 넣어준 것 (P1 → P4)

"경험으로 발견했다"고 보고할 수 없는 항목의 전체 목록. 코드 위치를 함께 적는다. 2026-10-24 독립 검토 2차(`results/magi-review-02.json`)의 지적대로 화면 몸·학습기 v3/v4·P4까지 갱신했다.

## 1. 표현 (제공)
- 객체 ID = 작업 공간 상대 경로(fs) 또는 패널 id·값 객체 id(view: `p1 p2 p3 cmp`, `ext:*`, `key:*`, `grp:*`).
- 관측 속성 — fs: `kind ∈ {absent,file,dir}`, `ext`, `hash`(내용 sha256 앞 12자), `parent_kind`. `world/fs_world.py::Workspace.attrs` · view: `kind ∈ {absent,panel,compare,ext,key,grp}`, `filter`, `sort`, `group`, `value`(값 객체의 이름; 패널은 `-`). `world/view_world.py::ViewWorkspace.attrs_of`
- 미관측과 부재는 다르다: 우주(universe) 밖은 관측 안 됨(`None`), 우주 안에 없으면 `absent`. 우주 = 존재하는 객체 ∪ 목표가 언급한 객체 ∪ 조상(fs) / 패널 4 + 값 객체 11(view).
- 관계 `same_content(x,y)` = 두 hash가 같고 `-`가 아님(fs).
- 들어올림(lifting): 행동 인자를 역할 변수 `?a0,?a1`로 치환하고 **식별 속성을 제외한 모든 관측 속성**(`IDENTITY_ATTRS = ('hash',)`)의 리터럴과 `same_content`로 상황 서명을 만든다. `agent/lift.py::lifted_pre`
- 구조 규칙(fs): 효과 적용 후 `parent_kind(x) := kind(parent(x))` 재계산(`DERIVED_ATTRS`). `agent/lift.py::apply_effects`
- **효과 가설 언어**(학습기 v4): 바뀐 속성마다 후보 = 상수 `const v`(비식별 속성; `hash`는 `-`/`unknown`만) → **다른 역할의 임의 속성 복사** `copy 역할j[, 속성]`(같은 속성 우선) → `unknown`. 학습기는 도구의 모든 성공을 맞히는 첫 후보를 고른다. `agent/lift.py::effect_candidates`, `agent/rule_learner.py::_effects`
- 검색 비교군 B의 효과(`lifted_effects`)는 한 경험에서 읽은 단일 명세: 상수, 또는 사후 값이 다른 역할의 **`hash`·`value`**와 같을 때의 복사(`COPY_SOURCE_ATTRS`). `value`는 view 몸의 속성이다 — 몸 지식이며 여기 공개한다.
- **유형 속성**(학습기 v3, 성공을 유형 그룹으로 나누는 기준): 몸 명세가 선언. fs `('kind',)`, view `('kind','value')`. `agent/models.py::FS_SPEC`, `eval/run.py::BODIES['view']['spec']['type_attrs']`. "값 객체의 이름이 유형을 구분한다"는 것은 사람이 준 것이다.

## 2. 도구 (제공: 서명과 효과 설명만. 전제조건·실패 조건은 제공하지 않음)
### fs — `agent/bootstrap.py::DOCS`
| 도구 | 인자 | 설명서에 적힌 효과 | 설명서에 **없는** 것 (학습 대상) |
|---|---|---|---|
| mkdir(?a0) | 1 | kind(?a0)=dir | 이미 있으면 실패, 부모가 dir 아니면 실패 |
| copy(?a0,?a1) | 2 | kind(?a1)=file, hash(?a1)=hash(?a0) | ?a0 file, ?a1 absent, ?a1의 부모 dir |
| move(?a0,?a1) | 2 | kind(?a0)=absent, hash(?a0)=-, kind(?a1)=file, hash(?a1)=hash(?a0) | 파일만, 덮어쓰기 불가, 부모 dir |
| delete(?a0) | 1 | kind(?a0)=absent, hash=- ; capability `destroy` | 파일만 삭제 |
| convert(?a0,?a1) | 2 | kind(?a1)=file | ?a0 ext=txt, ?a1 ext=md, ?a1 absent, 부모 dir; 결과 hash는 원본과 다름 |

### view — `agent/bootstrap.py::VIEW_DOCS`
| 도구 | 인자 | 설명서에 적힌 효과 | 설명서에 **없는** 것 (학습 대상) |
|---|---|---|---|
| open(?a0) | 1 | kind=panel, filter=all, sort=name, group=none | ?a0이 패널 id이고 absent여야 |
| close(?a0) | 1 | kind=absent, 나머지 `-` ; capability `close_panels` | panel 또는 compare만 |
| filter(?a0,?a1) | 2 | filter(?a0)=value(?a1) | ?a0 panel(compare 불가), ?a1 ext 값 객체 |
| sort(?a0,?a1) | 2 | sort(?a0)=value(?a1) | ?a0 panel 또는 compare, ?a1 key 값 객체 |
| group(?a0,?a1) | 2 | group(?a0)=value(?a1) | ?a0 panel, ?a1 grp; `grp:ext`는 filter=all일 때만 |
| compare(?a0,?a1) | 2 | kind(?a0)=compare | ?a0 absent 패널 id, ?a1 panel; **filter·sort를 ?a1에서 상속**(설명서에 없음) |

설명은 참이지만 불완전하다. 거짓 설명은 범위 밖.

## 3. 목표 구조 (제공)
`must`, `keep`, `capabilities`, `budget`, `universe`. `core/types.py::Goal`. **제한된 한국어 문법**(`lang/korean.py`)은 사람이 쓴 정규식으로 지시를 이 구조로 바꾼다 — 언어 학습이 아니다. 지원 형식은 `SUPPORTED`에 공개하고 미지원은 보고, 지시어는 선택이 없으면 질문.

## 4. 의사결정 (제공, 모든 조건 동일)
- 예산 제한 최선우선 탐색. f = g + h, h = 미충족 must 리터럴 수, 설명서만으로 예측한 단계는 g에 +0.5. keep 위반·예측 실패 가지치기. capability 없는 도구는 계획에 넣지 않음. 구속 예산은 **예측 호출 수**, 시간은 안전장치. 정지 이유 기록. `agent/planner.py`
- 후퇴 지평: 첫 행동만 실행 → 재관측 → 재계획. 같은 상태에서 실패한 행동은 다시 고르지 않음(에피소드 안의 기억). `agent/loop.py`
- **매크로 형식**(E): 연속 도구 쌍 + 인자 관계(`eq`=같은 객체, `child`=바로 아래). 어떤 매크로가 있는지는 자기 완수 흔적에서 추출(지지 ≥2). 계획에서 한 후보 행동, 실행은 원시 행동 하나씩. `agent/skills.py`
- **감독자의 대조 규칙**(P4): 미검증 행동을 실제 재관측과 비교 — 인자 객체가 행동 전과 같으면 `not_done`, 예측 사후와 같으면 `done`, 아니면 `unknown`. 운영 기계, 학습 아님. `agent/supervisor.py`

## 5. 경험 획득 정책 (제공, 평가 하네스 소유, 학습기 미참조)
`eval/explore.py` — `novelty`(도구 균등, 미시도 서명 우선) · `scarce`(도구 가중 1/(1+성공)) · `contrast`(+ 성공 서명과 리터럴 하나 차이인 미시도 서명 우선) · `contrast-role`(차이가 한 인자 역할에 국한) · `contrast-kind`(성공 없는 도구는 인자 kind 튜플 수준의 최소 시도 조합 우선). 조건과 무관하게 **동일 로그**를 모든 조건에 제공. 목표·정답 경로 없음.

## 6. 학습기가 획득해야 하는 것
각 도구의 전제조건(위 표의 빈칸), 설명서에 없는 효과, 조건을 새 객체·확장자·깊이·조합·새 시작 화면에 적용하는 것.

## 7. 제공하지 않은 것
정답 계획, 과제 템플릿, 평가 seed, 진실 모델(`eval/oracle.py`, `eval/view_tasks.py::ViewTrueModel`은 학습기에서 import 불가, `tests/test_leakage.py`).

## 8. 평가기가 쓰는 측정 장치 (학습기와 무관)
`eval/oracle.py::rule_agreement` — 고정 모델을 train 분포의 새 상황에서 진실 의미론과 층화 비교(도구×진실결과 셀 ≥20 + near-miss 셀). 2차 검토 뒤 `unk`(효과 미정)·`strict`(near 셀 포함) 추가. `semantic_check` — 진실 모델 자체의 검증.
