"""Exposed chronological audit, not a policy rerun or held-out capability test.

Compare frozen and prefix-updated hypotheses on the SAME already selected native
actions. Predict before ingesting each result; report selection bias explicitly.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_task_eval import Adapter
from scripts.developmental_continual_probe import score
from scripts.developmental_rooted_probe import rooted
from packages.action_core.world import Frame, Action


def run(source, output, families=False):
    if output.exists(): raise FileExistsError(output)
    db = sqlite3.connect('file:' + source.resolve().as_posix() + '?mode=ro&immutable=1', uri=True)
    try:
        events = [(kind, json.loads(text)) for kind, text in db.execute(
            'SELECT kind,payload FROM events ORDER BY seq')]
    finally: db.close()
    old = []
    for name in ('developmental-continual.json', 'developmental-online-eval.json'):
        old += json.loads((ROOT / 'evidence' / name).read_text())['records']
    if families:
        old += [json.loads((ROOT/'evidence/developmental-composition-probe.json').read_text())['rows'][0]['native_record']]
        old += [r['record'] for r in json.loads((ROOT/'evidence/developmental-rewrite-scope.json').read_text())['rows']
                if r['case'] in ('declared_absent', 'declared_present')]
    models = {name: Adapter(old) for name in ('frozen', 'online')}
    if families:
        from scripts.developmental_effect_families import EffectFamilies
        for model in models.values(): model.model = EffectFamilies(old)
    totals = {name: Counter() for name in models}; rows = []
    for kind, event in events:
        if kind in ('BEGIN', 'OBSERVE'):
            frame = Frame.from_dict(event['frame'])
        elif kind == 'PREDICT':
            action = Action.from_dict(event['action']); before = frame
            predictions = {name: model.predict_cells(before, action) for name, model in models.items()}
        elif kind == 'RESULT':
            frame = Frame.from_dict(event['frame']); row = dict(action=action.to_dict(), scores={}, unknown_causes={})
            for name, model in models.items():
                row['scores'][name] = dict(score(predictions[name], frame))
                totals[name].update(row['scores'][name]); causes = Counter()
                for field, address, values in predictions[name]:
                    if values: continue
                    key, _ = rooted(before, action, field, address)
                    if families:
                        # Combined support must not be attributed to only one language.
                        causes['no_combined_proposal'] += 1
                    else:
                        support = model.model.rules.get(key)
                        causes['unseen_context' if support is None else 'exhausted_support'] += 1
                row['unknown_causes'][name] = dict(causes)
            models['online'].model.learn([dict(before=before.to_dict(), action=action.to_dict(), after=frame.to_dict())])
            rows.append(row)
    result = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        selected_actions=len(rows), selection_bias=True, families=families,
        training_count=len(old), totals=totals, rows=rows)
    with output.open('x') as stream: json.dump(result, stream, sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}))


if __name__ == '__main__': run(Path(sys.argv[1]), Path(sys.argv[2]), '--families' in sys.argv[3:])
