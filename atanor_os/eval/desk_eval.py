"""DESK_EVAL_PROTOCOL.md runner (evaluator side): for one course seed, the NONE condition (an empty mind taught on the
desk) and the GEN1 condition (a mind that lived the 75-day three-body course, then taught on the desk); ORACLE is
measured inside eval/teacher_eval.py on the same evaluation world.
Usage: python -m atanor_os.eval.desk_eval <seed> <out_dir> [sealed:<path>]
"""
import json
import shutil
import sys
from pathlib import Path

from .teacher_eval import evaluate
from ..teach.long_course import CHANGE_FROM, run as long_course
from ..teach.teacher_policy import Teacher

DESK_SESSIONS = 25
DESK_CHANGE_FROM = 10


def run(seed, out_dir, sealed=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'desk-s{seed}'
    if base.exists():
        shutil.rmtree(base)
    # NONE: an empty mind, desk only
    Teacher(base / 'none' / 'desk', seed=seed, drift_from=DESK_CHANGE_FROM, body='desk', mind=base / 'none' / 'mind').run(DESK_SESSIONS)
    # GEN1: the three-body course first, then the desk, one mind
    long_course(base / 'gen1', seed, per_body=25, shared=True, change_from=CHANGE_FROM)
    Teacher(base / 'gen1' / 'desk', seed=seed, drift_from=DESK_CHANGE_FROM, body='desk', mind=base / 'gen1' / 'mind').run(DESK_SESSIONS)
    out = {}
    for cond in ('none', 'gen1'):
        r = evaluate(base / cond / 'desk', 100 + seed, out_dir / f'{cond}-s{seed}.json', sealed)
        out[cond] = {k: r[k] for k in ('summary', 'held_why')} | {k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'}
                                                                    for k in ('unseen_change', 'oracle', 'delayed')}
        shutil.copy(base / cond / 'desk' / 'log.jsonl', out_dir / f'{cond}-s{seed}-course-log.jsonl')
    (out_dir / f'summary-s{seed}.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[3:] if a.startswith('sealed:')), None)
    print(json.dumps(run(int(sys.argv[1]), sys.argv[2], sealed), indent=1))
