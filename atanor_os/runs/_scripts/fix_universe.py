import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
old = """        universe |= set(interp['selected'])
        g = Goal('life:' + interp['pid'], must, keep, {'destroy': True}, dict(BUDGET), sorted(universe))"""
new = """        universe |= set(interp['selected'])
        if interp['dest'] and self._needs_dest(interp['pid']):
            universe.add(interp['dest'])                      # the second object belongs to the goal even if only its value is copied
        g = Goal('life:' + interp['pid'], must, keep, {'destroy': True}, dict(BUDGET), sorted(universe))"""
assert old in s, 'universe anchor'; p.write_bytes(s.replace(old, new, 1).encode('utf-8')); print('universe fixed')
