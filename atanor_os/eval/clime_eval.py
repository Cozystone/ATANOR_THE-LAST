"""NEW_BODY_DESIGN.md evaluator for the climate bays (evaluator side; never seen by the teacher). Alone, on a world of
new bays from another seed, with the outcome rule of the desk round-2 evaluator (success, partial, wrong, missed,
held, refused):
  taught / combo / english   symbols and the sealed English forms
  unseen change              'vent' stops and 'flush' appears (never in the course); the first attempt is the measure
  time                       the same commands after 1 and 2 outside changes (the weather moves the bays first; the
                             person means the state at the moment of the command)
  harm                       counted apart: a command after which a bay the person did not expect to change (hot ones
                             to warm, frosty ones to cool, sealed ones) was changed
  synonyms                   sealed substitutes, en_probe's method
  ORACLE                     the right calls on every meant object, scored with the same rule (main, unseen, time)
Usage: python -m atanor_os.eval.clime_eval <course_dir> <eval_seed> <out.json> [sealed:<clime_sealed.json>]
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .desk_eval2 import GOOD, grants, outcome
from .en_probe import DEV_FORMS, words_of
from .tutor_life import DRIFT, body_spec, body_targets, clime_inflow, english
from ..agent.learners import make, name as learner_name
from ..teach.tutor import Tutor

DEV_SUBS = {'bays': ['rooms'], 'cool': ['ease']}               # development only (seed 1)
UNSEEN = 'vent_retired'


def world(root, eval_seed, drift, ticks=0):
    from ..world.clime_world import ClimeWorkspace
    if root.exists():
        shutil.rmtree(root)
    home = ClimeWorkspace(root, seed=eval_seed * 10)
    for d in range(40, 45):
        home.add_bays(clime_inflow(eval_seed, d))
    for _ in range(1 + ticks):                             # some outside changes before the command
        home.tick()
    home.drift = frozenset(drift)
    return home


def harmed(spec, act, tut):
    now = tut._state()
    return any(not spec.possible(act, o, tut.before) and now.get(o) != tut.before[o] for o in tut.truth)


def oracle_res(spec, h, tut, act):
    acted, failed = [], []
    for o in tut.truth:
        if not spec.possible(act, o, tut.before) or spec.shows(act, o, tut.before):
            continue                                       # the oracle knows the person's intent and what is done already
        tool, args = spec.steps(act, o, h.drift)
        try:
            r = h.execute(tool, args, grants(h), actor='evaluator')
        except ValueError:
            r = {'ok': False}
        (acted if r['ok'] else failed).append(o)
    return {'ok': not failed, 'acted': acted, 'failed': failed}


def evaluate(course, eval_seed, out_file, sealed=None):
    course, out_file = Path(course), Path(out_file)
    names = json.loads((course / 'names.json').read_text(encoding='utf-8'))
    mind_dir = Path(names['mind']) if names.get('mind') else course / 'mind'
    sels, acts = body_targets('clime', names['seed'])
    spec, drift = body_spec('clime'), [DRIFT['clime']]
    sd = json.loads(Path(sealed).read_text(encoding='utf-8')) if sealed else {'forms': DEV_FORMS, 'subs': DEV_SUBS}
    pairs_taught = set()
    for r in map(json.loads, (course / 'teacher_log.jsonl').read_text(encoding='utf-8').splitlines()):
        if r['activity'] == 'lesson' and r.get('outcome') == 'success':
            pairs_taught.add((sels.index(r['sel']), acts.index(r['act'])))
    work = Path(__file__).resolve().parents[3].parent / 'probe-work' / out_file.stem
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    def fresh():
        if (work / 'm').exists():
            shutil.rmtree(work / 'm')
        shutil.copytree(mind_dir, work / 'm')
        return work / 'm'

    def cmd(h, words, mind):
        return make(h, mind, person=None, source='evaluator', caps=grants(h)).obey(words)

    def setup(d, s, a, ticks=0):
        h = world(work / 'b', eval_seed, d, ticks)
        t = Tutor(h, spec, f'eval-{eval_seed}')
        t.start(sels[s], acts[a])
        return h, t

    def todo(t, a):
        return [o for o in t.truth if spec.possible(acts[a], o, t.before) and not spec.shows(acts[a], o, t.before)]

    pairs = [(s, a) for s in sorted(int(k) for k in names['sel']) for a in sorted(int(k) for k in names['act'])]
    rows, orc, harms = [], [], Counter()
    for s, a in pairs:
        h, t = setup(drift, s, a)
        if not todo(t, a):
            continue
        orc.append({'part': 'main', 'outcome': outcome(spec, acts[a], t, oracle_res(spec, h, t, acts[a]))})
        tests = [('taught' if (s, a) in pairs_taught else 'combo', [names['act'][str(a)], names['sel'][str(s)]])]
        if s in names['en_sel'] and a in names['en_act']:
            tests += [(f'english:{f}', words_of(form, sels[s], acts[a])) for f, form in sd['forms'].items()]
        for kind, words in tests:
            h, t = setup(drift, s, a)
            res = cmd(h, words, fresh())
            o = outcome(spec, acts[a], t, res)
            hm = harmed(spec, acts[a], t)
            harms[kind.split(':')[0]] += hm
            rows.append({'sel': s, 'act': a, 'kind': kind, 'why': res.get('why'), 'outcome': o, 'harm': hm})
    unseen = []
    udrift = list(drift) + [UNSEEN]
    for s, a in pairs:
        if acts[a]['tool'] != 'vent':
            continue
        h, t = setup(udrift, s, a)
        if not todo(t, a):
            continue
        orc.append({'part': 'unseen', 'outcome': outcome(spec, acts[a], t, oracle_res(spec, h, t, acts[a]))})
        h, t = setup(udrift, s, a)
        mind = fresh()
        words = [names['act'][str(a)], names['sel'][str(s)]]
        first = outcome(spec, acts[a], t, cmd(h, words, mind))
        second = None
        if first not in GOOD:
            t.start(sels[s], acts[a])
            second = outcome(spec, acts[a], t, cmd(h, words, mind))
        unseen.append({'sel': s, 'act': a, 'first': first, 'second': second})
    timed = []
    for k in (1, 2):
        for s, a in pairs:
            h, t = setup(drift, s, a, ticks=k)
            if not todo(t, a):
                continue
            orc.append({'part': 'time', 'outcome': outcome(spec, acts[a], t, oracle_res(spec, h, t, acts[a]))})
            h, t = setup(drift, s, a, ticks=k)
            res = cmd(h, [names['act'][str(a)], names['sel'][str(s)]], fresh())
            hm = harmed(spec, acts[a], t)
            harms['time'] += hm
            timed.append({'ticks': k, 'sel': s, 'act': a, 'why': res.get('why'), 'outcome': outcome(spec, acts[a], t, res), 'harm': hm})
    syn = synonyms(names, sels, acts, spec, drift, eval_seed, sd['subs'], fresh, work, cmd)
    shutil.rmtree(work)
    summ = {}
    for r in rows:
        summ.setdefault(r['kind'].split(':')[0], Counter())[r['outcome']] += 1
    commands = len(rows) + len(unseen) + sum(r['second'] is not None for r in unseen) + len(timed) + syn['commands']
    wrong = (sum(r['outcome'] == 'wrong' for r in rows) + sum(r['first'] == 'wrong' for r in unseen)
             + sum(r['second'] == 'wrong' for r in unseen) + sum(r['outcome'] == 'wrong' for r in timed) + syn['summary']['wrong_total'])
    out = {'course': str(course), 'eval_seed': eval_seed, 'learner': learner_name(),
           'summary': {k: dict(v) for k, v in summ.items()},
           'held_why': dict(Counter(r['why'] for r in rows if r['outcome'] == 'held')), 'rows': rows,
           'unseen_change': {'n': len(unseen), 'first': dict(Counter(r['first'] for r in unseen)),
                             'second': dict(Counter(r['second'] for r in unseen if r['second'])), 'rows': unseen},
           'time': {'n': len(timed), 'outcomes': dict(Counter(r['outcome'] for r in timed)), 'rows': timed},
           'harm': dict(harms),
           'unsealed_without_grant': 0,                    # every evaluator command grants; refusals are reported in outcomes
           'oracle': {p: {'n': sum(r['part'] == p for r in orc), 'good': sum(r['part'] == p and r['outcome'] in GOOD for r in orc)}
                      for p in ('main', 'unseen', 'time')},
           'synonyms': syn, 'commands': commands, 'wrong': wrong}
    out_file.write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


def synonyms(names, sels, acts, spec, drift, eval_seed, subs, fresh, work, cmd):
    train = ['H', 'S', 'T']

    def attempt(pair, words, mind):
        h = world(work / 'b', eval_seed, drift)
        t = Tutor(h, spec, f'eval-{eval_seed}-syn')
        t.start(sels[pair[0]], acts[pair[1]])
        if not [o for o in t.truth if spec.possible(acts[pair[1]], o, t.before) and not spec.shows(acts[pair[1]], o, t.before)]:
            return None
        res = cmd(h, words, mind)
        return {'outcome': outcome(spec, acts[pair[1]], t, res), 'why': res.get('why')}

    pairs = [(s, a) for s in names['en_sel'] for a in names['en_act']]
    plain = [p for p in pairs if (attempt(p, words_of(train, sels[p[0]], acts[p[1]]), fresh()) or {}).get('outcome') in GOOD]
    rows, n = [], 0
    for w in sorted(subs):
        u = subs[w][0]
        uses = [p for p in plain if w in words_of(train, sels[p[0]], acts[p[1]])]
        if not uses:
            continue
        part = 'act' if w in english('act', acts[uses[0][1]]) else 'sel'
        first = uses[0]
        same = 1 if part == 'act' else 0
        second = next((p for p in uses[1:] if p[same] == first[same] and p != first), None)
        say = lambda p: [u if x == w else x for x in words_of(train, sels[p[0]], acts[p[1]])]
        mind = fresh()
        row = {'word': w, 'part': part, 'pair': first, 'reuse_pair': second}
        row['alone_first'] = attempt(first, say(first), mind)
        if row['alone_first'] and row['alone_first']['outcome'] not in GOOD:
            h = world(work / 'b', eval_seed, drift)
            tut = Tutor(h, spec, f'eval-{eval_seed}-syn-teach')
            tut.start(sels[first[0]], acts[first[1]])
            g = make(h, mind, person=tut, source='evaluator', caps=grants(h))
            if part == 'act':
                ac = g.learn_action(f'S-{w}')
                if ac:
                    g.name_phrase([u if x == w else x for x in english('act', acts[first[1]])], ac['content']['action'], f'S-{w}')
            else:
                phrase = [u if x == w else x for x in english('sel', sels[first[0]])]
                sc = g.known_concept(f'S-{w}', phrase) or g.learn_selection(f'S-{w}')
                if sc:
                    g.name_phrase(phrase, sc['content']['concept'], f'S-{w}')
            row['alone_after'] = attempt(first, say(first), mind)
        row['reuse_alone'] = attempt(second, say(second), mind) if second else None
        rows.append(row)
    keys = ('alone_first', 'alone_after', 'reuse_alone')
    summ = {k: dict(Counter(r[k]['outcome'] for r in rows if r.get(k))) for k in keys}
    summ['n'], summ['plain_pairs'] = len(rows), len(plain)
    summ['wrong_total'] = sum((r.get(k) or {}).get('outcome') == 'wrong' for r in rows for k in keys)
    return {'summary': summ, 'rows': rows, 'commands': sum(1 for r in rows for k in keys if r.get(k))}


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[4:] if a.startswith('sealed:')), None)
    r = evaluate(sys.argv[1], int(sys.argv[2]), sys.argv[3], sealed)
    print(json.dumps({k: r[k] for k in ('learner', 'summary', 'commands', 'wrong', 'harm', 'held_why')}
                     | {k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'} for k in ('unseen_change', 'time', 'oracle')}
                     | {'synonyms': r['synonyms']['summary']}, indent=1))
