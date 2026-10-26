"""The pre-registered cross-body transfer probe (TRANSFER_PROTOCOL.md; evaluator side).

One mind learns on the board and the file body (a synthetic-teacher course, shared mind). Then, in body B, the person
says body A's English word for 'make it vanish' with a selection phrase known in B. The same mind copy answers with the
transfer mechanism off (the comparison) and on, with the person there and alone. With the person there and the
mechanism on, a 'yes' binds the word in B; the same command is then given again alone (does the word now work in B?).
The screen body has no action whose observed change is that the object vanishes, so only board <-> file can be tested.
Usage: python -m atanor_os.eval.transfer_probe <seed> <out.json> [--per-body 15]
"""
import datetime
import json
import shutil
import sys
from pathlib import Path

from .tutor_life import body_spec, body_targets, english
from ..teach.long_course import run as course
from ..teach.tutor import Tutor
from ..ui.pilot import Clock, drive
from ..ui.teach_server import Session

GONE_TOOLS = {'board': 'scrap', 'fs': 'delete'}


def attempt(base, b, seed, words, sel, act, transfer, alone, tag):
    work = base / f'probe-{tag}'
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(base / b, work / b)
    shutil.copytree(base / 'mind', work / 'mind')
    sess = Session(work / b, seed=seed, source='evaluator', clock=Clock(datetime.datetime(2026, 12, 20, 10, 0)), body=b,
                   mind=work / 'mind', transfer=transfer)
    sess.new_session()                                     # some days later: new objects
    tut = Tutor(sess.home, body_spec(b), f'probe-{seed}')
    tut.start(sel, act)
    st = sess.home.observe(sess.home.existing())
    if not [o for o in tut.truth if not tut.spec.shows(act, o, st)]:
        return None
    rows = []
    for k, alone_k in enumerate([alone] + ([True] if (transfer and not alone) else [])):
        tut.start(sel, act)
        sess.start('command', text=' '.join(words), alone=alone_k)
        drive(sess, tut, {})
        r = [json.loads(l) for l in (work / b / 'log.jsonl').read_text(encoding='utf-8').splitlines()][-1]
        rows.append({'alone': alone_k, 'outcome': r.get('outcome'), 'why': r.get('why'), 'help': r.get('help', {})})
    shutil.rmtree(work)
    return rows


def run(seed, out_file, per_body=15):
    out_file = Path(out_file)
    base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'transfer-s{seed}'
    course(base, seed, per_body, shared=True, bodies=('board', 'fs'), budget=3)
    names = {b: json.loads((base / b / 'names.json').read_text(encoding='utf-8')) for b in ('board', 'fs')}
    results = []
    for a_body, b_body in (('board', 'fs'), ('fs', 'board')):
        sels_a, acts_a = body_targets(a_body, seed)
        sels_b, acts_b = body_targets(b_body, seed)
        ga = next((i for i, x in enumerate(acts_a) if x['tool'] == GONE_TOOLS[a_body]), None)
        gb = next((i for i, x in enumerate(acts_b) if x['tool'] == GONE_TOOLS[b_body]), None)
        note = None
        if ga is None or ga not in names[a_body]['en_act']:
            note = f'{a_body}: no English phrase taught for its vanish action'
        elif gb is None or str(gb) not in names[b_body]['act']:
            note = f'{b_body}: vanish action not taught'
        if note:
            results.append({'from': a_body, 'to': b_body, 'testable': False, 'note': note})
            continue
        word = english('act', acts_a[ga])[0]
        for s in sorted(names[b_body]['en_sel']):
            words = [word] + english('sel', sels_b[s])
            for transfer in (False, True):
                for alone in (False, True):
                    tag = f"{a_body}-{b_body}-{s}-{int(transfer)}-{int(alone)}"
                    rows = attempt(base, b_body, seed, words, sels_b[s], acts_b[gb], transfer, alone, tag)
                    if rows is None:
                        continue
                    results.append({'from': a_body, 'to': b_body, 'testable': True, 'sel': s, 'transfer': transfer,
                                    'alone': alone, 'attempts': rows})
    out = {'seed': seed, 'results': results}
    out_file.write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


if __name__ == '__main__':
    per = int(sys.argv[sys.argv.index('--per-body') + 1]) if '--per-body' in sys.argv else 15
    r = run(int(sys.argv[1]), sys.argv[2], per)
    print(json.dumps(r, indent=1)[:3000])
