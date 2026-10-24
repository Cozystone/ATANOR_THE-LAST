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
        self.help['explain'] += 1
        return EXPLAIN.get(word)

    def point(self, command):
        self.help['point'] += 1
        return {'objects': list(self.truth), 'dest': self.task['dest']}

    def _steps(self, objs):
        t, d = self.task['tool'], self.task['dest']
        out = [('mkdir', (d,))] if t in ('move', 'copy') else []
        retired = t == 'copy' and 'copy_retired' in getattr(self.home, 'drift', ())
        for o in objs:
            if retired:
                out.append(('replicate', (f'{d}/{o}', o)))        # the person knows how the world works now
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
        rels = {(it[0], it[1]) for it in proposal['change'] if len(it) == 3}
        tool = 'move' if ('o', 'kind') in rels and ('D/o', 'kind') in rels else 'copy' if ('D/o', 'kind') in rels else 'delete' if rels == {('o', 'kind')} else None
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
