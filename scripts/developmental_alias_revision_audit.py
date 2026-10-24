"""Historical exposed contradiction ingestion; no policy/capability claim."""
import json
import sys
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_effect_families import EffectFamilies
from scripts.developmental_continual_probe import score
from packages.action_core.world import Frame, Action


def run(output, partial=False, tree=False, sequence=None):
    def read(name): return json.loads((ROOT/'evidence'/name).read_text())
    old = read('developmental-continual.json')['records'] + read('developmental-online-eval.json')['records']
    scope = read('developmental-rewrite-scope.json')['rows']
    seeds = [read('developmental-composition-probe.json')['rows'][0]['native_record']]
    seeds += [r['record'] for r in scope if r['case'] in ('declared_absent', 'declared_present')]
    cases = sequence or ['hidden_absent', 'hidden_present']
    pair = [next(r['record'] for r in scope if r['case']==case) for case in cases]
    if sequence is None:
        assert pair[0]['before']==pair[1]['before'] and pair[0]['action']==pair[1]['action']
        assert pair[0]['after']!=pair[1]['after']
    model = EffectFamilies(old+seeds)
    if partial or tree:
        from packages.shared_world.contextual_rewrite import ContextualRewrite
        from packages.shared_world.partial_conditional_support import fit_partial
        from packages.shared_world.conditional_tree_support import fit_tree
        model.structural = ContextualRewrite(old+seeds, fitter=fit_tree if tree else fit_partial)
    def measure(records):
        counts = Counter()
        for r in records:
            counts.update(score(model.predict(Frame.from_dict(r['before']), Action.from_dict(r['action'])), Frame.from_dict(r['after'])))
        return dict(counts)
    snapshots = []
    phases = [('before', [])] + ([(f'after_{case}', [record]) for case,record in zip(cases,pair)]
        if sequence is not None else [('after_absent', [pair[0]]), ('after_both', [pair[1]])])
    for phase, extra in phases:
        model.learn(extra)
        snapshots.append(dict(phase=phase, old=measure(old), scope={r['case']:measure([r['record']]) for r in scope}))
    with output.open('x') as f: json.dump(dict(exposed=True, partial=partial, tree=tree,
        sequence=sequence, snapshots=snapshots), f, sort_keys=True)
    print(json.dumps(snapshots))


if __name__ == '__main__':
    sequence = next((arg.split('=',1)[1].split(',') for arg in sys.argv[2:] if arg.startswith('--sequence=')), None)
    run(Path(sys.argv[1]), '--partial' in sys.argv[2:], '--tree' in sys.argv[2:], sequence)
