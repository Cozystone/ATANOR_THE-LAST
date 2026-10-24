"""Exposed causal diagnostic: remove one observed relation channel per arm.

No channel is preselected as irrelevant. No evaluation transition is training.
Native cloned starting bodies are researcher probes, NOT autonomous acquisition.
"""
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.developmental_conditional_eval import Model
from scripts.developmental_continual_probe import score
from scripts.developmental_rooted_probe import rooted
from scripts.representation_r3_dev import configuration
from scripts.developmental_active_eval import event
from packages.action_core.world import Sandbox, Frame, Action


def without_channel(name):
    return lambda key: key[:-1] + (tuple(row for row in key[-1] if row[0] != name),)


def run(source, output):
    raw = source.read_bytes()
    report = json.loads(raw)
    output.mkdir(exist_ok=False)
    total, retention, rows = {}, {}, []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='atanor_ablation_') as root:
        for life in (r for r in report['lives'] if r['arm'] == 'active'):
            training = life['bootstrap'] + life['acquisition']
            frame = Frame.from_dict(training[0]['before'])
            action = Action.from_dict(training[0]['action'])
            key, _ = rooted(frame,action,'kind',(0,))
            models = {'full': Model(training)}
            models.update({f'drop:{name}':Model(training,key_transform=without_channel(name)) for name,_ in key[-1]})
            for label, model in models.items():
                retained = retention.setdefault(label, Counter())
                for record in training:
                    before, after = (Frame.from_dict(record[k]) for k in ('before','after'))
                    retained.update(score(model.predict(before,Action.from_dict(record['action']),True),after))
            for task in (2,3):
                cfg, _, reference, payload = configuration(3+task%2,97001+20*life['life']+task)
                template = Sandbox(Path(root)/f"template{life['life']}_{task}",**cfg)
                for ordinal, action in enumerate(template.actions()):
                    if time.monotonic()-started>120:
                        raise TimeoutError('diagnostic cap120s')
                    body = Sandbox(Path(root)/f"query{life['life']}_{task}_{ordinal}",**cfg)
                    before = body.observe()
                    predictions = {label:model.predict(before,action,True) for label,model in models.items()}
                    record = event(body,action)
                    assert body._paths[reference].read_bytes() == payload
                    after = Frame.from_dict(record['after'])
                    counts = {label:score(prediction,after) for label,prediction in predictions.items()}
                    for label, measured in counts.items():
                        total.setdefault(label,Counter()).update(measured)
                    rows.append({'life':life['life'],'task':task,'record':record,'counts':counts})
    assert source.read_bytes() == raw
    result = {'source_sha256':hashlib.sha256(raw).hexdigest(),'totals':total,'retention':retention,
              'native_transitions':len(rows),'rows':rows,
              'scope':'exposed diagnostic; all full-state cells; no task-capability or concept-discovery claim'}
    with (output/'report.json').open('x') as stream:
        json.dump(result,stream,separators=(',',':'),sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__ == '__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]))
