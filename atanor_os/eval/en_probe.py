"""English phrase-order probe (evaluator side). Takes the mind of a finished tutor life, lets the person name every taught
selection and action with its English phrase (pointing or demonstrating while saying it, as in the life), then gives
English commands with nobody there, on a fresh board, for every named selection x named action. The same mind answers
each command twice: with the joint explanation alone (BASE) and with phrase positions (ORDER). Holding is not success.

Forms: 'train' (the life's own order) and 'dev' (development only) here; sealed forms come from a file outside the
repository and are run once, on an evaluation seed, in a frozen snapshot.
Usage: python -m atanor_os.eval.en_probe <life_FULL_dir> <seed> <out.json> [sealed:<path>]
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from .tutor_life import DRIFT, body_spec, body_targets, day_inflow, english

DEV_FORMS = {'train': ['H', 'S', 'T'], 'dev': ['please', 'H', 'S', 'T', 'now']}


def words_of(form, sel, act):
    ea, es = english('act', act), english('sel', sel)
    out = []
    for t in form:
        out += {'H': ea[:1], 'T': ea[1:], 'S': es}.get(t, [t])
    return out


def board(root, seed, drift):
    from ..world.board_world import BoardWorkspace
    if root.exists():
        shutil.rmtree(root)
    home = BoardWorkspace(root)
    for d in range(30, 38):                             # new cards ATANOR has never seen, some already in trays
        home.add_cards({f'p{d}{k}': c for k, c in day_inflow(seed, d).items()})
    home.drift = frozenset(drift)
    return home


def todo(spec, home, tut, act):
    st = home.observe(home.existing())
    rest = [o for o in tut.truth if not spec.shows(act, o, st)]
    if act['tool'] in ('lift', 'unlodge') and any(st[o]['tray'] == '-' for o in rest):
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

    home = board(work / 'board', seed, drift)          # naming session, the person present
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
        pts = tut.point()
        feats = g.feats()
        cands = sorted((x for x in g.mem.claims.claims('selects') if all(set(x['content']['atoms']) <= feats[o] for o in pts)),
                       key=lambda x: (len(g.extension(x['content']['atoms'], feats)), x['id']))
        if cands:
            g.name_phrase(english('sel', sels[s]), cands[0]['content']['concept'], f'P{s}')
            named_s.add(s)
            node_s[s] = cands[0]['content']['concept']
        ac = g.learn_action(f'P{a}')
        same = [x for x in g.mem.claims.claims('effect') if x['content']['tool'] == ac['content']['tool']
                and x['content']['gained'] == ac['content']['gained'] and x['id'] != ac['id']]
        node_a[a] = (same[0] if same else ac)['content']['action']
        g.name_phrase(english('act', acts[a]), node_a[a], f'P{a}')
        named_a.add(a)
        if cands:
            g.apply(cands[0]['content'], ac['content'], f'P{s}.{a}')
        naming.append({'sel': s, 'act': a, 'named': True, 'sel_named': bool(cands), 'confirmed': tut.confirm()})

    rows = []
    for s in sorted(named_s):
        for a in sorted(named_a):
            base_home = board(work / 'cmd_board', seed, drift)
            t0 = Tutor(base_home, spec, f'{seed}-en-cmd')
            t0.start(sels[s], acts[a])
            if not todo(spec, base_home, t0, acts[a]):
                continue
            for fname, form in forms.items():
                words = words_of(form, sels[s], acts[a])
                row = {'sel': s, 'act': a, 'form': fname, 'taught_pair': (s, a) in taught, 'words': words}
                for st in (None, 'order'):
                    h = board(work / 'cmd_board', seed, drift)
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
           'summary': summ, 'rows': rows}
    out_file.write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    if not keep:
        shutil.rmtree(work)
    return out


if __name__ == '__main__':
    forms = None
    if len(sys.argv) > 4 and sys.argv[4].startswith('sealed:'):
        forms = json.loads(Path(sys.argv[4][7:]).read_text(encoding='utf-8'))['forms']
    r = run(sys.argv[1], int(sys.argv[2]), sys.argv[3], forms)
    print(json.dumps({k: r[k] for k in ('named_sel', 'named_act', 'summary')}, indent=1))
