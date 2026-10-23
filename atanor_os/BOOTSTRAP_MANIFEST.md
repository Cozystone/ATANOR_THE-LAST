# BOOTSTRAP_MANIFEST — 학습기에 사람이 미리 넣어준 것 (P1)

"경험으로 발견했다"고 보고할 수 없는 항목의 전체 목록. 코드 위치를 함께 적는다.

## 1. 표현 (제공)
- 객체 ID = 작업 공간 상대 경로. 관측 속성: `kind ∈ {absent,file,dir}`, `ext`(이름 기반 확장자, 없으면 `-`), `hash`(내용 sha256 앞 12자, 파일 아니면 `-`), `parent_kind`(부모 경로의 kind; 루트의 부모는 `dir`). `world/fs_world.py::Workspace.attrs`
- 미관측과 부재는 다르다: 우주(universe) 밖 경로는 관측 안 됨(`None`), 우주 안에 없으면 `absent`.
- 우주 = 존재하는 경로 ∪ 목표가 언급한 경로 ∪ 그 조상. `Workspace.universe`
- 관계 `same_content(x,y)` = 두 hash가 같고 `-`가 아님. 목표·들어올림에 사용.
- 들어올림(lifting): 행동 인자를 역할 변수 `?a0,?a1`로 치환하고, 각 역할의 `kind/ext/parent_kind` 리터럴과 역할 쌍의 `same_content` 리터럴로 상황 서명을 만든다. **`hash` 값 자체는 서명에 넣지 않는다**(내용별 고유값이라 검색 비교군 B가 인위적으로 약해짐; 동등 관계만 사용). `agent/lift.py::lifted_pre`
- 구조 규칙: 효과 적용 후 `parent_kind(x) := kind(parent(x))`로 재계산. (도구 의미가 아니라 관측 구조.) `agent/lift.py::apply_effects`
- 효과 표현: `(역할, 속성, const v | copy 역할j | unknown)`. `hash`의 `copy`는 사후 값이 다른 역할의 사전 값과 같을 때만 인식. `agent/lift.py::lifted_effects`

## 2. 도구 (제공: 서명과 효과 설명만. 전제조건·실패 조건은 제공하지 않음)
`agent/bootstrap.py::DOCS`

| 도구 | 인자 | 설명서에 적힌 효과 | 설명서에 **없는** 것 (학습 대상) |
|---|---|---|---|
| mkdir(?a0) | 1 | kind(?a0)=dir | 이미 있으면 실패, 부모가 dir 아니면 실패 |
| copy(?a0,?a1) | 2 | kind(?a1)=file, hash(?a1)=hash(?a0) | ?a0이 file이어야, ?a1이 absent여야, ?a1의 부모가 dir이어야 |
| move(?a0,?a1) | 2 | kind(?a0)=absent, hash(?a0)=-, kind(?a1)=file, hash(?a1)=hash(?a0) | **파일만** 이동, 덮어쓰기 불가, 부모 dir 필요 |
| delete(?a0) | 1 | kind(?a0)=absent, hash=- ; capability `destroy` 필요 | 파일만 삭제 |
| convert(?a0,?a1) | 2 | kind(?a1)=file | ?a0 ext=txt, ?a1 ext=md, ?a1 absent, 부모 dir; 결과 hash는 원본과 다름 |

설명은 참이지만 불완전하다 (헌장 §8 평가조건 1: 정상 설명). 거짓 설명은 P1 범위 밖.

## 3. 목표 구조 (제공)
`must`(끝에 성립), `keep`(끝에 성립 + 도중에 위반 금지), `capabilities`, `budget`, `universe`. `core/types.py::Goal`

## 4. 의사결정 (제공, 모든 조건 동일)
- 예산 제한 최선우선 탐색. f = g + h, h = 미충족 must 리터럴 수, 설명서만으로 예측한 단계는 g에 +0.5. `keep` 위반 상태와 예측 실패 상태는 가지치기. capability 없는 도구는 계획에 넣지 않음(따라서 "차단된 제안"은 P1에서 구조적으로 0). 구속 예산은 **예측 호출 수**(결정적), 시간은 안전장치. 정지 이유(found/exhausted/predictions/nodes/seconds)를 기록. `agent/planner.py`
- 후퇴 지평: 계획의 첫 행동만 실행 → 재관측 → 재계획. 계획 없음 = 보류(abstain). 같은 상태에서 실패한 행동은 그 상태에서 다시 고르지 않는다(무조건 재시도 금지, 헌장 §4 실행 관리자). 이것은 에피소드 안의 기억이지 모델 갱신이 아니다. `agent/loop.py`
- 정보 획득 정책: P1에는 없음(문서 조회·질문·시험 선택 없음). 학습 성과는 행동 모델에만 귀속.

## 5. 경험 획득 정책 (제공, 평가 하네스 소유)
- 매 단계 도구를 균등 선택한 뒤, 아직 시도하지 않은 상황 서명의 행동을 우선(그 안에서 균등), 없으면 그 도구의 행동 중 균등. train 분포 작업 공간, seed 고정, 40행동마다 새 공간, `destroy` 허용. 조건과 무관하게 **동일 로그**를 B·C·D에 제공. 목표·정답 경로 없음. `eval/explore.py`

## 6. 학습기가 획득해야 하는 것
- 각 도구의 전제조건(위 표의 빈칸), 설명서에 없는 효과의 유무, 조건을 새 객체·새 확장자·새 깊이·새 조합에 적용하는 것.

## 7. 제공하지 않은 것
- 정답 계획, 과제 템플릿, 평가 seed, 진실 모델(`eval/oracle.py`는 학습기에서 import 불가).
