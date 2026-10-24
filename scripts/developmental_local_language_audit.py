"""Exposed SQL diagnosis: prequential prediction versus hindsight fit.

Constants make single-example expressivity trivial; do not score that as learning.
Separate identical-feature incompatible supports from partition-fit limitations.
No runtime changes, fresh capability claim, source transfer, or outcome leakage
into prequential predictions. Existing local/relational feature sets only.
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.developmental_continual_probe import score
from scripts.developmental_fk_tasks import context
from packages.action_core.world import Frame, Action
from packages.shared_world.relational import _value
from scripts.developmental_rooted_probe import rooted


def switching_probe(output):
    """DEV only: switch feature FAMILY on past conflict, not new concept creation.

Both shadows learn all history; measured CPU includes both, so no sparse-cost
claim. Switch only when the pre-step local rule has neither common support nor
consistent partitions. No names/task IDs/outcomes enter that choice. Fixed rich
features remain externally supplied. Fail gate if errors exceed fixed-rich or
correct singletons fail to improve over local. No retries/tuning this comparison.
"""
    source = ROOT/'evidence/developmental-fk-schema-tasks.json'
    raw = source.read_bytes()
    models = {'local': Model([]), 'rich': Model([], numeric_context=context)}
    totals = {a: Counter() for a in ('local', 'rich', 'adaptive')}
    curves = []
    start = time.process_time()
    for ordinal, row in enumerate(json.loads(raw)['training']):
        before, after = (Frame.from_dict(row[k]) for k in ('before', 'after'))
        action = Action.from_dict(row['action'])
        predictions = {a: m.predict(before, action, True) for a,m in models.items()}
        selected, switched = [], 0
        for left, right in zip(predictions['local'], predictions['rich']):
            assert left[:2] == right[:2]
            key, _ = rooted(before, action, left[0], left[1])
            rule = models['local'].rules.get(key)
            use_rich = rule is not None and not rule.common and not rule.alternatives
            selected.append(right if use_rich else left)
            switched += use_rich
        predictions['adaptive'] = selected
        scores = {a: score(p, after) for a,p in predictions.items()}
        for a,s in scores.items(): totals[a].update(s)
        curves.append(dict(ordinal=ordinal, switched_cells=switched, scores=scores))
        for model in models.values(): model.learn([row])
    passed = (totals['adaptive']['wrong'] <= totals['rich']['wrong'] and
              totals['adaptive']['correct_singleton'] > totals['local']['correct_singleton'])
    report = dict(scope=switching_probe.__doc__, source_sha256=hashlib.sha256(raw).hexdigest(),
                  verdict='DEV_GAIN' if passed else 'NO_GO', totals=totals, curve=curves,
                  total_shadow_cpu_seconds=time.process_time()-start)
    assert source.read_bytes() == raw
    with output.open('x') as stream: json.dump(report, stream, sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('scope','curve')}))


def disagreement_audit(output):
    """Diagnostic replay, not another attempt: can family disagreement flag errors?

Neither outcomes nor error labels select forecasts. Labels below are retrospective
diagnosis. Preserve both sealed comparisons; no new policy or capability claim.
"""
    source = ROOT/'evidence/developmental-fk-schema-tasks.json'
    raw = source.read_bytes()
    models = [Model([]), Model([], numeric_context=context)]
    counts, errors = Counter(), []
    for ordinal, row in enumerate(json.loads(raw)['training']):
        before, after = (Frame.from_dict(row[k]) for k in ('before','after'))
        action = Action.from_dict(row['action'])
        predictions = [m.predict(before, action, True) for m in models]
        for left, right in zip(*predictions):
            assert left[:2] == right[:2]
            truth = _value(after, left[0], left[1])
            wrong = [bool(p[2]) and truth not in p[2] for p in (left,right)]
            same = left[2] == right[2]
            counts['cells'] += 1
            counts['different_predictions'] += not same
            counts['both_wrong'] += all(wrong)
            counts['same_wrong'] += same and all(wrong)
            counts['any_wrong'] += any(wrong)
            counts['different_and_any_wrong'] += not same and any(wrong)
            key,nodes = rooted(before,action,left[0],left[1])
            seen = any(f==context(before,nodes) for f,_ in models[1].examples.get(key,()))
            category = 'seen' if seen else 'novel'
            outcome = ('unknown' if not right[2] else 'wrong' if wrong[1] else
                       'correct_singleton' if len(right[2])==1 else 'correct_set')
            counts[category+':'+outcome] += 1
            if any(wrong):
                errors.append(dict(ordinal=ordinal,field=left[0],address=left[1],truth=truth,
                    local=left[2],rich=right[2],same=same,
                    past_examples=len(models[0].examples.get(key,())),
                    rich_context_seen=seen))
        for m in models: m.learn([row])
    assert source.read_bytes() == raw
    report = dict(scope=disagreement_audit.__doc__, counts=counts,errors=errors,
                  source_sha256=hashlib.sha256(raw).hexdigest())
    with output.open('x') as stream: json.dump(report,stream,sort_keys=True)
    print(json.dumps(report))


def run(output):
    source = ROOT/'evidence/developmental-fk-schema-tasks.json'
    raw = source.read_bytes()
    records = json.loads(raw)['training']
    report = {'scope': __doc__, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'arms': {}}
    for arm, features in [('local', None), ('relational', context)]:
        model = Model([], numeric_context=features)
        pre, changed, fitted, causes = Counter(), Counter(), Counter(), Counter()
        curve = []
        for ordinal, row in enumerate(records):
            before, after = (Frame.from_dict(row[k]) for k in ('before', 'after'))
            action = Action.from_dict(row['action'])
            prediction = model.predict(before, action, True)
            result = score(prediction, after)
            pre.update(result)
            changed.update(score([p for p in prediction if _value(before, p[0], p[1]) != _value(after, p[0], p[1])], after))
            curve.append({'ordinal': ordinal, 'score': result})
            model.learn([row])
        witnesses = []
        for key, rule in model.rules.items():
            if rule.common or rule.alternatives:
                causes['resolved_contexts'] += 1
                continue
            groups = defaultdict(list)
            for feature, symbols in model.examples[key]:
                groups[feature].append(symbols)
            collisions = [feature for feature, supports in groups.items() if not frozenset.intersection(*supports)]
            reason = 'identical_features_incompatible_supports' if collisions else 'partition_limit'
            causes[reason] += 1
            if len(witnesses) < 4:
                witnesses.append({'key': key, 'reason': reason, 'examples': len(model.examples[key]),
                                  'colliding_feature_groups': len(collisions)})
        for row in records:
            before, after = (Frame.from_dict(row[k]) for k in ('before', 'after'))
            fitted.update(score(model.predict(before, Action.from_dict(row['action']), True), after))
        report['arms'][arm] = dict(prequential=pre, changed_prequential=changed, hindsight_fit=fitted,
                                   unresolved_causes=causes, witnesses=witnesses, curve=curve)
    assert source.read_bytes() == raw
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True)
    print(json.dumps({arm: {k:v for k,v in data.items() if k not in ('curve','witnesses')}
                      for arm,data in report['arms'].items()}))


def bounded_probe(output, pooled=False):
    """Exposed DEV gate: zero errors AND retain >=95% fixed-rich correct singletons.

Single chronological run, predict then ingest. No source-transfer or fresh-task
claim. CPU includes repeated range computations. A fail ends this candidate,
not license to tune a percentile on this corpus.
"""
    from scripts.developmental_bounded_context import BoundedContext
    source = ROOT/'evidence/developmental-fk-schema-tasks.json'
    raw = source.read_bytes()
    if pooled:
        from scripts.developmental_pooled_context import learner
    candidate = 'pooled' if pooled else 'bounded'
    models = {'rich':Model([],numeric_context=context),
              candidate:learner() if pooled else BoundedContext([],numeric_context=context)}
    totals = {a:Counter() for a in models}
    cpu = Counter()
    curves = []
    for ordinal,row in enumerate(json.loads(raw)['training']):
        before,after = (Frame.from_dict(row[k]) for k in ('before','after'))
        action = Action.from_dict(row['action'])
        scores = {}
        for arm,model in models.items():
            start=time.process_time()
            prediction=model.predict(before,action,True)
            scores[arm]=score(prediction,after)
            totals[arm].update(scores[arm])
            model.learn([row])
            cpu[arm]+=time.process_time()-start
        curves.append(dict(ordinal=ordinal,scores=scores))
    passed=((totals[candidate]['wrong']<=totals['rich']['wrong'] and
             totals[candidate]['correct_singleton']>totals['rich']['correct_singleton']) if pooled else
            (totals[candidate]['wrong']==0 and
             totals[candidate]['correct_singleton']>=.95*totals['rich']['correct_singleton']))
    scope=('Exposed DEV pooled conditions: strictly more correct singletons, no more errors than rich; '
           'unchanged single-predicate learner. No fresh capability or source transfer.' if pooled else bounded_probe.__doc__)
    report=dict(scope=scope,totals=totals,cpu_seconds=cpu,curve=curves,
                verdict='DEV_PASS' if passed else 'NO_GO',
                source_sha256=hashlib.sha256(raw).hexdigest())
    assert source.read_bytes()==raw
    with output.open('x') as stream: json.dump(report,stream,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k not in ('scope','curve')}))


if __name__ == '__main__':
    (lambda p: bounded_probe(p, True) if '--pooled' in sys.argv else
     bounded_probe(p) if '--bounded' in sys.argv else
     (disagreement_audit if '--disagreement' in sys.argv else
      switching_probe if '--switching' in sys.argv else run)(p))(Path(sys.argv[1]))
