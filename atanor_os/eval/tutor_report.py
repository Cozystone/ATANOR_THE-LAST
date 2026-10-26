"""Summary of a tutor life (evaluator side): A (no words), B (symbols), C (new combinations), D (English), memory."""
import json
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
    out['wrong_total'] = sum(r.get('outcome') == 'wrong' for r in rows)
    out['questions_total'] = sum(v for r in rows for q, v in r.get('help', {}).items() if q != 'confirm')
    return out


if __name__ == '__main__':
    for d in sys.argv[1:]:
        print(Path(d).name, json.dumps(summary(d)))
