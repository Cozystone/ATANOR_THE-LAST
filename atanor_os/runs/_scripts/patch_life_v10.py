"""v10: an explanation never makes a word's meaning less specific. If the person's explanation yields only generic
atoms while the word already had a meaning naming a value, the specific meaning is kept (and the explanation still
counts as evidence for the word)."""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
old = """        for p in pids or []:
            self.pattern_of[word][p] += 5                    # the person defined it: strong evidence, not one co-occurrence
            self.confirmed[f'{word}|{p}'] += 1               # stated by the person counts like a confirmed use
        if meaning is not None:
            self.meaning[word] = set(meaning)"""
new = """        for p in pids or []:
            self.pattern_of[word][p] += 5                    # the person defined it: strong evidence, not one co-occurrence
            self.confirmed[f'{word}|{p}'] += 1               # stated by the person counts like a confirmed use
        if meaning is not None:
            def specific(m):
                return any(a.startswith("('U'") and a.split(',')[3].strip(" )'") not in ('0', '1', '-') for a in m)
            old_m = self.meaning.get(word)
            if old_m is not None and specific(old_m) and not specific(meaning):
                pass                                         # the explanation names no value: keep the more specific meaning
            else:
                self.meaning[word] = set(meaning)"""
assert old in s, 'anchor'
p.write_bytes(s.replace(old, new, 1).encode('utf-8'))
print('v10 ok')
