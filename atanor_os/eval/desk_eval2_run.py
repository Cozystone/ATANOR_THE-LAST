"""DESK_EVAL2_PROTOCOL.md / DESK_EVAL3_PROTOCOL.md runner for one course seed and one learner (ATANOR_LEARNER: 'g35' or
'g36' frozen, else current).
  NONE   an empty mind taught on the desk (25 sessions), evaluated by desk_eval2
  THREE  the 75-day three-body course (one mind), evaluated per body by teacher_eval (the regression check)
  GEN1   (current learner only) the THREE mind then taught on the desk, evaluated by desk_eval2
Every evaluation names its own work folder (the output file's stem), so runs in parallel do not meet.
Usage: python -m atanor_os.eval.desk_eval2_run <seed> <out_dir> [sealed:<desk2_sealed.json>] [en:<english forms json>]
"""
import json
import shutil
import sys
from pathlib import Path

from . import desk_eval2, teacher_eval
from ..agent.learners import name as learner_name
from ..teach.long_course import CHANGE_FROM, run as long_course
from ..teach.teacher_policy import Teacher

DESK_SESSIONS = 25
DESK_CHANGE_FROM = 10


def short(r):
    return {k: r[k] for k in ('summary', 'held_why')} | {'unseen_change': {k: v for k, v in r['unseen_change'].items() if k != 'rows'}}


def run(seed, out_dir, sealed=None, en=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    who = learner_name()
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'r2-{who}-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    out = {'learner': who, 'seed': seed}
    Teacher(base / 'none' / 'desk', seed=seed, drift_from=DESK_CHANGE_FROM, body='desk', mind=base / 'none' / 'mind').run(DESK_SESSIONS)
    r = desk_eval2.evaluate(base / 'none' / 'desk', 100 + seed, out_dir / f'r2-{who}-none-s{seed}.json', sealed)
    out['none'] = {k: v for k, v in r.items() if k not in ('rows',)} | {'synonyms': r['synonyms']['summary']}
    out['none']['modifier'] = {k: v for k, v in r['modifier'].items() if k != 'rows'}
    shutil.copy(base / 'none' / 'desk' / 'log.jsonl', out_dir / f'r2-{who}-none-s{seed}-course-log.jsonl')
    long_course(base / 'gen1', seed, per_body=25, shared=True, change_from=CHANGE_FROM)
    out['three'] = {}
    for b in ('board', 'fs', 'view'):
        r = teacher_eval.evaluate(base / 'gen1' / b, 100 + seed, out_dir / f'r2-{who}-three-{b}-s{seed}.json', en)
        out['three'][b] = short(r)
    if who == 'current':
        Teacher(base / 'gen1' / 'desk', seed=seed, drift_from=DESK_CHANGE_FROM, body='desk', mind=base / 'gen1' / 'mind').run(DESK_SESSIONS)
        r = desk_eval2.evaluate(base / 'gen1' / 'desk', 100 + seed, out_dir / f'r2-{who}-gen1-s{seed}.json', sealed)
        out['gen1'] = {k: v for k, v in r.items() if k not in ('rows',)} | {'synonyms': r['synonyms']['summary']}
        out['gen1']['modifier'] = {k: v for k, v in r['modifier'].items() if k != 'rows'}
        shutil.copy(base / 'gen1' / 'desk' / 'log.jsonl', out_dir / f'r2-{who}-gen1-s{seed}-course-log.jsonl')
    for part in ('none', 'gen1'):
        if part in out:
            out[part] = {k: ({kk: vv for kk, vv in v.items() if kk != 'rows'} if isinstance(v, dict) else v) for k, v in out[part].items()}
    (out_dir / f'r2-{who}-summary-s{seed}.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[3:] if a.startswith('sealed:')), None)
    en = next((a[3:] for a in sys.argv[3:] if a.startswith('en:')), None)
    print(json.dumps(run(int(sys.argv[1]), sys.argv[2], sealed, en), indent=1))
