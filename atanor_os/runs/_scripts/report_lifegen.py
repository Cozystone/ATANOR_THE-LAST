"""Append the generated-life results (dev seed and one held-out seed) to LIFE_REPORT.md and DECISIONS.md.
Usage: python atanor_os/runs/_scripts/report_lifegen.py <dev_run> <dev_seed> <eval_run> <eval_seed> <version_label> <causes_md_file> [days=30]"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, '.')
from atanor_os.eval.life_gen import life  # noqa: E402

dev_run, dev_seed, eval_run, eval_seed, label, causes = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6]
DAYS = int(sys.argv[7]) if len(sys.argv) > 7 else 30
TOOL_OF = {'copy_retired': 'copy', 'move_retired': 'move', 'delete_retired': 'delete'}


def curve(run, seed, cond, days=None):
    rows = [json.loads(l) for l in (Path(run) / cond / 'days.jsonl').read_text(encoding='utf-8').splitlines()]
    L = life(seed, days or DAYS)
    phr = {(d['day'], k): t for d in L for k, t in enumerate(d['tasks'])}
    weeks, seen, mastered, adapt, change_day = {}, set(), set(), {}, {}
    for r in rows:
        t = phr[(r['day'], r['task'])]
        w = weeks.setdefault((r['day'] - 1) // 7 + 1, Counter())
        w['n'] += 1
        w[r['outcome']] += 1
        w['help'] += r['help_score']
        w['lab'] += r['counts'].get('lab_actions', 0)
        expr = (' '.join(t['phrases']['verb']), ' '.join(t['phrases']['selector_synonym']) or t['ext'])
        if expr[0] not in {e[0] for e in seen} or expr[1] not in {e[1] for e in seen}:
            w['new'] += 1
            w['new_help'] += r['help_score']
        seen.add(expr)
        if r['tool'] in mastered:
            w['rep'] += 1
            w['rep_free'] += int(r['success'] and r['help_score'] == 0)
        if r['success'] and r['help_score'] == 0:
            mastered.add(r['tool'])
        for ch in r['drift']:
            change_day.setdefault(ch, r['day'])
        for ch in change_day:
            if r['tool'] == TOOL_OF[ch] and ch not in adapt:
                adapt[(ch, 'n')] = adapt.get((ch, 'n'), 0) + 1
                if r['success'] and r['help_score'] == 0:
                    adapt[ch] = adapt[(ch, 'n')]
    alone = [r for r in rows if not r['user']]
    user = [r for r in rows if r['user']]
    tot = {'n': len(rows), 'success': sum(r['success'] for r in rows), 'wrong': sum(r['outcome'] == 'wrong' for r in rows),
           'help': sum(r['help_score'] for r in rows), 'alone': f"{sum(r['success'] for r in alone)}/{len(alone)}",
           'user': f"{sum(r['success'] for r in user)}/{len(user)}",
           'adapt': {k: v for k, v in adapt.items() if isinstance(k, str)}}
    return weeks, tot


def table(run, seed, conds, days=None):
    out = ['| 조건 | 주 | 과제 | 성공 | 틀림 | 보류 | 도움 | 실험 | 새 표현(도움) | 익힌 뒤 무도움 재사용 |', '|---|---|---|---|---|---|---|---|---|---|']
    tots = {}
    for c in conds:
        if not (Path(run) / c / 'days.jsonl').exists():
            continue
        weeks, tot = curve(run, seed, c, days)
        tots[c] = tot
        for w, v in sorted(weeks.items()):
            out.append(f"| {c if w == 1 else ''} | {w} | {v['n']} | {v['success']} | {v['wrong']} | {v['held']} | {v['help']} | {v['lab']} | {v['new']} ({v['new_help']}) | {v['rep_free']}/{v['rep']} |")
    out.append('')
    out.append('| 조건 | 전체 성공 | 틀린 행동 | 총 도움 | 사람 있는 날 | 사람 없는 날 | 세계 변화 뒤 첫 무도움 성공까지 과제 수 |')
    out.append('|---|---|---|---|---|---|---|')
    for c, t in tots.items():
        out.append(f"| {c} | {t['success']}/{t['n']} | {t['wrong']} | {t['help']} | {t['user']} | {t['alone']} | {t['adapt'] or '없음'} |")
    return '\n'.join(out), tots


dev_tbl, dev_tot = table(dev_run, dev_seed, ['LIFE'], 30)
eval_tbl, eval_tot = table(eval_run, eval_seed, ['LIFE', 'FRESH', 'CASE', 'HAND'])
cause_text = Path(causes).read_text(encoding='utf-8')
L = life(eval_seed, DAYS)
section = f"""
## 생성형 장기 생활 — {label} (2026-10-25)
한 집에서 {DAYS}일. 매일 새 파일 10개가 들어오고, 사람이 2–3개 명령을 준다(동의어·문형·정중어가 섞인 영어). 4일마다 하루는 물을 사람이 없다. 8일 이후 두 번 세계가 바뀐다(도구 하나가 작동을 멈추고, 이름과 인자 수만 알려 준 새 도구가 생긴다). 모든 것은 시드로 생성된다. 개발은 시드 {dev_seed}에서만 하고, 코드 판본마다 새 시드에서 **한 번** 평가한다. 평가 시드의 결과는 그 뒤 고치지 않는다.

도움 점수: 설명·가리키기·확인 1, 시범 2, 전체 시범 3. "보류"는 행동하지 않고 멈춘 것, "틀림"은 행동했으나 사람이 원한 결과가 아닌 것.

### 개발 시드 {dev_seed} (최종 코드, 반복 수정의 결과이므로 성과로 주장하지 않음)
{dev_tbl}

### 평가 시드 {eval_seed} (이 코드 판본의 첫 실행; 세계 변화 {[d['drift'] for d in L if d['drift']][-1]})
{eval_tbl}

- HAND는 시나리오 A의 어휘("copy/move/delete … called/named")로 개발자가 쓴 고정 절차다. 생성형 생활의 동의어와 "into X" 문형에서는 거의 모두 "이해 못 함"으로 멈춘다. 고정 절차는 그 어휘 밖에서 쓸모가 없음을 그대로 보여 준다.
- FRESH와 CASE의 사람 없는 날 성공은 0이다. LIFE만 사람 없는 날에 일을 한다.

{cause_text}
"""
p = Path('atanor_os/LIFE_REPORT.md')
p.write_text(p.read_text(encoding='utf-8').rstrip('\n') + '\n' + section, encoding='utf-8')
lt, ft = eval_tot['LIFE'], eval_tot.get('FRESH', {})
d = Path('atanor_os/DECISIONS.md')
s = d.read_bytes().decode('utf-8')
nl = '\r\n' if '\r\n' in s else '\n'
entry = (f"- 2026-10-25 · **생성형 장기 생활 {label}: 평가 시드 {eval_seed} 첫 실행** (`LIFE_REPORT.md`). LIFE 성공 {lt['success']}/{lt['n']}, 틀린 행동 {lt['wrong']}, 총 도움 {lt['help']}, "
         f"사람 없는 날 {lt['alone']}, 세계 변화 뒤 첫 무도움 성공까지 {lt['adapt']}; FRESH 성공 {ft.get('success')}/{ft.get('n')}, 도움 {ft.get('help')}, 사람 없는 날 {ft.get('alone')}; "
         f"CASE 도움 {eval_tot.get('CASE', {}).get('help')}; HAND 성공 {eval_tot.get('HAND', {}).get('success')}/{eval_tot.get('HAND', {}).get('n')}. "
         f"개발 시드 {dev_seed}(최종 코드): LIFE {dev_tot['LIFE']['success']}/{dev_tot['LIFE']['n']}, 틀림 {dev_tot['LIFE']['wrong']}, 도움 {dev_tot['LIFE']['help']}. "
         "평가 시드의 실패 원인은 보고서에 적고, 다음 판본은 새 시드에서 평가한다.")
d.write_bytes((s.rstrip('\r\n') + nl + entry + nl).encode('utf-8'))
print('report ok')
