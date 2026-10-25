import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
old = "        self.body = getattr(home, 'BODY', 'fs')"
new = "        self.body = getattr(home, 'BODY', 'fs')\n        self.caps = {c: True for c in set(getattr(home, 'CAPABILITY', {}).values())}   # the person's command grants the body's capabilities"
assert old in s; s = s.replace(old, new, 1)
n = s.count("{'destroy': True}")
s = s.replace("        g = Goal('life:' + interp['pid'], must, keep, {'destroy': True}, dict(BUDGET), sorted(universe))",
              "        g = Goal('life:' + interp['pid'], must, keep, dict(self.caps), dict(BUDGET), sorted(universe))")
s = s.replace("        res = ws.execute(tool, tuple(args), caps or {'destroy': True})", "        res = ws.execute(tool, tuple(args), caps or self.caps)")
assert "{'destroy': True}" not in s, s.count("{'destroy': True}")
p.write_bytes(s.encode('utf-8')); print('caps generalized', n)
