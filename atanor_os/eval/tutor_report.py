"""Summary of a tutor life (evaluator side): A (no words), B (symbols), C (new combinations), D (English), memory."""
import json
import re
import sys
from collections import Counter
from pathlib import Path


def summary(run_dir):
    rows = [json.loads(l) for l in (Path(run_dir) / 'days.jsonl').read_text(encoding='utf-8').splitlines()]
    les = [r for r in rows if r['event'] == 'lesson' and 'criterion_ok' in r]
    out = {'A_lessons': len(les), 'A_criterion_ok': sum(r['criterion_ok'] for r in les),
           'A_reproduced': sum(bool(r.get('reproduced')) for r in les),
           'A_contrast_per_lesson': round(sum(r.get('help', {}).get('contrast', 0) for r in les) / max(1, len(les)), 2),
           'A_wrong_imitation': sum(1 for r in les if r.get('reproduced') is False)}
    for kind, lang, key in (('B', 'sym', 'B'), ('C', 'sym', 'C'), ('B', 'en', 'D_B'), ('C', 'en', 'D_C')):
        ts = [r for r in rows if r['event'] == 'test' and r.get('kind') == kind and r.get('lang') == lang and r.get('outcome') not in ('infeasible', None)]
        alone = [r for r in ts if not r['user']]
        out[key] = {'n': len(ts), 'first_try': sum(bool(r.get('first_try')) for r in ts), 'success': sum(r['outcome'] == 'success' for r in ts),
                    'wrong': sum(r['outcome'] == 'wrong' for r in ts), 'held': sum(r['outcome'] == 'held' for r in ts),
                    'alone': f"{sum(bool(r.get('first_try')) for r in alone)}/{len(alone)}",
                    'questions': sum(v for r in ts for q, v in r.get('help', {}).items() if q != 'confirm')}
    ret = [r for r in rows if 'retrieval_ok' in r]
    out['retrieval_ok'] = f"{sum(r['retrieval_ok'] for r in ret)}/{len(ret)}"
    drift = [r for r in rows if r['event'] == 'test' and r.get('drift') and r.get('outcome') not in ('infeasible', None)]
    out['after_change_first_try'] = f"{sum(bool(r.get('first_try')) for r in drift)}/{len(drift)}"
    out['redemonstrated'] = sum(bool(r.get('redemonstrated')) for r in rows)
    m = re.search(r'tutor-[a-z]+(\d+)-(board|fs|view)', str(run_dir))
    if m:                                               # revision after the counter-example: commands with the changed tool
        from .tutor_life import body_targets, DRIFT
        seed, body = int(m.group(1)), m.group(2)
        tool = {'board': 'lodge', 'fs': 'copy', 'view': 'sort'}[body]
        acts = body_targets(body, seed)[1]
        hit = [r for r in drift if acts[r['act']]['tool'] == tool]
        first = next((i for i, r in enumerate(hit) if r.get('first_try')), None)
        out['changed_tool_commands'] = len(hit)
        out['commands_until_unaided'] = first if first is not None else f'none in {len(hit)}'
    taught_day = {}                                     # reuse after time: days since the selection was last taught
    by_age = {'0-2': [0, 0], '3-6': [0, 0], '7+': [0, 0]}
    for r in rows:
        if r['event'] == 'lesson' and 'sel' in r:
            taught_day[r['sel']] = r['day']
        if r['event'] == 'test' and r.get('lang') == 'sym' and r.get('outcome') not in ('infeasible', None) and r.get('sel') in taught_day:
            age = r['day'] - taught_day[r['sel']]
            k = '0-2' if age <= 2 else ('3-6' if age <= 6 else '7+')
            by_age[k][0] += bool(r.get('first_try'))
            by_age[k][1] += 1
            if r.get('retaught'):
                taught_day[r['sel']] = r['day']
    out['reuse_by_age'] = {k: f'{a}/{n}' for k, (a, n) in by_age.items()}
    wrong_used = [r for r in rows if r.get('outcome') == 'wrong']
    out['wrong_claim_use'] = f"{len(wrong_used)}/{sum(1 for r in rows if r.get('used_claims'))}"
    out['wrong_total'] = sum(r.get('outcome') == 'wrong' for r in rows)
    out['questions_total'] = sum(v for r in rows for q, v in r.get('help', {}).items() if q != 'confirm')
    return out


if __name__ == '__main__':
    for d in sys.argv[1:]:
        print(Path(d).name, json.dumps(summary(d)))
