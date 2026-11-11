"""Runner for one course seed on one of the island's five places (the learner is ATANOR_LEARNER's; ORACLE is inside
isle_eval). NONE only: an empty mind taught in the place (25 sessions, the tool change from session 10), then what the
learner does between a course and its evaluation (learners.after_course: practice for next_explore), then the
evaluator on world seed 100 + seed (practice world seed + 300 inside after_course).
Each place has its own module (reef_run ... crag_run): python -m atanor_os.eval.<place>_run <seed> <out_dir>
"""
import json
import shutil
from pathlib import Path

from .isle_eval import evaluate
from ..agent.learners import after_course, name as learner_name
from ..teach.teacher_policy import Teacher

SESSIONS = 25
CHANGE = 10


def short(r):
    return {k: r[k] for k in ('summary', 'held_why', 'harm', 'commands', 'wrong', 'irreversible_without_grant')} | {
        k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'} for k in ('unseen_change', 'time', 'oracle', 'nogrant')} | {
        'synonyms': r['synonyms']['summary']}


def run(body, seed, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    who = learner_name()
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'{body}-{who}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    out = {'learner': who, 'seed': seed}
    Teacher(base / 'none' / body, seed=seed, drift_from=CHANGE, body=body, mind=base / 'none' / 'mind').run(SESSIONS)
    out['practice_none'] = after_course(base / 'none' / body, base / 'none' / 'mind', body, seed)
    out['none'] = short(evaluate(body, base / 'none' / body, 100 + seed, out_dir / f'{body}-{who}-none-s{seed}.json'))
    shutil.copy(base / 'none' / body / 'log.jsonl', out_dir / f'{body}-{who}-none-s{seed}-course-log.jsonl')
    (out_dir / f'{body}-{who}-summary-s{seed}.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out
