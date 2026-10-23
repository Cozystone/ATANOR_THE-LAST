"""Task generation and splits (evaluator-owned; EXPERIMENT_PROTOCOL.md). Never imported by agent/.

v2 (after review magi-review-01): the convert template requires an output whose content differs
from every observable file (only the convert tool can produce that); the test split rotates its
extension list so md/log/json all occur; the planner budget is a deterministic prediction cap.
"""
import random

from ..core.types import Goal, Literal
from ..world.fs_world import Workspace, name_ext

WORDS_TRAIN = ['alpha', 'bravo', 'cedar', 'delta', 'ember', 'fjord', 'gale', 'harbor', 'iris', 'jade',
               'kelp', 'lumen', 'maple', 'nova', 'opal', 'pine', 'quartz', 'reed', 'sage', 'tide']
WORDS_TEST = ['umber', 'violet', 'willow', 'xenon', 'yarrow', 'zephyr', 'amber', 'basil', 'coral', 'dune',
              'elm', 'fern', 'grove', 'hazel', 'ivory', 'juniper', 'kite', 'lotus', 'mint', 'nectar']
EXT = {'train': ['txt', 'csv'], 'dev': ['txt', 'csv'], 'test': ['txt', 'csv', 'md', 'log', 'json']}
TARGET = {'train': {'backup': ['bak'], 'sort': ['sorted'], 'convert': ['conv']},
          'dev':   {'backup': ['bak'], 'sort': ['sorted'], 'convert': ['conv']},
          'test':  {'backup': ['archive', 'out/archive'], 'sort': ['bins', 'out/bins'],
                    'convert': ['rendered', 'out/rendered']}}
TEMPLATES = ('backup', 'sort', 'convert')
# `predictions` is the binding per-call search budget (deterministic, identical for every condition);
# `seconds` is only a safety guard whose use is recorded as a stop reason.
BUDGET = {'actions': 20, 'predictions': 400000, 'nodes': 600, 'depth': 12, 'seconds': 180.0}


def layout(rng, split):
    words = WORDS_TEST if split == 'test' else WORDS_TRAIN
    exts = EXT[split]
    n = rng.choice([3, 4]) if split == 'test' else rng.choice([2, 3])
    names = rng.sample(words, n + 2)
    offset = rng.randrange(len(exts))
    files = {}
    for i in range(n):
        ext = 'txt' if i == 0 else (exts[(i + offset) % len(exts)] if split == 'test' else rng.choice(exts))
        files[f'{names[i]}.{ext}'] = f'{names[i]} {rng.random():.6f}\n'.encode()
    return files, names[n], f'{names[n]}/{names[n + 1]}.txt'


def materialize(root, files, ddir, dfile):
    ws = Workspace(root)
    (ws.root / ddir).mkdir()
    for p, c in files.items():
        (ws.root / p).write_bytes(c)
    (ws.root / dfile).write_bytes(b'keep me\n')
    return ws


def make_task(index, split, root):
    """Deterministic task `index` of `split`, materialized as a fresh real workspace under `root`."""
    rng = random.Random(f'{split}-{index}')
    files, ddir, dfile = layout(rng, split)
    ws = materialize(root, files, ddir, dfile)
    template = TEMPLATES[index % 3] if split == 'test' else rng.choice(TEMPLATES)
    target = rng.choice(TARGET[split][template])
    originals = sorted(files)
    h = {f: ws.attrs(f)['hash'] for f in originals}
    keep = [Literal('kind', (ddir,), 'dir'), Literal('kind', (dfile,), 'file'),
            Literal('hash', (dfile,), ws.attrs(dfile)['hash'])]
    must, universe = [], [ddir, dfile] + originals
    for f in originals:
        if template == 'backup':
            d = f'{target}/{f}'
            must += [Literal('kind', (d,), 'file'), Literal('same_content', (d, f), True)]
            keep += [Literal('kind', (f,), 'file'), Literal('hash', (f,), h[f])]
        elif template == 'sort':
            d = f'{target}/{name_ext(f)}/{f}'
            must += [Literal('kind', (d,), 'file'), Literal('hash', (d,), h[f]), Literal('kind', (f,), 'absent')]
        elif name_ext(f) == 'txt':
            d = f'{target}/{f[:-4]}.md'
            # A file that is content-distinct from every observable file: copy/move cannot produce it.
            must += [Literal('kind', (d,), 'file')] + [Literal('same_content', (d, x), False)
                                                       for x in originals + [dfile]]
            keep += [Literal('kind', (f,), 'file'), Literal('hash', (f,), h[f])]
        else:
            keep += [Literal('kind', (f,), 'file'), Literal('hash', (f,), h[f])]
            continue
        universe.append(d)
    goal = Goal(f'{split}-{index}-{template}', must, keep, {'destroy': False}, dict(BUDGET), sorted(set(universe)))
    return ws, goal, {'template': template, 'target': target, 'files': originals, 'split': split, 'index': index}
