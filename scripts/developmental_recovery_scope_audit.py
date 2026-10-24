"""Native actuator-scope diagnosis, not learner capability or bounded-search proof.

Reconstruct an EXPOSED missing-parent fixture from the previous native protocol.
Execute every permitted first action on an independent temporary clone. The
unbounded obstruction is separately justified by the implementation: this schema
contains no directory creator, all initial objects are files, and no action may
address the missing ancestor. The first-action sweep alone is not that proof.
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Sandbox
from packages.action_core.observation_scope import observe_ancestors
from scripts.representation_r3_dev import configuration


def run(output):
    cfg, aliases, _, _ = configuration(6, 144002, 'detached_absent')
    cfg['operations'] = cfg['operations'] + [{'id': 'rename', 'arity': 2}]
    cfg['paths'] = list(cfg['paths'])
    cfg['paths'][int(aliases[0][1:])] = 'envelope/' + cfg['paths'][int(aliases[0][1:])]
    cfg['context_initial'] = {}
    rows = []
    with tempfile.TemporaryDirectory(prefix='atanor_recovery_scope_') as temp:
        root = Path(temp)
        template = Sandbox(root/'template', **cfg)
        before = template.observe()
        sensed, added = observe_ancestors(template, [aliases[0]], max_new=1)
        actions = template.actions()
        for i, action in enumerate(actions):
            body = Sandbox(root/str(i), **cfg)
            ok = body.step(action)
            rows.append(dict(action=action.to_dict(), native_ok=ok,
                             missing_ancestor_created=(body.root/'envelope').exists(),
                             target_exists=body._paths[aliases[0]].exists()))
        report = dict(scope=__doc__, capability_claim=False,
            before=before.to_dict(), sensor_frame=sensed.to_dict(), added_handles=list(added),
            operation_schema=cfg['operations'], permitted_action_count=len(actions),
            sensor_handles_actionable=any(h in a.args for h in added for a in actions),
            ancestor_created_count=sum(r['missing_ancestor_created'] for r in rows),
            target_created_count=sum(r['target_exists'] for r in rows), rows=rows,
            invariant_argument=(
                'Initially no directory below root. empty/copy create only files and require an existing '
                'parent; unlink removes a file; rename moves an existing file and requires an existing '
                'parent. Fixed schema excludes mkdir; fixed handle scope excludes envelope. Therefore '
                'no sequence can create envelope or the required child, with no external mutation.'),
            verdict='UNREACHABLE_UNDER_EXISTING_ACTUATOR_SCOPE',
            source_sha256={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
                ('packages/action_core/world.py', 'scripts/representation_r3_dev.py',
                 'scripts/representation_r1_dev.py', 'packages/action_core/observation_scope.py')})
    with output.open('x') as stream:
        json.dump(report, stream, sort_keys=True)
    print(json.dumps({k: v for k, v in report.items() if k not in
                     ('rows', 'scope', 'before', 'sensor_frame', 'source_sha256', 'invariant_argument')}))


if __name__ == '__main__':
    run(Path(sys.argv[1]))
