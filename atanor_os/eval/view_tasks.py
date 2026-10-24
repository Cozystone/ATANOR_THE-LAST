"""P3 evaluator side for the view body: true model, task generator with splits, exploration block.
Never imported by agent/."""
import random

from ..agent.lift import apply_effects
from ..core.types import Goal, Literal
from ..world.fs_world import name_ext
from ..world.view_world import PANELS, ViewWorkspace, is_value
from .generator import BUDGET, layout, materialize

TRUE_EFFECTS = {
    'open':    [(0, 'kind', ('const', 'panel')), (0, 'filter', ('const', 'all')), (0, 'sort', ('const', 'name')),
                (0, 'group', ('const', 'none'))],
    'close':   [(0, 'kind', ('const', 'absent')), (0, 'filter', ('const', '-')), (0, 'sort', ('const', '-')),
                (0, 'group', ('const', '-'))],
    'filter':  [(0, 'filter', ('copy', 1, 'value'))],
    'sort':    [(0, 'sort', ('copy', 1, 'value'))],
    'group':   [(0, 'group', ('copy', 1, 'value'))],
    'compare': [(0, 'kind', ('const', 'compare')), (0, 'filter', ('copy', 1, 'filter')),
                (0, 'sort', ('copy', 1, 'sort')), (0, 'group', ('const', 'none'))],
}


def view_true_pre(state, tool, args):
    o = [state.get(a) for a in args]
    if any(x is None for x in o):
        return False
    if tool == 'open':
        return args[0] in PANELS and o[0]['kind'] == 'absent'
    if tool == 'close':
        return o[0]['kind'] in ('panel', 'compare')
    if tool == 'filter':
        return o[0]['kind'] == 'panel' and o[1]['kind'] == 'ext'
    if tool == 'sort':
        return o[0]['kind'] in ('panel', 'compare') and o[1]['kind'] == 'key'
    if tool == 'group':
        return o[0]['kind'] == 'panel' and o[1]['kind'] == 'grp' and (o[1]['value'] == 'none' or o[0]['filter'] == 'all')
    return args[0] in PANELS and o[0]['kind'] == 'absent' and o[1]['kind'] == 'panel'


class ViewTrueModel:
    name = 'ORACLE'

    def predict(self, state, tool, args, sig=None):
        if not view_true_pre(state, tool, args):
            return None, 'oracle_fail'
        return apply_effects(state, args, TRUE_EFFECTS[tool]), 'oracle'

    def update(self, exp):
        pass

    def describe(self):
        return {'condition': self.name, 'body': 'view'}


# --- splits: train/dev use p1/p2 and txt/csv/name/size; test uses p3, md/log/json, key ext ---
SPLIT = {
    'train': {'panels': ('p1', 'p2'), 'exts': ('txt', 'csv'), 'keys': ('name', 'size')},
    'dev':   {'panels': ('p1', 'p2'), 'exts': ('txt', 'csv'), 'keys': ('name', 'size')},
    'test':  {'panels': ('p3', 'p1'), 'exts': ('md', 'log', 'json'), 'keys': ('ext', 'size')},
}
TEMPLATES = ('focus', 'regroup', 'compare')


def _initial_spec(rng, split):
    """A plausible starting screen; test starts from a busier screen (two open panels, one filtered)."""
    spec = {'p1': {'kind': 'panel', 'filter': 'all', 'sort': 'name', 'group': 'none'}}
    if split == 'test' or rng.random() < 0.5:
        spec['p2'] = {'kind': 'panel', 'filter': rng.choice(('txt', 'csv')), 'sort': 'size', 'group': 'none'}
    return spec


def make_view_task(index, split, root):
    rng = random.Random(f'view-{split}-{index}')
    files, ddir, dfile = layout(rng, split if split != 'train' else 'train')
    data = materialize(root / 'data', files, ddir, dfile)
    spec = _initial_spec(rng, split)
    ws = ViewWorkspace(root / 'view', data, spec=spec)
    cfg = SPLIT[split]
    template = TEMPLATES[index % 3] if split == 'test' else rng.choice(TEMPLATES)
    keep = [Literal(a, (p,), v) for p, s in spec.items() for a, v in (('kind', s['kind']),)
            if p not in cfg['panels']]                              # untouched panels stay open
    must = []
    if template == 'focus':                 # open a (new) panel and configure it
        p = cfg['panels'][0]
        e, k = rng.choice(cfg['exts']), rng.choice(cfg['keys'])
        must = [Literal('kind', (p,), 'panel'), Literal('filter', (p,), e), Literal('sort', (p,), k)]
    elif template == 'regroup':             # p1 is filtered at the start; grouping needs the unfiltered list first
        p = 'p1'
        spec[p]['filter'] = rng.choice(cfg['exts'])
        ws._write(spec)
        must = [Literal('kind', (p,), 'panel'), Literal('group', (p,), 'ext'), Literal('filter', (p,), 'all')]
    else:                                   # a comparison panel of a configured list panel
        p, c = cfg['panels'][0], 'cmp'
        e = rng.choice(cfg['exts'])
        must = [Literal('kind', (c,), 'compare'), Literal('filter', (c,), e), Literal('kind', (p,), 'panel'),
                Literal('filter', (p,), e)]
    goal = Goal(f'view-{split}-{index}-{template}', must, keep, {'close_panels': False}, dict(BUDGET), [])
    return ws, goal, {'template': template, 'target': cfg['panels'][0], 'files': sorted(files), 'split': split,
                      'index': index, 'body': 'view'}


def view_block(rng, root):
    """Exploration workspace for the view body: fresh data plus a random starting screen."""
    files, ddir, dfile = layout(rng, 'train')
    data = materialize(root / 'data', files, ddir, dfile)
    spec = {}
    for p in ('p1', 'p2'):
        if rng.random() < 0.6:
            spec[p] = {'kind': 'panel', 'filter': rng.choice(('all', 'txt', 'csv')),
                       'sort': rng.choice(('name', 'size')), 'group': 'none'}
    return ViewWorkspace(root / 'view', data, spec=spec), []


def view_sem_block(rng, root):
    return view_block(rng, root)
