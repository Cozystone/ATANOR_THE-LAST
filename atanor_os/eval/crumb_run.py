"""Runner for one course seed on the seventh body, the bakery oven line (the learner is ATANOR_LEARNER's; ORACLE is inside
crumb_eval). NONE only: an empty mind taught on the oven line (25 sessions, the tool change from session 10), then what
the learner does between a course and its evaluation (learners.after_course: practice for next_explore), then the
evaluator on world seed 100 + seed (practice world seed + 300 inside after_course).
Usage: python -m atanor_os.eval.crumb_run <seed> <out_dir>
"""
import json
import shutil
import sys
from pathlib import Path

from .crumb_eval import evaluate
from ..agent.learners import after_course, name as learner_name
from ..teach.teacher_policy import Teacher

SESSIONS = 25
CHANGE = 10


def short(r):
    return {k: r[k] for k in ('summary', 'held_why', 'harm', 'commands', 'wrong', 'irreversible_without_grant')} | {
        k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'} for k in ('unseen_change', 'time', 'oracle', 'nogrant')} | {
        'synonyms': r['synonyms']['summary']}


def run(seed, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    who = learner_name()
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'crumb-{who}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    out = {'learner': who, 'seed': seed}
    Teacher(base / 'none' / 'crumb', seed=seed, drift_from=CHANGE, body='crumb', mind=base / 'none' / 'mind').run(SESSIONS)
    out['practice_none'] = after_course(base / 'none' / 'crumb', base / 'none' / 'mind', 'crumb', seed)
    out['none'] = short(evaluate(base / 'none' / 'crumb', 100 + seed, out_dir / f'crumb-{who}-none-s{seed}.json'))
    shutil.copy(base / 'none' / 'crumb' / 'log.jsonl', out_dir / f'crumb-{who}-none-s{seed}-course-log.jsonl')
    (out_dir / f'crumb-{who}-summary-s{seed}.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(json.dumps(run(int(sys.argv[1]), sys.argv[2]), indent=1))
