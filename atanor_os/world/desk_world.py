"""Fourth body: a desk (a local office sandbox; DESK_BODY.md). Items of four apps (messages, drafts, tasks, notes)
live in one JSON state inside a sandbox folder; places, tags and nothing else are value objects tools take as second
arguments. Structurally new against the other bodies: some effects arrive later (a sent draft is only queued; a later
tick makes it sent or failed and may bring a reply), the outside world changes items between ticks (new messages,
items locked or unlocked, tasks blocked), a command over several items may partly fail, and purge is irreversible
(behind a capability, sandbox only). Every action and every outside change is written to world_log.jsonl, and outside
changes are drawn from (seed, tick number), so a run can be replayed.

Objects: item ids (opaque, e.g. 'i3k1'), place objects ('f.inbox' ...), tag objects ('t.red' ...). Every object has the
same five attributes: kind, place, status, tag, value. Tool preconditions are enforced here and not exported.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import time
from pathlib import Path

PLACES = ('inbox', 'archive', 'outbox', 'tasks', 'notes')
TAGS = ('red', 'blue', 'green')
VALUE_OBJECTS = tuple([f'f.{p}' for p in PLACES] + [f't.{t}' for t in TAGS])
TOOLS = {'read': 1, 'file': 2, 'tag': 2, 'send': 1, 'complete': 1, 'pin': 1, 'purge': 1}
CAPABILITY = {'purge': 'destroy_items'}
BLANK = {'kind': 'absent', 'place': '-', 'status': '-', 'tag': '-', 'value': '-'}
HOME = {'message': 'inbox', 'draft': 'outbox', 'task': 'tasks', 'note': 'notes'}
FILEABLE = {'message': ('inbox', 'archive'), 'note': ('notes', 'archive'), 'task': ('tasks', 'archive')}


class DeskWorkspace:
    BODY = 'desk'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # changed world rules: {'file_retired', 'tag_retired'}

    def __init__(self, root, create=True, seed=0):
        self.root = Path(root).absolute()
        self.path = self.root / 'desk.json'
        if create:
            self.root.mkdir(parents=True, exist_ok=False)
            self._write({'items': {}, 'seed': seed, 'tick': 0})

    def _read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def _write(self, spec):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(spec, indent=1, sort_keys=True), encoding='utf-8')
        tmp.replace(self.path)

    def _log(self, **row):
        with open(self.root / 'world_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, sort_keys=True) + '\n')

    # ------------------------------------------------------------ the world on its own
    def add_items(self, items):
        """New items arrive: {id: {'kind': ..., 'tag': ..., optional 'status'}} (they start in their app's place)."""
        spec = self._read()
        for iid, it in items.items():
            k = it['kind']
            status = it.get('status') or {'message': 'unread', 'draft': 'draft', 'task': 'open', 'note': 'plain'}[k]
            spec['items'][iid] = {'kind': k, 'place': it.get('place', HOME[k]), 'status': status, 'tag': it.get('tag', 'none'),
                                  'locked': False, 'blocked': False}
        self._write(spec)
        self._log(event='arrive', actor='outside', items={iid: spec['items'][iid] for iid in sorted(items)}, after=self.fingerprint())

    def tick(self):
        """Time passes: queued drafts are sent (or fail), some sent drafts bring a reply, and the outside world locks or
        unlocks some messages and blocks or unblocks some tasks. Drawn from (seed, tick), so it replays."""
        spec = self._read()
        spec['tick'] += 1
        rng = random.Random(f"desk-{spec['seed']}-tick-{spec['tick']}")
        changes = []
        for iid in sorted(spec['items']):
            it = spec['items'][iid]
            if it['kind'] == 'draft' and it['status'] == 'queued':
                it['status'] = 'sent' if rng.random() < 0.85 else 'failed'
                changes.append((iid, it['status']))
                if it['status'] == 'sent' and rng.random() < 0.5:
                    rid = f"r{spec['tick']}{iid}"
                    spec['items'][rid] = {'kind': 'message', 'place': 'inbox', 'status': 'unread', 'tag': it['tag'], 'locked': False, 'blocked': False}
                    changes.append((rid, 'reply'))
            elif it['kind'] == 'message' and rng.random() < 0.08:
                it['locked'] = not it['locked']
                changes.append((iid, 'locked' if it['locked'] else 'unlocked'))
            elif it['kind'] == 'task' and it['status'] == 'open' and rng.random() < 0.08:
                it['blocked'] = not it['blocked']
                changes.append((iid, 'blocked' if it['blocked'] else 'unblocked'))
        self._write(spec)
        self._log(event='tick', actor='outside', tick=spec['tick'], changes=changes, after=self.fingerprint())
        return changes

    # ------------------------------------------------------------ observation
    @staticmethod
    def attrs_of(spec, obj):
        if obj.startswith('f.') and obj[2:] in PLACES:
            return {'kind': 'place', 'place': '-', 'status': '-', 'tag': '-', 'value': obj[2:]}
        if obj.startswith('t.') and obj[2:] in TAGS:
            return {'kind': 'tag', 'place': '-', 'status': '-', 'tag': '-', 'value': obj[2:]}
        it = spec['items'].get(obj)
        if it is None:
            return dict(BLANK)
        status = 'locked' if it.get('locked') else ('blocked' if it.get('blocked') else it['status'])
        return {'kind': it['kind'], 'place': it['place'], 'status': status, 'tag': it['tag'], 'value': '-'}

    def tools(self):
        t = dict(TOOLS)
        if 'file_retired' in self.drift:
            t['shelve'] = 2
        if 'tag_retired' in self.drift:
            t['mark'] = 2
        return t

    def existing(self):
        return sorted(set(self._read()['items']) | set(VALUE_OBJECTS))

    def universe(self, paths=()):
        return sorted(set(self._read()['items']) | set(VALUE_OBJECTS) | set(paths))

    def observe(self, paths=()):
        spec = self._read()
        return {o: self.attrs_of(spec, o) for o in self.universe(paths)}

    def kind(self, obj):
        return self.attrs_of(self._read(), obj)['kind']

    def lab_copy(self, root, objs=(), seen=None):
        """A fresh desk with the same state; the lab never ticks (no outside changes there) and logs to its own folder."""
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = DeskWorkspace(root, create=True)
        lab._write(self._read())
        lab.drift = self.drift
        return lab

    def actions(self_or_universe, universe=None):
        tools = self_or_universe.tools() if universe is not None else TOOLS
        universe = self_or_universe if universe is None else universe
        out = []
        for tool, ar in tools.items():
            out += [(tool, (a,)) for a in universe] if ar == 1 else [(tool, (a, b)) for a in universe for b in universe if a != b]
        return out

    # ------------------------------------------------------------ action
    def fingerprint(self):
        """A short hash of the whole state (for the log: which state an action met and left)."""
        return hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]

    def execute(self, tool, args, capabilities, actor='learner'):
        """actor is for the log only: 'learner' (default), 'teacher', 'person', 'evaluator'."""
        t0 = time.perf_counter()
        tools = self.tools()
        before = self.fingerprint()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            self._log(event='invalid', actor=actor, tool=tool, args=list(args), before=before)
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            self._log(event='act', actor=actor, tool=tool, args=list(args), ok=False, error='blocked', before=before, after=before)
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        spec = self._read()
        it = spec['items'].get(args[0])
        if tool == 'send' and it and it['kind'] == 'draft' and it['status'] in ('queued', 'sent'):
            # the desk's own check right before sending (GENERATION_1_CLOSEOUT.md): a draft already on its way is not
            # sent again; nothing changes, and the attempt is logged apart from real sends
            self._log(event='duplicate_prevented', actor=actor, tool=tool, args=list(args), status=it['status'], before=before)
            return {'ok': True, 'noop': True, 'blocked': False, 'error': '', 'ms': (time.perf_counter() - t0) * 1000}
        ok = getattr(self, '_tool_' + tool)(spec, *args)
        if ok:
            self._write(spec)
        self._log(event='act', actor=actor, tool=tool, args=list(args), ok=bool(ok), before=before, after=self.fingerprint())
        return {'ok': bool(ok), 'blocked': False, 'error': '' if ok else 'precondition', 'ms': (time.perf_counter() - t0) * 1000}

    @staticmethod
    def _item(spec, x):
        return spec['items'].get(x)

    def _move(self, spec, x, f):
        it = self._item(spec, x)
        if it is None or not f.startswith('f.') or it.get('locked') or f[2:] not in FILEABLE.get(it['kind'], ()):
            return False
        it['place'] = f[2:]
        return True

    def _tool_file(self, spec, x, f):
        return 'file_retired' not in self.drift and self._move(spec, x, f)

    def _tool_shelve(self, spec, f, x):
        """Changed world only: the place first."""
        return 'file_retired' in self.drift and self._move(spec, x, f)

    def _set_tag(self, spec, x, t):
        it = self._item(spec, x)
        if it is None or not t.startswith('t.') or t[2:] not in TAGS:
            return False
        it['tag'] = t[2:]
        return True

    def _tool_tag(self, spec, x, t):
        return 'tag_retired' not in self.drift and self._set_tag(spec, x, t)

    def _tool_mark(self, spec, t, x):
        """Changed world only: the tag first."""
        return 'tag_retired' in self.drift and self._set_tag(spec, x, t)

    def _tool_read(self, spec, x):
        it = self._item(spec, x)
        if it is None or it['kind'] != 'message' or it.get('locked') or it['status'] != 'unread':
            return False
        it['status'] = 'read'
        return True

    def _tool_send(self, spec, x):
        it = self._item(spec, x)
        if it is None or it['kind'] != 'draft' or it['status'] != 'draft':
            return False
        it['status'] = 'queued'                            # the outcome comes later (tick)
        return True

    def _tool_complete(self, spec, x):
        it = self._item(spec, x)
        if it is None or it['kind'] != 'task' or it.get('blocked') or it['status'] != 'open':
            return False
        it['status'] = 'done'
        return True

    def _tool_pin(self, spec, x):
        it = self._item(spec, x)
        if it is None or it['kind'] != 'note' or it['status'] != 'plain':
            return False
        it['status'] = 'pinned'
        return True

    def _tool_purge(self, spec, x):
        if x not in spec['items']:
            return False
        del spec['items'][x]
        return True

