"""DESK_EVAL_PROTOCOL.md runner (evaluator side): for one course seed, the NONE condition (an empty mind taught on the
desk) and the GEN1 condition (a mind that lived the 75-day three-body course, then taught on the desk); ORACLE is
measured inside eval/teacher_eval.py on the same evaluation world.
Usage: python -m atanor_os.eval.desk_eval <seed> <out_dir> [sealed:<path>]
"""
import json
import shutil
import sys
from collections import Counter
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


def synonyms(course, eval_seed, subs, out_file):
    """The desk synonym part of DESK_EVAL_PROTOCOL.md (sealed substitutes, desk_sealed.json), the method of
    en_probe.run_synonyms on the evaluation world: a substitute word in a command already understood, alone first;
    if not done, one showing with the new phrase (person = the Tutor, as in the course); then alone again, and the new
    word in another pair alone. 'outcome' uses teacher_eval's rule; 'judge' is the Tutor's verdict, kept apart."""
    from .en_probe import todo, words_of
    from .teacher_eval import world
    from .tutor_life import DRIFT, body_spec, body_targets, english
    from ..agent.grounding import Grounder
    from ..teach.tutor import Tutor
    course, out_file = Path(course), Path(out_file)
    names = json.loads((course / 'names.json').read_text(encoding='utf-8'))
    mind_dir = Path(names['mind'])
    sels, acts = body_targets('desk', names['seed'])
    spec, drift = body_spec('desk'), [DRIFT['desk']]
    work = Path(__file__).resolve().parents[3].parent / 'probe-work' / (out_file.stem + '-syn')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    train = ['H', 'S', 'T']

    def attempt(pair, words, mind, person=None):
        h = world(work / 'b', eval_seed, drift, 'desk')
        t = Tutor(h, spec, f'eval-{eval_seed}-syn')
        t.start(sels[pair[0]], acts[pair[1]])
        if not todo(spec, h, t, acts[pair[1]]):
            return None
        res = Grounder(h, mind, person=None, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}).obey(words)
        ok = t.judge()
        return {'outcome': 'success' if ok and res.get('ok') else ('wrong' if res.get('acted') else
                                                                    ('missed' if res.get('ok') else 'held')),
                'judge': bool(ok), 'why': res.get('why')}

    def fresh():
        m = work / 'm'
        if m.exists():
            shutil.rmtree(m)
        shutil.copytree(mind_dir, m)
        return m

    pairs = [(s, a) for s in names['en_sel'] for a in names['en_act']]
    plain = [p for p in pairs if (attempt(p, words_of(train, sels[p[0]], acts[p[1]]), fresh()) or {}).get('outcome') == 'success']
    rows = []
    for w in sorted(subs):
        u = subs[w][0]
        uses = [p for p in plain if w in words_of(train, sels[p[0]], acts[p[1]])]
        if not uses:
            continue
        part = 'act' if w in english('act', acts[uses[0][1]]) else 'sel'
        first = uses[0]
        same = 1 if part == 'act' else 0
        second = next((p for p in uses[1:] if p[same] == first[same] and p != first), None)
        cmd = lambda p: [u if x == w else x for x in words_of(train, sels[p[0]], acts[p[1]])]
        mind = fresh()
        row = {'word': w, 'part': part, 'pair': first, 'reuse_pair': second}
        row['alone_first'] = attempt(first, cmd(first), mind)
        if row['alone_first']['outcome'] != 'success':
            h = world(work / 'b', eval_seed, drift, 'desk')
            tut = Tutor(h, spec, f'eval-{eval_seed}-syn-teach')
            tut.start(sels[first[0]], acts[first[1]])
            g = Grounder(h, mind, person=tut, source='evaluator', caps={c: True for c in set(getattr(h, 'CAPABILITY', {}).values())})
            if part == 'act':
                ac = g.learn_action(f'S-{w}')
                if ac:
                    g.name_phrase([u if x == w else x for x in english('act', acts[first[1]])], ac['content']['action'], f'S-{w}')
            else:
                phrase = [u if x == w else x for x in english('sel', sels[first[0]])]
                sc = g.known_concept(f'S-{w}', phrase) or g.learn_selection(f'S-{w}')
                if sc:
                    g.name_phrase(phrase, sc['content']['concept'], f'S-{w}')
            row['teach_help'] = dict(tut.help)
            row['alone_after'] = attempt(first, cmd(first), mind)
        row['reuse_alone'] = attempt(second, cmd(second), mind) if second else None
        rows.append(row)
    keys = ('alone_first', 'alone_after', 'reuse_alone')
    summ = {k: dict(Counter(r[k]['outcome'] for r in rows if r.get(k))) for k in keys}
    summ['n'] = len(rows)
    summ['plain_pairs'] = len(plain)
    summ['wrong_total'] = sum((r.get(k) or {}).get('outcome') == 'wrong' for r in rows for k in keys)
    summ['wrong_but_judged_right'] = sum((r.get(k) or {}).get('outcome') == 'wrong' and r[k]['judge'] for r in rows for k in keys)
    out = {'course': str(course), 'eval_seed': eval_seed, 'summary': summ, 'rows': rows}
    out_file.write_text(json.dumps(out, indent=1), encoding='utf-8')
    shutil.rmtree(work)
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'syn':                               # syn <course seed> <out_dir> <subs json>
        seed, out_dir = int(sys.argv[2]), Path(sys.argv[3])
        subs = json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))['subs']
        base = Path(__file__).resolve().parents[3].parent / 'probe-work' / f'desk-s{seed}'
        print(json.dumps({c: synonyms(base / c / 'desk', 100 + seed, subs, out_dir / f'syn-{c}-s{seed}.json')['summary']
                          for c in ('none', 'gen1')}, indent=1))
    else:
        sealed = next((a[7:] for a in sys.argv[3:] if a.startswith('sealed:')), None)
        print(json.dumps(run(int(sys.argv[1]), sys.argv[2], sealed), indent=1))
