import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:80]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/world/fs_world.py', [
    ("""class Workspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
""", """class Workspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # P8b: changed world rules, e.g. {'move_dirs'}; empty = the original world
"""),
    ("""    def _move(self, s, d):
        if not s.is_file() or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
""", """    def _move(self, s, d):
        movable = s.is_file() or ('move_dirs' in self.drift and s.is_dir() and not s.is_symlink())
        if not movable or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
"""),
])

patch('atanor_os/world/view_world.py', [
    ("""class ViewWorkspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
""", """class ViewWorkspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # P8b: changed world rules, e.g. {'group_filtered'}; empty = the original world
"""),
    ("""        ok = getattr(self, '_' + tool)(spec, *args)""",
     """        ok = self._group(spec, *args, drift=self.drift) if tool == 'group' else getattr(self, '_' + tool)(spec, *args)"""),
    ("""    def _group(spec, p, g):
        if spec.get(p, {}).get('kind') != 'panel' or not g.startswith('grp:'):
            return False
        if g != 'grp:none' and spec[p]['filter'] != 'all':      # grouping by ext needs the unfiltered list
            return False
""", """    def _group(spec, p, g, drift=frozenset()):
        if spec.get(p, {}).get('kind') != 'panel' or not g.startswith('grp:'):
            return False
        if g != 'grp:none' and spec[p]['filter'] != 'all' and 'group_filtered' not in drift:   # original world: needs the unfiltered list
            return False
"""),
])
print('ok')
