import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
assert s.count("any(it[0] != 'o' for it in self.patterns[r['pid']])") == 4
s = s.replace("any(it[0] != 'o' for it in self.patterns[r['pid']])", "self._needs_dest(r['pid'])")
old = "    def _proposal(self, r):"
new = '''    def _needs_dest(self, pid):
        """A change needs a second object when an entry is about it or copies a value from it."""
        return any(it[0] != 'o' or (isinstance(it[2], str) and it[2].startswith('=D.')) for it in self.patterns.get(pid, []))

    def _remembered_kind(self, p):
        """The kind an object last had when it was present: in the home now, or in memory."""
        k = self.home.kind(p) if hasattr(self.home, 'kind') else None
        if k and k != 'absent':
            return k
        for e in reversed(self.episodes):
            for st in (e.post, e.pre):
                ob = st.get(p)
                if ob and ob.get('kind') not in (None, 'absent'):
                    return ob['kind']
        return None

    def _proposal(self, r):'''
assert old in s; s = s.replace(old, new, 1)
old = "        seen = {p: 'file' for p in objs}"
new = "        seen = {p: k for p in objs for k in [self._remembered_kind(p)] if k}"
assert old in s; s = s.replace(old, new, 1)
p.write_bytes(s.encode('utf-8')); print('fixed', p)
