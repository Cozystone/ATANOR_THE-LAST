"""The person ATANOR lives with (training/evaluation helper, never imported by agent/).

Answers only when asked; every answer is counted. Knows what each command means (tool, extension, destination)
because the person gave the command. Questions it answers:
  explain(word)          -> a paraphrase in other words, '' if the word carries no meaning, None if it has none
  point(command)         -> the objects meant and the destination name
  demonstrate(cmd, o, D) -> the steps it would do for one object (ATANOR performs them itself in its lab)
  demonstrate_goal(goal) -> the steps for the whole goal (last resort when experiments did not help)
  check(proposal)        -> whether a proposed interpretation (change, objects, destination) is what was meant
  confirm(command)       -> whether the workspace now is what was asked
"""
from collections import Counter

EXPLAIN = {
    'please': '',
    'kindly': '',
    'transfer': 'move',
    'relocate': 'move',
    'shift': 'move',
    'duplicate': 'make a copy',
    'clone': 'make a copy',
    'erase': 'delete',
    'remove': 'delete',
    'discard': 'delete',
    'logs': 'log files',
    'spreadsheets': 'csv files',
    'notes': 'md files',
}


class Teacher:
    def __init__(self, home):
        self.home = home
        self.task = None
        self.help = Counter()

    def begin(self, task):
        self.task = task
        files = [p for p in self.home.existing() if '/' not in p and self.home.kind(p) == 'file']
        self.before = {p: self.home.attrs(p)['hash'] for p in files}
        self.truth = sorted(p for p in files if task['ext'] == 'any' or p.endswith('.' + task['ext']))

    def explain(self, word):
        """A person answers from what they meant: a word of the verb phrase -> the plain verb; a word naming the
        files -> '<ext> files'; a word that only introduces the folder or is polite -> '' (changes nothing)."""
        self.help['explain'] += 1
        ph = self.task.get('phrases')
        if not ph:
            return EXPLAIN.get(word)
        if word in ph['verb'] and word != ph['base']:
            return ph['base']
        if word in ph['selector_synonym']:
            return f"{self.task['ext']} files"
        if word in ph['function']:
            return ''
        return None

    def point(self, command):
        self.help['point'] += 1
        return {'objects': list(self.truth), 'dest': self.task['dest']}

    def _steps(self, objs):
        t, d = self.task['tool'], self.task['dest']
        out = [('mkdir', (d,))] if t in ('move', 'copy') else []
        drift = getattr(self.home, 'drift', ())
        for o in objs:                                         # the person knows how the world works now
            if t == 'copy' and 'copy_retired' in drift:
                out.append(('replicate', (f'{d}/{o}', o)))
            elif t == 'move' and 'move_retired' in drift:
                out.append(('shove', (f'{d}/{o}', o)))
            elif t == 'delete' and 'delete_retired' in drift:
                out.append(('zap', (o,)))
            else:
                out.append((t, (o, f'{d}/{o}')) if t in ('move', 'copy') else (t, (o,)))
        return out

    def demonstrate(self, command, o, dest):
        self.help['demonstrate'] += 1
        return self._steps([o])

    def demonstrate_goal(self, goal):
        self.help['demonstrate_goal'] += 1
        return self._steps(self.truth)

    def check(self, proposal):
        """'Is this what you mean?' about a concrete proposal: the change, the objects and the destination."""
        self.help['check'] += 1
        ch = {(it[0], it[1], it[2]) for it in proposal['change'] if len(it) == 3}
        gone = ('o', 'kind', 'absent') in ch
        arrives = any(r == 'D/o' and k == 'kind' for r, k, _ in ch)
        tool = 'move' if gone and arrives else 'copy' if arrives else 'delete' if gone else None   # judged by what changes kind
        return tool == self.task['tool'] and sorted(proposal['objects']) == self.truth and (proposal['dest'] or None) == self.task['dest']

    def confirm(self, command):
        self.help['confirm'] += 1
        return self.judge()

    def judge(self):
        t, d = self.task['tool'], self.task['dest']
        ok = True
        for p, h in self.before.items():
            st = self.home.attrs(p)
            if p not in self.truth:
                ok &= st['kind'] == 'file' and st['hash'] == h
                continue
            if t in ('move', 'copy'):
                q = self.home.attrs(f'{d}/{p}')
                ok &= q['kind'] == 'file' and q['hash'] == h
            ok &= (st['kind'] == 'file' and st['hash'] == h) if t == 'copy' else st['kind'] == 'absent'
        return bool(ok)


class ViewTeacher(Teacher):
    """The person using the screen body. Knows the command's meaning: a panel, a tool, and the value object it takes
    (filter/sort/group: 'ext:csv', 'key:size', 'grp:ext'; compare: the source panel; open/close: none)."""
    ATTR = {'filter': 'filter', 'sort': 'sort', 'group': 'group'}

    def begin(self, task):
        self.task = task
        self.before = self.home._read()
        self.truth = [task['panel']]

    def point(self, command):
        self.help['point'] += 1
        return {'objects': list(self.truth), 'dest': self.task.get('value')}

    def explain(self, word):
        """A verb word -> the plain verb; a value synonym -> the value's own word; a function word -> '' (nothing)."""
        self.help['explain'] += 1
        ph = self.task.get('phrases')
        if not ph:
            return None
        if word in ph['verb'] and word != ph['base']:
            return ph['base']
        if word in ph['selector_synonym'] and self.task.get('value'):
            return self.task['value'].split(':', 1)[1]
        if word in ph['function']:
            return ''
        return None

    def _steps(self, objs):
        t, v = self.task['tool'], self.task.get('value')
        drift = getattr(self.home, 'drift', ())
        if t == 'filter' and 'filter_retired' in drift:
            return [('sift', (v, o)) for o in objs]          # the person knows how the screen works now
        if t == 'sort' and 'sort_retired' in drift:
            return [('rank', (v, o)) for o in objs]
        return [(t, (o, v)) if v else (t, (o,)) for o in objs]

    def check(self, proposal):
        self.help['check'] += 1
        ch = {(it[0], it[1]): it[2] for it in proposal['change'] if len(it) == 3}
        t = self.task['tool']
        want = {'open': ('kind', 'panel'), 'close': ('kind', 'absent')}
        if t in want:
            ok_change = ch.get(('o', 'kind')) == want[t][1]
        elif t in self.ATTR:
            ok_change = ('o', self.ATTR[t]) in ch and ch.get(('o', 'kind')) == 'panel'
        else:
            ok_change = ch.get(('o', 'kind')) == 'compare'
        return ok_change and sorted(proposal['objects']) == self.truth and (proposal['dest'] or None) == (self.task.get('value') or None)

    def judge(self):
        spec = self.home._read()
        t, p, v = self.task['tool'], self.task['panel'], self.task.get('value')
        cur = ViewWorkspace.attrs_of(spec, p)
        if t == 'open':
            ok = cur['kind'] == 'panel'
        elif t == 'close':
            ok = cur['kind'] == 'absent'
        elif t in self.ATTR:
            ok = cur['kind'] == 'panel' and cur[self.ATTR[t]] == v.split(':', 1)[1]
        else:
            src = ViewWorkspace.attrs_of(self.before, v)
            ok = cur['kind'] == 'compare' and cur['filter'] == src['filter'] and cur['sort'] == src['sort']
        for q in self.before:                                   # every other panel is as it was
            if q != p and ViewWorkspace.attrs_of(spec, q) != ViewWorkspace.attrs_of(self.before, q):
                ok = False
        return bool(ok)


from ..world.view_world import ViewWorkspace  # noqa: E402  (after the class: the module is evaluator-side only)
