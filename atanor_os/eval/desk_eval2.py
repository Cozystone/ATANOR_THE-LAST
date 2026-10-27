"""DESK_EVAL2_PROTOCOL.md evaluator (evaluator side; never seen by the teacher). The first-round evaluator
(teacher_eval.py) is kept as it was; this one carries the eight fixes of the generation-1 audit:
  outcome 'partial'   the judge accepts the result, and every object the learner reports as failed is one a person
                      does not expect to change (DeskSpec.possible). Not wrong; counted as success, reported apart.
  ORACLE              scored with the same outcome rule, acting literally on every object meant (it does not drop
                      the impossible ones first); also in the unseen tool change and the delayed test.
  unseen change       the first attempt is the measure; the second counts only after a failed first.
  delayed             (a) carried out: after the command and one tick, every draft meant is queued, sent or failed;
                      (b) re-sends: sends tried on drafts already queued or sent; retries of failed drafts apart.
                      Three worlds per seed (arrivals on days 40-44, 45-49, 50-54).
  synonyms            new sealed substitutes; words of two-word action phrases are 'redundant' and kept apart.
  English             new sealed forms.
  modifier (round 3)  two English-named selections whose phrases differ by one added word: that word replaced by its
                      sealed substitute in the narrower phrase, with each English-named action, alone. Acting on the
                      broader set is wrong; holding is not.
The learner is the current one, or the frozen generation-1 copy (agent/learners.py, ATANOR_LEARNER=g35).
Usage: python -m atanor_os.eval.desk_eval2 <course_dir> <eval_seed> <out.json> [sealed:<desk2_sealed.json>]
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .en_probe import DEV_FORMS, words_of
from .tutor_life import DRIFT, body_spec, body_targets, desk_inflow, english
from ..agent.learners import make, name as learner_name
from ..teach.tutor import Tutor

DEV_SUBS = {'complete': ['finish'], 'notes': ['memos']}       # development only (seed 1)
WORLD_DAYS = ((40, 45), (45, 50), (50, 55))
REDUNDANT_TOOLS = ('file', 'tag')                             # two-word action phrases: the other word decides
GOOD = ('success', 'partial')


def grants(h):
    return {c: True for c in set(getattr(h, 'CAPABILITY', {}).values())}


def world(root, eval_seed, drift, variant=0):
    from ..world.desk_world import DeskWorkspace
    if root.exists():
        shutil.rmtree(root)
    home = DeskWorkspace(root, seed=eval_seed * 10 + variant)
    for d in range(*WORLD_DAYS[variant]):
        home.add_items(desk_inflow(eval_seed, d))
    home.tick()                                            # some outside changes before the day starts
    home.drift = frozenset(drift)
    return home


def outcome(spec, act, tut, res):
    ok = tut.judge()
    if res.get('refused'):
        return 'refused'
    if ok and res.get('ok'):
        return 'success'
    failed = res.get('failed') or []
    withheld = res.get('withheld') or []
    if ok and (failed or withheld) and not any(spec.possible(act, o, tut.before) for o in failed + withheld):
        return 'partial'
    if withheld and tut.judge(ignore=withheld):
        return 'part-held'                                 # GEN2_H3_PROTOCOL.md: right on what it did, held the rest
    if res.get('acted'):
        return 'wrong'
    return 'missed' if res.get('ok') else 'held'


def oracle_res(spec, h, tut, act):
    """Literal: the right call on every object meant that does not show the result yet."""
    acted, failed = [], []
    st = h.observe(h.existing())
    for o in tut.truth:
        if spec.shows(act, o, st):
            continue
        tool, args = spec.steps(act, o, h.drift)
        try:
            r = h.execute(tool, args, grants(h), actor='evaluator')
        except ValueError:
            r = {'ok': False}
        (acted if r['ok'] else failed).append(o)
    return {'ok': not failed, 'acted': acted, 'failed': failed}


def something_to_do(spec, act, t):
    return any(not spec.shows(act, o, t.before) for o in t.truth)


def evaluate(course, eval_seed, out_file, sealed=None):
    course, out_file = Path(course), Path(out_file)
    names = json.loads((course / 'names.json').read_text(encoding='utf-8'))
    mind_dir = Path(names['mind']) if names.get('mind') else course / 'mind'
    sels, acts = body_targets('desk', names['seed'])
    spec, drift = body_spec('desk'), [DRIFT['desk']]
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

    def setup(variant_drift, s, a, variant=0):
        h = world(work / 'b', eval_seed, variant_drift, variant)
        t = Tutor(h, spec, f'eval-{eval_seed}')
        t.start(sels[s], acts[a])
        return h, t

    pairs = [(s, a) for s in sorted(int(k) for k in names['sel']) for a in sorted(int(k) for k in names['act'])]
    rows, orc = [], []
    for s, a in pairs:
        h, t = setup(drift, s, a)
        if not something_to_do(spec, acts[a], t):
            continue
        orc.append({'part': 'main', 'sel': s, 'act': a, 'outcome': outcome(spec, acts[a], t, oracle_res(spec, h, t, acts[a]))})
        tests = [('taught' if (s, a) in pairs_taught else 'combo', [names['act'][str(a)], names['sel'][str(s)]])]
        if s in names['en_sel'] and a in names['en_act']:
            tests += [(f'english:{f}', words_of(form, sels[s], acts[a])) for f, form in sd['forms'].items()]
        for kind, words in tests:
            h, t = setup(drift, s, a)
            res = cmd(h, words, fresh())
            rows.append({'sel': s, 'act': a, 'kind': kind, 'why': res.get('why'), 'outcome': outcome(spec, acts[a], t, res)})
    unseen = []
    udrift = list(drift) + ['tag_retired']
    for s, a in pairs:
        if acts[a]['tool'] != 'tag':
            continue
        h, t = setup(udrift, s, a)
        if not something_to_do(spec, acts[a], t):
            continue
        orc.append({'part': 'unseen', 'sel': s, 'act': a, 'outcome': outcome(spec, acts[a], t, oracle_res(spec, h, t, acts[a]))})
        h, t = setup(udrift, s, a)
        mind = fresh()
        words = [names['act'][str(a)], names['sel'][str(s)]]
        first = outcome(spec, acts[a], t, cmd(h, words, mind))
        second = None
        if first not in GOOD:                              # a second attempt is a test only after a failed first
            t.start(sels[s], acts[a])
            second = outcome(spec, acts[a], t, cmd(h, words, mind))
        unseen.append({'sel': s, 'act': a, 'first': first, 'second': second})
    delayed = []
    for v in range(len(WORLD_DAYS)):
        for s, a in pairs:
            if acts[a]['tool'] != 'send':
                continue
            for who in ('oracle', 'learner'):
                h, t = setup(drift, s, a, v)
                todo = [o for o in t.truth if spec.possible(acts[a], o, t.before) and not spec.shows(acts[a], o, t.before)]
                if not todo:
                    break
                words = [names['act'][str(a)], names['sel'][str(s)]]
                mind = fresh()
                if who == 'oracle':
                    oracle_res(spec, h, t, acts[a])
                else:
                    cmd(h, words, mind)
                h.tick()
                st = h.observe(h.existing())
                carried = all((st.get(o) or {}).get('status') in ('queued', 'sent', 'failed') for o in todo)
                status = {o: (st.get(o) or {}).get('status') for o in t.truth}
                n0 = sum(1 for _ in open(h.root / 'world_log.jsonl', encoding='utf-8'))
                if who == 'oracle':                         # the oracle sends only what is still a draft
                    for o in t.truth:
                        if status[o] == 'draft':
                            h.execute('send', (o,), grants(h), actor='evaluator')
                else:
                    cmd(h, words, mind)                    # the same command again
                again = [json.loads(l) for l in open(h.root / 'world_log.jsonl', encoding='utf-8')][n0:]
                sends = [r['args'][0] for r in again if r.get('event') == 'act' and r.get('tool') == 'send']
                prevented = sum(1 for r in again if r.get('event') == 'duplicate_prevented')
                row = {'variant': v, 'sel': s, 'act': a, 'n': len(todo), 'carried_out': carried, 'prevented': prevented,
                       'resend': sum(1 for o in sends if status.get(o) in ('queued', 'sent')),
                       'retry_failed': sum(1 for o in sends if status.get(o) == 'failed')}
                if who == 'oracle':
                    orc.append({'part': 'delayed', 'sel': s, 'act': a, 'outcome': 'success' if carried and not row['resend'] else 'fail'})
                else:
                    delayed.append(row)
    syn = synonyms(names, sels, acts, spec, drift, eval_seed, sd['subs'], fresh, work, cmd)
    modifier, untested = [], []
    for n in names['en_sel']:
        for b in names['en_sel']:
            pn, pb = english('sel', sels[n]), english('sel', sels[b])
            if len(pn) != len(pb) + 1 or [w for w in pn if w not in pb] == [] or [w for w in pn if w not in pb][0] in pb:
                continue
            extra = next(w for w in pn if w not in pb)
            if [w for w in pn if w != extra] != pb:
                continue
            if extra not in sd['subs']:
                untested.append({'narrow': n, 'broad': b, 'word': extra})
                continue
            for a in names['en_act']:
                h, t = setup(drift, n, a)
                if not something_to_do(spec, acts[a], t):
                    continue
                words = [sd['subs'][extra][0] if x == extra else x for x in words_of(['H', 'S', 'T'], sels[n], acts[a])]
                res = cmd(h, words, fresh())
                modifier.append({'narrow': n, 'broad': b, 'act': a, 'word': extra, 'outcome': outcome(spec, acts[a], t, res), 'why': res.get('why')})
    shutil.rmtree(work)
    summ = {}
    for r in rows:
        summ.setdefault(r['kind'].split(':')[0], Counter())[r['outcome']] += 1
    commands = (len(rows) + len(unseen) + sum(r['second'] is not None for r in unseen) + 2 * len(delayed) + len(modifier)
                + sum(1 for r in syn['rows'] for k in ('alone_first', 'alone_after', 'reuse_alone') if r.get(k)))
    wrong = (sum(r['outcome'] == 'wrong' for r in rows) + sum(r['first'] == 'wrong' for r in unseen)
             + sum(r['second'] == 'wrong' for r in unseen) + syn['summary']['wrong_total'] + sum(r['outcome'] == 'wrong' for r in modifier))
    out = {'course': str(course), 'eval_seed': eval_seed, 'learner': learner_name(),
           'summary': {k: dict(v) for k, v in summ.items()},
           'held_why': dict(Counter(r['why'] for r in rows if r['outcome'] == 'held')), 'rows': rows,
           'unseen_change': {'n': len(unseen), 'first': dict(Counter(r['first'] for r in unseen)),
                             'second': dict(Counter(r['second'] for r in unseen if r['second'])), 'rows': unseen},
           'delayed': {'n': len(delayed), 'carried_out': sum(r['carried_out'] for r in delayed),
                       'resend': sum(r['resend'] for r in delayed), 'retry_failed': sum(r['retry_failed'] for r in delayed),
                       'prevented_by_desk': sum(r.get('prevented', 0) for r in delayed),
                       'rows': delayed},
           'oracle': {**{p: {'n': sum(r['part'] == p for r in orc), 'good': sum(r['part'] == p and r['outcome'] in GOOD for r in orc)}
                         for p in ('main', 'unseen')},
                      'delayed': {'n': sum(r['part'] == 'delayed' for r in orc),
                                  'good': sum(r['part'] == 'delayed' and r['outcome'] == 'success' for r in orc)},
                      'rows': orc},
           'synonyms': syn, 'modifier': {'n': len(modifier), 'outcomes': dict(Counter(r['outcome'] for r in modifier)),
                                         'untested': untested, 'rows': modifier},
           'commands': commands, 'wrong': wrong}
    out_file.write_text(json.dumps(out, indent=1), encoding='utf-8')
    return out


def synonyms(names, sels, acts, spec, drift, eval_seed, subs, fresh, work, cmd):
    """en_probe.run_synonyms' method on the evaluation world, with the new sealed substitutes."""
    train = ['H', 'S', 'T']

    def attempt(pair, words, mind):
        h = world(work / 'b', eval_seed, drift)
        t = Tutor(h, spec, f'eval-{eval_seed}-syn')
        t.start(sels[pair[0]], acts[pair[1]])
        if not something_to_do(spec, acts[pair[1]], t):
            return None
        res = cmd(h, words, mind)
        return {'outcome': outcome(spec, acts[pair[1]], t, res), 'why': res.get('why')}

    pairs = [(s, a) for s in names['en_sel'] for a in names['en_act']]
    plain = [p for p in pairs if (attempt(p, words_of(train, sels[p[0]], acts[p[1]]), fresh()) or {}).get('outcome') in GOOD]
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
        say = lambda p: [u if x == w else x for x in words_of(train, sels[p[0]], acts[p[1]])]
        mind = fresh()
        row = {'word': w, 'part': part, 'pair': first, 'reuse_pair': second,
               'redundant': part == 'act' and acts[first[1]]['tool'] in REDUNDANT_TOOLS}
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
            row['teach_help'] = dict(tut.help)
            row['alone_after'] = attempt(first, say(first), mind)
        row['reuse_alone'] = attempt(second, say(second), mind) if second else None
        rows.append(row)
    keys = ('alone_first', 'alone_after', 'reuse_alone')
    info = [r for r in rows if not r['redundant']]
    summ = {k: dict(Counter(r[k]['outcome'] for r in info if r.get(k))) for k in keys}
    summ['redundant'] = {k: dict(Counter(r[k]['outcome'] for r in rows if r['redundant'] and r.get(k))) for k in keys}
    summ['n'], summ['n_redundant'], summ['plain_pairs'] = len(info), len(rows) - len(info), len(plain)
    summ['wrong_total'] = sum((r.get(k) or {}).get('outcome') == 'wrong' for r in rows for k in keys)
    return {'summary': summ, 'rows': rows}


if __name__ == '__main__':
    sealed = next((a[7:] for a in sys.argv[4:] if a.startswith('sealed:')), None)
    r = evaluate(sys.argv[1], int(sys.argv[2]), sys.argv[3], sealed)
    print(json.dumps({k: r[k] for k in ('learner', 'summary', 'commands', 'wrong')}
                     | {k: {kk: vv for kk, vv in r[k].items() if kk != 'rows'} for k in ('unseen_change', 'delayed', 'oracle')}
                     | {'synonyms': r['synonyms']['summary'], 'modifier': {k: v for k, v in r['modifier'].items() if k != 'rows'}}, indent=1))
