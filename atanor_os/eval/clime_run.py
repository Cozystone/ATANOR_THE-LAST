"""NEW_BODY_DESIGN.md runner for one course seed (the learner is the generation-1 closeout core unless ATANOR_LEARNER
says otherwise; ORACLE is inside clime_eval).
  NONE   an empty mind taught on the climate bays (25 sessions)
  GEN1   one mind: the 75-day three-body course, the desk (25 sessions), then the climate bays (25 sessions)
Usage: python -m atanor_os.eval.clime_run <seed> <out_dir> [sealed:<clime_sealed.json>]
"""
import json
import shutil
import sys
from pathlib import Path

from .clime_eval import evaluate
from ..agent.learners import name as learner_name
from ..teach.long_course import CHANGE_FROM, run as long_course
from ..teach.teacher_policy import Teacher

SESSIONS = 25
CHANGE = 10


def short(r):
    return {k: r[k] for k in ('summary', 'held_why', 'harm', 'commands', 'wrong')} | {
        k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'} for k in ('unseen_change', 'time', 'oracle')} | {
        'synonyms': r['synonyms']['summary']}


def run(seed, out_dir, sealed=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    who = learner_name()
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'clime-{who}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    out = {'learner': who, 'seed': seed}
    Teacher(base / 'none' / 'clime', seed=seed, drift_from=CHANGE, body='clime', mind=base / 'none' / 'mind').run(SESSIONS)
    out['none'] = short(evaluate(base / 'none' / 'clime', 100 + seed, out_dir / f'clime-{who}-none-s{seed}.json', sealed))
    shutil.copy(base / 'none' / 'clime' / 'log.jsonl', out_dir / f'clime-{who}-none-s{seed}-course-log.jsonl')
    long_course(base / 'gen1', seed, per_body=25, shared=True, change_from=CHANGE_FROM)
    Teacher(base / 'gen1' / 'desk', seed=seed, drift_from=10, body='desk', mind=base / 'gen1' / 'mind').run(25)
    Teacher(base / 'gen1' / 'clime', seed=seed, drift_from=CHANGE, body='clime', mind=base / 'gen1' / 'mind').run(SESSIONS)
    out['gen1'] = short(evaluate(base / 'gen1' / 'clime', 100 + seed, out_dir / f'clime-{who}-gen1-s{seed}.json', sealed))
    shutil.copy(base / 'gen1' / 'clime' / 'log.jsonl', out_dir / f'clime-{who}-gen1-s{seed}-course-log.jsonl')
    (out_dir / f'clime-{who}-summary-s{seed}.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[3:] if a.startswith('sealed:')), None)
    print(json.dumps(run(int(sys.argv[1]), sys.argv[2], sealed), indent=1))
