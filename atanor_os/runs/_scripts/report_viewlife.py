"""Append the screen-body life results (dev seed and one held-out seed) to LIFE_REPORT.md and DECISIONS.md.
Usage: python atanor_os/runs/_scripts/report_viewlife.py <dev_run> <dev_seed> <eval_run> <eval_seed> <label> <notes_md>"""
import json
import sys
from collections import Counter
from pathlib import Path

dev_run, dev_seed, eval_run, eval_seed, label, notes = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]


def table(run, conds):
    out = ['| 조건 | 주 | 과제 | 성공 | 틀림 | 보류 | 실행 불가 | 도움 | 가리킴 |', '|---|---|---|---|---|---|---|---|---|']
    tots = {}
    for c in conds:
        p = Path(run) / c / 'days.jsonl'
        if not p.exists():
            continue
        rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()]
        weeks = {}
        for r in rows:
            w = weeks.setdefault((r['day'] - 1) // 7 + 1, Counter())
            w['n'] += 1
            w[r['outcome']] += 1
            w['help'] += r['help_score']
            w['point'] += r['help'].get('point', 0)
        for k, v in sorted(weeks.items()):
            out.append(f"| {c if k == 1 else ''} | {k} | {v['n']} | {v['success']} | {v['wrong']} | {v['held']} | {v['infeasible']} | {v['help']} | {v['point']} |")
        feas = [r for r in rows if r['outcome'] != 'infeasible']
        alone = [r for r in feas if not r['user']]
        user = [r for r in feas if r['user']]
        tots[c] = {'n': len(feas), 'success': sum(r['success'] for r in feas), 'wrong': sum(r['outcome'] == 'wrong' for r in feas),
                   'help': sum(r['help_score'] for r in feas), 'user': f"{sum(r['success'] for r in user)}/{len(user)}",
                   'alone': f"{sum(r['success'] for r in alone)}/{len(alone)}"}
    out.append('')
    out.append('| 조건 | 성공 | 틀린 행동 | 총 도움 | 사람 있는 날 | 사람 없는 날 |')
    out.append('|---|---|---|---|---|---|')
    for c, t in tots.items():
        out.append(f"| {c} | {t['success']}/{t['n']} | {t['wrong']} | {t['help']} | {t['user']} | {t['alone']} |")
    return '\n'.join(out), tots


dev_tbl, dev_tot = table(dev_run, ['LIFE', 'FRESH', 'CASE'])
eval_tbl, eval_tot = table(eval_run, ['LIFE', 'FRESH', 'CASE'])
section = f"""
## 두 번째 몸: 화면 — 같은 코어, {label} (2026-10-25)
화면 몸(패널 p1·p2·p3와 값 객체 ext:csv·key:size·grp:ext; 도구 filter·sort·group·open·close)에 **같은 `agent/life.py`를 그대로** 붙였다. 몸은 자기 이름·종류 서명·이름으로 쓸 수 있는 값·실험실 사본·상태 재구성·권한만 제공한다. 코어에 panel·filter·file·dir·hash·ext 같은 몸 단어가 없음을 테스트가 막는다. 도구별 규칙을 사람이 넣지 않았다: 어느 도구가 무엇을 바꾸는지, 두 번째 대상을 어떻게 부르는지("csv"라는 값으로)는 시범과 경험에서 배운다.

매일 아침 화면은 표준 배치(p1·p2 열림, 필터 없음)로 다시 시작하고, 사람이 2–3개 명령을 준다(동의어·정중어 섞인 영어). 4일마다 물을 사람이 없다. ATANOR가 앞 과제를 보류해 다음 과제가 불가능해지면 "실행 불가"로 건너뛴다.

### 개발 시드 {dev_seed} (반복 수정 뒤; 성과로 주장하지 않음)
{dev_tbl}

### 평가 시드 {eval_seed} (이 코드의 첫 실행)
{eval_tbl}

{Path(notes).read_text(encoding='utf-8')}
"""
p = Path('atanor_os/LIFE_REPORT.md')
p.write_text(p.read_text(encoding='utf-8').rstrip('\n') + '\n' + section, encoding='utf-8')
lt, ft, ct = eval_tot['LIFE'], eval_tot.get('FRESH', {}), eval_tot.get('CASE', {})
d = Path('atanor_os/DECISIONS.md')
s = d.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in s else '\n'
entry = (f"- 2026-10-25 · **두 번째 몸(화면) {label}: 같은 코어, 평가 시드 {eval_seed} 첫 실행** (`LIFE_REPORT.md`). LIFE 성공 {lt['success']}/{lt['n']}, 틀린 행동 {lt['wrong']}, 총 도움 {lt['help']}, "
         f"사람 있는 날 {lt['user']}, 없는 날 {lt['alone']}; FRESH {ft.get('success')}/{ft.get('n')}·도움 {ft.get('help')}·없는 날 {ft.get('alone')}; CASE {ct.get('success')}/{ct.get('n')}·도움 {ct.get('help')}. "
         f"개발 시드 {dev_seed}: LIFE {dev_tot['LIFE']['success']}/{dev_tot['LIFE']['n']}, 틀림 {dev_tot['LIFE']['wrong']}, 도움 {dev_tot['LIFE']['help']}. 코어는 몸 단어 없이 두 몸에서 같은 과정으로 배운다.")
d.write_bytes((s.rstrip('\r\n') + nl + entry + nl).encode('utf-8'))
print('report ok')
