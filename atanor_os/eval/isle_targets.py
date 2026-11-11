"""The island's five places (reef, moor, tarn, glen, crag; world/isle_world.py), evaluator side: what the person of
each place means (selections and actions), the words said for them, the tool that stops during a course and the one
that stops only at evaluation, the day's new urns, and how a place's world is opened. The urns, steles, attributes
and values are shared by the five places; the tool names and every command word are a place's own, and no word, tool
or value repeats the eight earlier bodies'. Never seen by the learner.
"""
import random
from pathlib import Path

PLACES = ('reef', 'moor', 'tarn', 'glen', 'crag')
CLASS = {'reef': 'ReefWorkspace', 'moor': 'MoorWorkspace', 'tarn': 'TarnWorkspace', 'glen': 'GlenWorkspace', 'crag': 'CragWorkspace'}
URN_IDS = {'reef': 'r{}f{}', 'moor': 'm{}r{}', 'tarn': 't{}n{}', 'glen': 'g{}n{}', 'crag': 'c{}g{}'}

SELS = {
    'reef': [{'coat': 'ashen'}, {'tide': 'neap'}, {'spin': 1}, {'coat': 'umber', 'tide': 'flood'}, {'depth': 0}],
    'moor': [{'coat': 'ochre'}, {'tide': 'ebb'}, {'depth': 3}, {'coat': 'ashen', 'spin': 2}, {'tide': 'flood'}],
    'tarn': [{'coat': 'umber'}, {'spin': 0}, {'tide': 'neap'}, {'coat': 'ochre', 'tide': 'ebb'}, {'depth': 1}],
    'glen': [{'tide': 'flood'}, {'coat': 'ashen'}, {'spin': 2}, {'tide': 'neap', 'coat': 'umber'}, {'depth': 4}],
    'crag': [{'coat': 'ochre'}, {'tide': 'ebb'}, {'depth': 2}, {'coat': 'umber', 'spin': 1}, {'spin': 3}],
}
ACTS = {
    'reef': [('vasko', 'k.flint'), ('vasko', 'k.shale'), ('timbal',), ('orrin',), ('pleth', 'k.basalt'), ('dunnel',)],
    'moor': [('mebrin',), ('sollux', 'k.basalt'), ('sollux', 'k.shale'), ('gavot',), ('ruskin', 'k.flint'), ('ombel',)],
    'tarn': [('farrel', 'k.flint'), ('yonker',), ('clavin', 'k.shale'), ('brosk', 'k.basalt'), ('brosk', 'k.flint'), ('webbin',)],
    'glen': [('hadrel', 'k.flint'), ('ockney', 'k.basalt'), ('pavrin', 'k.shale'), ('pavrin', 'k.flint'), ('tulsk',), ('fennit',)],
    'crag': [('jorvel', 'k.shale'), ('kessin', 'k.flint'), ('kessin', 'k.basalt'), ('ulmar',), ('drosk', 'k.shale'), ('nobbet',)],
}
RETIRED = {'reef': 'timbal', 'moor': 'mebrin', 'tarn': 'yonker', 'glen': 'tulsk', 'crag': 'ulmar'}     # stops during a course
UNSEEN = {'reef': 'orrin', 'moor': 'gavot', 'tarn': 'clavin', 'glen': 'pavrin', 'crag': 'kessin'}      # stops only at evaluation
BIND = {'reef': 'dunnel', 'moor': 'ombel', 'tarn': 'webbin', 'glen': 'fennit', 'crag': 'nobbet'}       # irreversible, needs a grant
DRIFT = {b: f'{t}_retired' for b, t in RETIRED.items()}

# ------------------------------------------------------------ the words said (a place's own; development English)
NOUN = {'reef': 'vessels', 'moor': 'jars', 'tarn': 'pots', 'glen': 'amphorae', 'crag': 'flagons'}
ADJ = {
    'reef': {('coat', 'ashen'): 'morvid', ('coat', 'umber'): 'celsh', ('tide', 'neap'): 'dravin', ('tide', 'flood'): 'ostrel',
             ('spin', 1): 'pennic', ('depth', 0): 'hollen'},
    'moor': {('coat', 'ochre'): 'tavish', ('coat', 'ashen'): 'grumel', ('tide', 'ebb'): 'lorrin', ('tide', 'flood'): 'siskel',
             ('depth', 3): 'burdel', ('spin', 2): 'wimsic'},
    'tarn': {('coat', 'umber'): 'fendral', ('coat', 'ochre'): 'kippan', ('tide', 'neap'): 'mirrow', ('tide', 'ebb'): 'sandrel',
             ('spin', 0): 'quintle', ('depth', 1): 'tobbin'},
    'glen': {('tide', 'flood'): 'brannoch', ('tide', 'neap'): 'eskerin', ('coat', 'ashen'): 'cluddy', ('coat', 'umber'): 'verrane',
             ('spin', 2): 'hoddle', ('depth', 4): 'stumlin'},
    'crag': {('coat', 'ochre'): 'lamprel', ('coat', 'umber'): 'godrel', ('tide', 'ebb'): 'pikkan', ('depth', 2): 'runnic',
             ('spin', 1): 'yarrel', ('spin', 3): 'mossick'},
}
VERB = {
    'reef': {'vasko': 'trindle', 'timbal': 'ammerse', 'orrin': 'flenk', 'pleth': 'corbish', 'dunnel': 'wrapple'},
    'moor': {'mebrin': 'snodge', 'sollux': 'bravel', 'gavot': 'tiddock', 'ruskin': 'plonter', 'ombel': 'hesker'},
    'tarn': {'farrel': 'grimmle', 'yonker': 'dabbet', 'clavin': 'swithe', 'brosk': 'narkle', 'webbin': 'pottle'},
    'glen': {'hadrel': 'clemmer', 'ockney': 'frindle', 'pavrin': 'skodge', 'tulsk': 'wembrel', 'fennit': 'jarkle'},
    'crag': {'jorvel': 'blannet', 'kessin': 'thrabble', 'ulmar': 'scundle', 'drosk': 'mivvet', 'nobbet': 'kraddle'},
}
DEV_SUBS = {'reef': {'vessels': ['containers'], 'flenk': ['flunkel']}, 'moor': {'jars': ['crocks'], 'tiddock': ['toddick']},
            'tarn': {'pots': ['ewers'], 'dabbet': ['dobbit']}, 'glen': {'amphorae': ['pitchers'], 'skodge': ['skadge']},
            'crag': {'flagons': ['carafes'], 'scundle': ['scandle']}}                   # development only
PLACE_OF_TOOL = {t: b for b, v in VERB.items() for t in v}


def targets(body):
    sels = [{'kind': 'urn', 'at': body, **s} for s in SELS[body]]     # 'at' is the place the person is in (not an attribute)
    acts = [{'tool': a[0], **({'second': a[1]} if len(a) > 1 else {})} for a in ACTS[body]]
    return sels, acts


def english(kind, spec):
    """The words for a selection or an action of one of the five places, or None if it is not theirs."""
    if kind == 'sel':
        b = spec.get('at')
        if b not in PLACES:
            return None
        return [ADJ[b][(k, spec[k])] for k in ('tide', 'coat', 'spin', 'depth') if k in spec] + [NOUN[b]]
    b = PLACE_OF_TOOL.get(spec.get('tool'))
    if b is None:
        return None
    return [VERB[b][spec['tool']]] + ([spec['second'][2:]] if spec.get('second') else [])


def inflow(body, seed, day, n=6):
    """The day's new urns (seeded): every coat arrives every day."""
    from ..world.isle_world import COATS, DEPTHS, SPINS, TIDES
    rng = random.Random(f'{body}-inflow-{seed}-{day}')
    coats = list(COATS) + [rng.choice(COATS) for _ in range(n - len(COATS))]
    rng.shuffle(coats)
    return {URN_IDS[body].format(day, k): {'depth': rng.choice(DEPTHS), 'spin': rng.choice(SPINS), 'coat': coats[k], 'tide': rng.choice(TIDES)}
            for k in range(n)}


def workspace(body):
    return getattr(__import__(f'atanor_os.world.{body}_world', fromlist=[CLASS[body]]), CLASS[body])


def open_home(body, root, seed):
    """The place's world under root (made if it is not there yet); nothing arrives and no day passes."""
    root = Path(root)
    return workspace(body)(root / body, create=not (root / body).exists(), seed=seed)


def new_day(home, seed, day_no):
    """The day's urns arrive, then a day passes (steles redrawn, some tides move on, old urns taken away)."""
    home.add_urns(inflow(home.BODY, seed, day_no))
    home.tick()
    return home
