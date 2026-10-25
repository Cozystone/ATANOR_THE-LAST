"""Screen-body world change: a tool stops working and a new one with an opaque name (reversed arguments) appears."""
import pathlib, sys
root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('.')
def patch(rel, pairs):
    p = root / rel; s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:60]}'; s = s.replace(old, new, 1)
    p.write_bytes(s.encode('utf-8'))
patch('atanor_os/world/view_world.py', [
    ("""    def tools(self):
        return dict(TOOLS)""", """    def tools(self):
        t = dict(TOOLS)
        if 'filter_retired' in self.drift:
            t['sift'] = 2
        if 'sort_retired' in self.drift:
            t['rank'] = 2
        return t

    def _sift(self, spec, v, p):
        \"\"\"Changed world only: filters, value first.\"\"\"
        if 'filter_retired' not in self.drift or spec.get(p, {}).get('kind') != 'panel' or not v.startswith('ext:'):
            return False
        spec[p]['filter'] = v[4:]
        return True

    def _rank(self, spec, k, p):
        \"\"\"Changed world only: sorts, key first.\"\"\"
        if 'sort_retired' not in self.drift or p not in spec or not k.startswith('key:'):
            return False
        spec[p]['sort'] = k[4:]
        return True"""),
    ("""        if tool not in TOOLS or len(args) != TOOLS[tool] or len(set(args)) != len(args):
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)""", """        tools = self.tools()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)"""),
    ("""    @staticmethod
    def actions(universe):
        out = []
        for tool, ar in TOOLS.items():""", """    def actions(self_or_universe, universe=None):
        tools = self_or_universe.tools() if universe is not None else TOOLS
        universe = self_or_universe if universe is None else universe
        out = []
        for tool, ar in tools.items():"""),
    ("""    @staticmethod
    def _filter(spec, p, v):
        if spec.get(p, {}).get('kind') != 'panel' or not v.startswith('ext:'):
            return False""", """    def _filter(self, spec, p, v):
        if 'filter_retired' in self.drift or spec.get(p, {}).get('kind') != 'panel' or not v.startswith('ext:'):
            return False"""),
    ("""    @staticmethod
    def _sort(spec, p, k):
        if p not in spec or not k.startswith('key:'):
            return False""", """    def _sort(self, spec, p, k):
        if 'sort_retired' in self.drift or p not in spec or not k.startswith('key:'):
            return False"""),
])
patch('atanor_os/teach/life_teacher.py', [
    ("""    def _steps(self, objs):
        t, v = self.task['tool'], self.task.get('value')
        return [(t, (o, v)) if v else (t, (o,)) for o in objs]""", """    def _steps(self, objs):
        t, v = self.task['tool'], self.task.get('value')
        drift = getattr(self.home, 'drift', ())
        if t == 'filter' and 'filter_retired' in drift:
            return [('sift', (v, o)) for o in objs]          # the person knows how the screen works now
        if t == 'sort' and 'sort_retired' in drift:
            return [('rank', (v, o)) for o in objs]
        return [(t, (o, v)) if v else (t, (o,)) for o in objs]"""),
])
patch('atanor_os/eval/life_gen_view.py', [
    ("""def life(seed, days=30):
    rng = random.Random(f'viewlife-{seed}')
    out = []
    for day in range(1, days + 1):
        user = day <= 2 or day % 4 != 0""", """CHANGES = ['filter_retired', 'sort_retired']


def life(seed, days=30, drift=True):
    rng = random.Random(f'viewlife-{seed}')
    change_days = sorted(rng.sample(range(8, days), 2)) if drift and days > 10 else []
    changes = rng.sample(CHANGES, 2)
    out, cur = [], []
    for day in range(1, days + 1):
        if day in change_days:
            cur = cur + [changes[change_days.index(day)]]
        user = day <= 2 or day % 4 != 0"""),
    ("""        out.append({'day': day, 'user': user, 'drift': [], 'tasks': tasks})""", """        out.append({'day': day, 'user': user, 'drift': list(cur), 'tasks': tasks})"""),
    ("""    home = ViewWorkspace(root / 'view', data, spec=json.loads(json.dumps(START)))        # the screen restarts each morning""",
     """    home = ViewWorkspace(root / 'view', data, spec=json.loads(json.dumps(START)))        # the screen restarts each morning
    home.drift = frozenset(day['drift'])"""),
    ("""            rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': [],
                         'success': False, 'outcome': 'infeasible',""", """            rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                         'success': False, 'outcome': 'infeasible',"""),
    ("""        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': [],
                     'success': ok,""", """        rows.append({'day': day_no, 'task': k, 'command': task['command'], 'tool': task['tool'], 'user': day['user'], 'drift': day['drift'],
                     'success': ok,"""),
])
print('view drift ok')
