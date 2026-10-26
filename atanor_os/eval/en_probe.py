"""English phrase-order probe (evaluator side). Takes the mind of a finished tutor life, lets the person name every taught
selection and action with its English phrase (pointing or demonstrating while saying it, as in the life), then gives
English commands with nobody there, on a fresh board, for every named selection x named action. The same mind answers
each command twice: with the joint explanation alone (BASE) and with phrase positions (ORDER). Holding is not success.

Forms: 'train' (the life's own order) and 'dev' (development only) here; sealed forms come from a file outside the
repository and are run once, on an evaluation seed, in a frozen snapshot.
Usage: python -m atanor_os.eval.en_probe <life_FULL_dir> <seed> <out.json> [sealed:<path>] [body:fs|view]
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .tutor_life import DRIFT, body_spec, body_targets, day_inflow, english, make_home

DEV_FORMS = {'train': ['H', 'S', 'T'], 'dev': ['please', 'H', 'S', 'T', 'now']}


def words_of(form, sel, act):
    ea, es = english('act', act), english('sel', sel)
    out = []
    for t in form:
        out += {'H': ea[:1], 'T': ea[1:], 'S': es}.get(t, [t])
    return out


def world(root, seed, drift, body='board'):
    """A fresh world ATANOR has never seen: new board cards (some already in trays), new files, or the day's panels."""
    if root.exists():
        shutil.rmtree(root)
    if body == 'board':
        from ..world.board_world import BoardWorkspace
        home = BoardWorkspace(root)
        for d in range(30, 38):
            home.add_cards({f'p{d}{k}': c for k, c in day_inflow(seed, d).items()})
    else:
        for d in (30, 31, 32) if body == 'fs' else (30,):
            home = make_home(body, root, seed, d)
    home.drift = frozenset(drift)
    return home


def todo(spec, home, tut, act):
    """The objects still to act on, or none if the person knows the action cannot be done on them here."""
    st = home.observe(home.existing())
    rest = [o for o in tut.truth if not spec.shows(act, o, st) and getattr(spec, 'possible', lambda a, x, s: True)(act, o, st)]
    if spec.BODY == 'board' and act['tool'] in ('lift', 'unlodge') and any(st[o]['tray'] == '-' for o in rest):
        return []
    if spec.BODY == 'view' and act['tool'] == 'group' and any(st[o]['filter'] != 'all' for o in rest):
        return []
    return rest


def run(life_dir, seed, out_file, forms=None, body='board', keep=False):
    from ..agent.grounding import Grounder
    from ..teach.tutor import Tutor
    forms = forms or DEV_FORMS
    life_dir, out_file = Path(life_dir), Path(out_file)
    work = Path(__file__).resolve().parents[3].parent / 'probe-work' / out_file.stem   # outside the repository
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copytree(life_dir / 'mind', work / 'mind')
    sels, acts = body_targets(body, seed)
    spec, drift = body_spec(body), [DRIFT[body]]
    S = json.loads((life_dir / 'tutor_state.json').read_text(encoding='utf-8'))
    taught = [tuple(p) for p in S['taught']]

    home = world(work / 'board', seed, drift, body)          # naming session, the person present
    tut = Tutor(home, spec, f'{seed}-en-probe')
    g = Grounder(home, work / 'mind', person=tut)
    named_s, named_a, naming, node_s, node_a = set(), set(), [], {}, {}
    for s, a in sorted(taught):
        if s in named_s and a in named_a:
            continue
        tut.start(sels[s], acts[a])
        if not todo(spec, home, tut, acts[a]):
            naming.append({'sel': s, 'act': a, 'named': False})
            continue
        known = g.known_concept(f'P{s}', english('sel', sels[s]))          # the person points while saying the phrase; contrast if unclear
        sc = known or g.learn_selection(f'P{s}')
        cands = [sc] if sc else []
        if cands:
            g.name_phrase(english('sel', sels[s]), cands[0]['content']['concept'], f'P{s}')
            named_s.add(s)
            node_s[s] = cands[0]['content']['concept']
        ac = g.learn_action(f'P{a}')
        node_a[a] = ac['content']['action']             # learn_action reuses an action only when the whole call matches
        g.name_phrase(english('act', acts[a]), node_a[a], f'P{a}')
        named_a.add(a)
        if cands:
            g.apply(cands[0]['content'], ac['content'], f'P{s}.{a}')
        naming.append({'sel': s, 'act': a, 'named': True, 'sel_named': bool(cands), 'sel_known': bool(known), 'confirmed': tut.confirm()})

    rows = []
    for s in sorted(named_s):
        for a in sorted(named_a):
            base_home = world(work / 'cmd_board', seed, drift, body)
            t0 = Tutor(base_home, spec, f'{seed}-en-cmd')
            t0.start(sels[s], acts[a])
            if not todo(spec, base_home, t0, acts[a]):
                continue
            for fname, form in forms.items():
                words = words_of(form, sels[s], acts[a])
                row = {'sel': s, 'act': a, 'form': fname, 'taught_pair': (s, a) in taught, 'words': words}
                for st in (None, 'order'):             # BASE is the explicit comparison; ORDER became the default
                    h = world(work / 'cmd_board', seed, drift, body)
                    if (work / 'cmd_mind').exists():
                        shutil.rmtree(work / 'cmd_mind')
                    shutil.copytree(work / 'mind', work / 'cmd_mind')
                    t = Tutor(h, spec, f'{seed}-en-cmd')
                    t.start(sels[s], acts[a])
                    gr = Grounder(h, work / 'cmd_mind', person=None, structure=st)
                    sd, ad, _ = gr.resolve(words)       # the reading, recorded apart from what was then done
                    res = gr.obey(words)
                    ok = t.judge()
                    k = st or 'base'
                    row[k] = 'success' if ok and res.get('ok') else ('wrong' if res.get('acted') else 'held')
                    row[k + '_why'] = res.get('why')
                    row[k + '_reading'] = 'none' if sd is None else ('meant' if (sd['claim']['content']['concept'], ad['claim']['content']['action']) == (node_s[s], node_a[a]) else 'other')
                rows.append(row)
    summ = {}
    for fname in forms:
        fr = [r for r in rows if r['form'] == fname]
        summ[fname] = {k: dict(Counter(r[k] for r in fr)) for k in ('base', 'order')}
        for k in ('base', 'order'):
            summ[fname][k + '_reading'] = dict(Counter(r[k + '_reading'] for r in fr))
            summ[fname][k + '_held_why'] = dict(Counter(r[k + '_why'] for r in fr if r[k] == 'held'))
        summ[fname]['n'] = len(fr)
        summ[fname]['base_held_order_success'] = sum(r['base'] == 'held' and r['order'] == 'success' for r in fr)
        summ[fname]['base_success_order_not'] = sum(r['base'] == 'success' and r['order'] != 'success' for r in fr)
    out = {'life': str(life_dir), 'seed': seed, 'named_sel': sorted(named_s), 'named_act': sorted(named_a), 'naming': naming,
           'node_s': node_s, 'node_a': node_a, 'summary': summ, 'rows': rows}
    out_file.write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    if not keep:
        shutil.rmtree(work)
    return out


DEV_SUBS = {'copy': ['duplicate'], 'move': ['relocate'], 'delete': ['remove'], 'stash': ['store'], 'shred': ['destroy'],
            'label': ['tag'], 'raise': ['lift'], 'take': ['pull'], 'show': ['display'], 'sort': ['order'], 'group': ['cluster'],
            'files': ['documents'], 'cards': ['notes'], 'panels': ['views']}


def run_synonyms(life_dir, seed, out_file, subs=None, body='board'):
    """An unseen word for something already named. No new structure: alone, ATANOR may act only if the other words
    settle the reading; otherwise it holds. With the person, one showing while saying the new phrase (a demonstration
    for an action word, pointing for a selection word). Then: the same command alone, and the new word in another
    pair alone (does the word, not the sentence, carry over)."""
    from ..agent.grounding import Grounder
    from ..teach.tutor import Tutor
    subs = subs or DEV_SUBS
    out_file = Path(out_file)
    base = run(life_dir, seed, out_file.with_name(out_file.stem + '_naming.json'), forms={'train': ['H', 'S', 'T']}, body=body, keep=True)
    work = Path(__file__).resolve().parents[3].parent / 'probe-work' / (out_file.stem + '_naming')
    sels, acts = body_targets(body, seed)
    spec, drift = body_spec(body), [DRIFT[body]]
    plain = [(r['sel'], r['act']) for r in base['rows'] if r['order'] == 'success']   # understood in the words already named
    train = ['H', 'S', 'T']
    rows = []

    def attempt(pair, words, mind):
        h = world(work / 'syn_board', seed, drift, body)
        t = Tutor(h, spec, f'{seed}-syn')
        t.start(sels[pair[0]], acts[pair[1]])
        res = Grounder(h, mind, person=None).obey(words)
        ok = t.judge()
        return 'success' if ok and res.get('ok') else ('wrong' if res.get('acted') else 'held')

    for w in sorted(subs):
        u = subs[w][0]
        uses = [p for p in plain if w in words_of(train, sels[p[0]], acts[p[1]])]
        if not uses:
            continue
        part = 'act' if w in english('act', acts[uses[0][1]]) else 'sel'
        first = uses[0]
        same = 1 if part == 'act' else 0                      # the reuse pair keeps the part with the new word
        second = next((p for p in uses[1:] if p[same] == first[same] and p != first), None)
        cmd = lambda p: [u if x == w else x for x in words_of(train, sels[p[0]], acts[p[1]])]
        mind = work / 'syn_mind'
        if mind.exists():
            shutil.rmtree(mind)
        shutil.copytree(work / 'mind', mind)
        row = {'word': w, 'sub': u, 'part': part, 'pair': first, 'reuse_pair': second}
        row['alone_first'] = attempt(first, cmd(first), mind)
        if row['alone_first'] != 'success':
            h = world(work / 'syn_board', seed, drift, body)
            tut = Tutor(h, spec, f'{seed}-syn-teach')
            tut.start(sels[first[0]], acts[first[1]])
            g = Grounder(h, mind, person=tut)
            new = cmd(first)
            if part == 'act':
                ac = g.learn_action(f'S-{w}')
                g.name_phrase([u if x == w else x for x in english('act', acts[first[1]])], ac['content']['action'], f'S-{w}')
            else:
                phrase = [u if x == w else x for x in english('sel', sels[first[0]])]
                sc = g.known_concept(f'S-{w}', phrase) or g.learn_selection(f'S-{w}')
                if sc:
                    g.name_phrase(phrase, sc['content']['concept'], f'S-{w}')
                    row['taught_to_named'] = sc['content']['concept'] == base['node_s'][first[0]]
            row['teach_help'] = dict(tut.help)
            row['alone_after'] = attempt(first, new, mind)
        row['reuse_alone'] = attempt(second, cmd(second), mind) if second else None
        rows.append(row)
    summ = {k: dict(Counter(r[k] for r in rows if r.get(k))) for k in ('alone_first', 'alone_after', 'reuse_alone')}
    summ['n'] = len(rows)
    summ['wrong_total'] = sum(r.get(k) == 'wrong' for r in rows for k in ('alone_first', 'alone_after', 'reuse_alone'))
    out = {'life': str(life_dir), 'seed': seed, 'body': body, 'summary': summ, 'rows': rows}
    out_file.write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    shutil.rmtree(work)
    return out


if __name__ == '__main__':
    forms = None
    if len(sys.argv) > 4 and sys.argv[4].startswith('sealed:'):
        forms = json.loads(Path(sys.argv[4][7:]).read_text(encoding='utf-8'))['forms']
    body = next((a[5:] for a in sys.argv[4:] if a.startswith('body:')), 'board')
    syn = next((a[4:] for a in sys.argv[4:] if a.startswith('syn:')), None)
    if syn is not None:
        subs = json.loads(Path(syn).read_text(encoding='utf-8'))['subs'] if syn else None
        r = run_synonyms(sys.argv[1], int(sys.argv[2]), sys.argv[3], subs, body=body)
        print(json.dumps(r['summary'], indent=1))
    else:
        r = run(sys.argv[1], int(sys.argv[2]), sys.argv[3], forms, body=body)
        print(json.dumps({k: r[k] for k in ('named_sel', 'named_act', 'summary')}, indent=1))
