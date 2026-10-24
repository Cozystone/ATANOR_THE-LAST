import json
import pathlib

p = pathlib.Path('atanor_os/protocol_p8b.json')
d = json.loads(p.read_text(encoding='utf-8'))
d['amendments'] = [{
    'version': '1.1',
    'frozen_at': '2026-10-24T23:50:00',
    'before_any_run': True,
    'checked_with': 'R1 built from E1 (a training artefact) and the true models only; no revision on E2/E3 and no test was run',
    'changes': [
        {'what': 'view drift replaced: group_filtered -> compare_replace (compare may replace an existing comparison view; '
                 'a target that is a list panel still fails; effects unchanged)',
         'why': "R1's view group rule is one conjunction (panel, grp) without the filter condition: the 11 training failures "
                '(filtered panel + grp:ext) stay unexplained because a single conjunction cannot express '
                "'filter all OR value none', so no evidence for that condition is stored. Removing a condition ATANOR never "
                'learned would not test revision. R1 holds compare\'s condition "target absent" with 21 stored counter-examples.'},
        {'what': 'view drift tasks: the comparison view cmp currently compares p1; make it compare p3 (filter and sort of p3) '
                 'without ever closing it (kind cmp = compare kept all the way; close not granted)',
         'why': 'needs the changed capability: 20/20 solved by the changed-world truth, 0/20 by the original truth in the original world'},
        {'what': 'fs drift detail: a folder cannot move into itself (the world rejects it explicitly; before, the rename raised an error)',
         'why': 'found when validating the changed-world truth (it predicted success for those cases)'},
        {'what': "changed-tool prediction split. (a) changed situations = actions of the changed tool where the original and the "
                 'changed true rule disagree, >= 20 checks from blocks shaped like the drift tasks (indices 1000-2999, disjoint '
                 'from the 20 evaluation tasks) and test blocks: the registered thresholds >= 0.90 and >= R1_KEEP + 20 pp apply here. '
                 "(b) the changed tool's other situations (20 true successes + 20 true failures): joins 'other-tool prediction >= 0.95'.",
         'why': 'the P8 stratified sampler draws few changed situations, so R1 would score about 0.9 on the changed tool without '
                'any revision and the +20 pp criterion could not be met by anyone. Validation with true models: changed-world truth '
                '1.00 (a) / 1.00 (b), original truth 0.00 (a) / 1.00 (b) in both bodies.'},
        {'what': 're-verification: re-creates the conflicting situation = stored conjunction minus the condition, plus the argument '
                 "types (first raw attribute) the conflicting new success had; runs in a fresh exploration block of the current world "
                 '(stable: original world, drift: changed world), at most 40 blocks per verification; a new success explained by '
                 'another rule of the same tool is not a conflict',
         'why': 'a first version picked any action lacking the condition (e.g. an absent source), which fails in both worlds'},
        {'what': 'details fixed: E3 = explore(seed 31, 600 steps, contrast-kind) per body in the changed world; prediction seeds '
                 '9100 + 10*drift + view, changed-tool seeds 9300 + view (+2 for (b)); R2_P8 drift = P8 revise(R2 stable, E3); '
                 'FULL_RAW/FULL_STRUCT/CASE/FIXED use E1+E2 (stable) and E1+E2+E3 (drift); training-situation exclusion includes E3',
         'why': 'implementation detail not fixed in v1'},
    ],
    'unchanged': 'all PASS thresholds, conditions, budget, measures and the overall verdict rule',
}]
p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')

md = pathlib.Path('atanor_os/P8B_DESIGN.md')
md.write_text(md.read_text(encoding='utf-8') + '''
## 개정 1.1 (2026-10-24 23:50, 실행 전)
R1(E1로 만든 훈련 산물)과 참 모델만으로 점검했다. E2·E3 수정과 시험은 하나도 돌리지 않았다. 판정 기준은 그대로다.

1. **화면 드리프트 교체**: "필터된 목록 묶기 허용" → **"비교 화면이 이미 있어도 compare로 바꿀 수 있음"**(대상이 목록 패널이면 여전히 실패, 효과는 같음).
   - 이유: R1의 화면 `group` 규칙은 (panel, grp) 하나의 연언이고 필터 조건이 없다. 훈련 실패 11건(필터된 패널 + grp:ext)은 "필터 all 또는 값 none"을 연언 하나로 쓸 수 없어 설명되지 않은 채 남고, 그 조건의 근거도 저장되지 않는다. ATANOR가 배운 적 없는 조건을 없애면 수정 능력을 시험하지 못한다.
   - R1은 `compare`의 "대상이 비어 있음" 조건을 반례 근거 21개로 갖고 있다.
2. **화면 드리프트 과제**: 비교 화면 `cmp`가 p1을 비교하는 중이다. 한 번도 닫지 않고(`cmp`가 처음부터 끝까지 비교 화면, 닫기 권한 없음) p3을 비교하게 만든다. 바뀐 세계의 참 모델은 20/20, 원래 세계의 참 모델은 0/20을 푼다.
3. **파일 드리프트 세부**: 폴더를 자기 안으로 옮길 수는 없다. 세계가 명시적으로 거부한다(이전에는 이름 바꾸기 오류로 실패).
4. **바뀐 도구 예측 분리**
   - (a) **바뀐 상황**: 원래 규칙과 바뀐 규칙의 답이 다른 상황, 20회 이상 확인. 등록된 기준(≥ 0.90, ≥ R1 유지 + 20 pp)을 여기에 적용한다.
   - (b) **바뀐 도구의 나머지 상황**: 참 성공 20 + 참 실패 20. "나머지 도구 ≥ 0.95"에 합친다.
   - 이유: P8의 층화 표본은 바뀐 상황을 거의 뽑지 않는다. 그러면 R1이 수정 없이도 약 0.9를 받아 누구도 +20 pp를 넘을 수 없다.
   - 참 모델 점검 결과(두 몸 모두): 바뀐 세계 참 모델 (a) 1.00 / (b) 1.00, 원래 참 모델 (a) 0.00 / (b) 1.00.
5. **재검증 방식**
   - 충돌한 상황을 다시 만든다. 저장된 연언에서 그 조건을 빼고, 충돌한 새 성공의 인자 유형(첫 원시 속성)을 붙인다.
   - 지금 세계의 새 탐색 공간에서 실행한다(안정: 원래 세계, 드리프트: 바뀐 세계). 검증 1회에 최대 40블록.
   - 같은 도구의 다른 규칙이 설명하는 새 성공은 충돌로 보지 않는다.
   - 이유: 첫 판은 그 조건이 없는 아무 행동(예: 원본이 없는 경우)을 골라, 두 세계 모두에서 실패했다.
6. **세부 고정**
   - E3 = 바뀐 세계에서 explore(seed 31, 600단계, contrast-kind).
   - 예측 seed = 9100 + 10×드리프트 + 화면, 바뀐 도구 seed = 9300 + 화면(+2는 (b)).
   - R2_P8의 드리프트 = P8 수정(안정 R2, E3).
   - 전체 기록·사례·사람 개념: 안정은 E1+E2, 드리프트는 E1+E2+E3.
   - 학습 상황 제외에 E3도 포함한다.
''', encoding='utf-8')

dec = pathlib.Path('atanor_os/DECISIONS.md')
dec.write_text(dec.read_text(encoding='utf-8').rstrip('\n') + '''
- 2026-10-24 · **`protocol_p8b.json` 개정 1.1(23:50, 실행 전).** 구현 중 R1(훈련 산물)과 참 모델로만 점검해 발견한 측정 결함 세 가지를 실행 전에 고쳤다. ① 화면 드리프트 "필터된 목록 묶기"는 R1이 그 조건을 배운 적이 없어(연언 하나로 표현 불가, 실패 11건이 설명되지 않은 채 남음) 수정 능력을 시험하지 못한다 → "비교 화면 교체 허용"(R1이 근거 21개로 가진 조건)으로 바꿈. ② 층화 표본은 바뀐 상황을 거의 뽑지 않아 "R1 + 20 pp" 기준이 누구에게도 불가능 → 바뀐 상황 전용 표본(≥ 20회)에 등록 기준을 적용하고, 바뀐 도구의 나머지 상황은 "나머지 ≥ 0.95"에 합침. ③ 폴더를 자기 안으로 옮기는 경우를 참 모델과 세계에서 명시. 재검증은 충돌한 상황(조건을 뺀 연언 + 새 성공의 인자 유형)을 지금 세계의 시험 공간에서 다시 만든다. 판정 기준·조건·예산은 그대로. E2·E3 수정과 시험은 아직 한 번도 돌리지 않았다.
''', encoding='utf-8')
print('ok')
