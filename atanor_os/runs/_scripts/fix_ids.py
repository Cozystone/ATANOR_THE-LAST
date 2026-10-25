import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
n1 = s.count("t in values or t == dest")
s = s.replace("t in values or t == dest", "t in values or t in view or t == dest")
old = "and toks[i] not in values and toks[i + 1] not in values:"
assert old in s; s = s.replace(old, "and toks[i] not in values and toks[i + 1] not in values and toks[i] not in view and toks[i + 1] not in view:")
old = "        unknown = [t for t in toks if self.word_n[t] == 0 and t != dest and t not in values]"
assert old in s; s = s.replace(old, "        unknown = [t for t in toks if self.word_n[t] == 0 and t != dest and t not in values and t not in view]")
n2 = s.count("        dest = self._dest(toks, values)")
s = s.replace("        dest = self._dest(toks, values)", "        dest = self._dest(toks, values | set(view))")
old = "        for t in toks:\n            if t == dest or t in values or t in self.neutral or t in change_words or self.word_n[t] == 0:"
assert old in s; s = s.replace(old, "        for t in toks:\n            if t == dest or t in values or t in view or t in self.neutral or t in change_words or self.word_n[t] == 0:")
p.write_bytes(s.encode('utf-8')); print('ids fixed', n1, n2)
