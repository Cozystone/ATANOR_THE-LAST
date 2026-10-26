"""Report on real teaching sessions (evaluator side; reads only the sandbox log and memory).

What it measures:
  - lessons: how often the criterion and the action were confirmed, and how much help (pointing, contrast answers,
    demonstrations) each took;
  - reuse: commands that use a name taught in an earlier session, by days since teaching, split by alone / with the
    person, and whether they worked on cards that did not exist when the name was taught;
  - failures by class (perception, grounding, structure, tool model, planning, safety hold, evaluator/env). A class says
    where to look; nothing here changes the learner;
  - where the memory came from: claims by source (a real person vs the program tutor).
Usage: python -m atanor_os.ui.session_report <sandbox_dir> [--md out.md]
"""
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

from ..agent.memory import Memory


def bucket(days):
    return 'same day' if days == 0 else ('1-2 days' if days <= 2 else ('3-6 days' if days <= 6 else '7+ days'))


def summary(root):
    root = Path(root)
    rows = [json.loads(l) for l in (root / 'log.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    sessions = [r for r in rows if r['event'] == 'session']
    lessons = [r for r in rows if r['event'] == 'lesson']
    names = [r for r in rows if r['event'] == 'name']
    cmds = [r for r in rows if r['event'] == 'command']
    out = {'sessions': len(sessions), 'dates': sorted({r['at'][:10] for r in sessions}),
           'lessons': len(lessons), 'lessons_confirmed': sum(bool(r.get('confirmed')) for r in lessons),
           'help_per_lesson': {k: round(sum(r.get('help', {}).get(k, 0) for r in lessons) / max(1, len(lessons)), 2)
                               for k in ('point', 'contrast', 'demo')},
           'phrases_named': len(names), 'phrases_on_known_concept': sum(bool(r.get('known_concept')) for r in names),
           'commands': len(cmds), 'outcomes': dict(Counter(r['outcome'] for r in cmds)),
           'failure_classes': dict(Counter(r['failure_class'] for r in rows if r.get('failure_class')))}
    reuse = {}
    for r in cmds:
        tw = r.get('taught_words') or {}
        earlier = [t for t in tw.values() if t['session'] < r['session']]
        if not earlier:
            continue
        days = (datetime.date.fromisoformat(r['at'][:10]) - min(datetime.date.fromisoformat(t['date']) for t in earlier)).days
        key = f"{bucket(days)} / {'alone' if r['alone'] else 'with person'}"
        b = reuse.setdefault(key, {'n': 0, 'success': 0, 'wrong': 0, 'held': 0, 'on_new_cards': 0})
        b['n'] += 1
        b[r['outcome'] if r['outcome'] in ('success', 'wrong', 'held') else 'held'] += 1
        b['on_new_cards'] += bool(r['outcome'] == 'success' and r.get('acted_new_cards'))
    out['reuse_after_sessions'] = reuse
    try:
        mem = Memory(root / 'mind', events_readable=True)
        out['claims_by_source'] = dict(Counter((c.get('scope') or {}).get('source') for c in mem.claims.claims()))
        out['events_by_source'] = dict(Counter(e.get('source') for e in mem.events.all()))
    except (OSError, ValueError):
        pass
    return out


def markdown(s):
    lines = ['# 실제 사용자 교수 세션 요약', '',
             f"- 세션 {s['sessions']}회 ({', '.join(s['dates'])}), 수업 {s['lessons']}회(확인 {s['lessons_confirmed']}), 수업당 도움 {s['help_per_lesson']}",
             f"- 이름 붙이기 {s['phrases_named']}회 (이미 배운 개념에 {s['phrases_on_known_concept']})",
             f"- 명령 {s['commands']}회: {s['outcomes']}",
             f"- 실패 분류: {s['failure_classes'] or '없음'}", '',
             '| 가르친 뒤 · 누구와 | 명령 | 성공 | 틀림 | 보류 | 새 카드에서 성공 |', '|---|---|---|---|---|---|']
    for k, b in sorted(s['reuse_after_sessions'].items()):
        lines.append(f"| {k} | {b['n']} | {b['success']} | {b['wrong']} | {b['held']} | {b['on_new_cards']} |")
    lines += ['', f"- 기억의 출처(주장): {s.get('claims_by_source')} · 사건: {s.get('events_by_source')}"]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    s = summary(sys.argv[1])
    print(json.dumps(s, ensure_ascii=False, indent=1))
    if '--md' in sys.argv:
        Path(sys.argv[sys.argv.index('--md') + 1]).write_text(markdown(s), encoding='utf-8')
