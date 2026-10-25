"""v15: how a change's second object is named is learned from every confirmed use, not frozen at the first one.
pattern_meta[pid]['D_named'] counts, per confirmed use, whether the second object was named by its own id token, by a
value it carries, or only by word meaning. The second object is looked for by value or meaning unless every use so far
named it by its id. (Before, the first demonstration decided once: a first 'by extension' left the sort change unable
to take 'by ext' ever after.)"""
import pathlib, sys

p = pathlib.Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


rep("""    def _resolve_dest(self, r, toks, view):
        \"\"\"A change whose second object was named by a value it carries: find the unselected object with that value.\"\"\"
        meta = self.pattern_meta.get(r['pid'] or '', {})
        if r.get('dest') or meta.get('D_by') != 'value':
            return r""", """    def _note_d_naming(self, pid, toks, dest, view):
        \"\"\"Remember how this use named the change's second object: by its id, by a value it carries, or by meaning.\"\"\"
        if not dest or pid not in self.patterns:
            return
        how = 'token' if dest in toks else ('value' if dest in view and set(view[dest][1]) & set(toks) else 'meaning')
        named = self.pattern_meta.setdefault(pid, {}).setdefault('D_named', {})
        named[how] = named.get(how, 0) + 1

    def _resolve_dest(self, r, toks, view):
        \"\"\"A change whose second object has been named by a value it carries or by word meaning: find it among the
        unselected objects.\"\"\"
        meta = self.pattern_meta.get(r['pid'] or '', {})
        named = dict(meta.get('D_named', {}))
        if meta.get('D_by'):
            named[meta['D_by']] = named.get(meta['D_by'], 0) + 1
        elif meta:
            named['meaning'] = named.get('meaning', 0) + 1           # the first demonstration named it neither way
        if r.get('dest') or not (named.get('value') or named.get('meaning')):
            return r""")
rep("""        if confirmed:                                           # only a confirmed use teaches what the words mean
            self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])""",
    """        if confirmed:                                           # only a confirmed use teaches what the words mean
            self.lex.learn(toks, view_from_json(interp['view_at_start']), interp['pid'], interp['selected'], interp['dest'])
            self._note_d_naming(interp['pid'], toks, interp['dest'], view_from_json(interp['view_at_start']))""")
p.write_bytes(s.encode('utf-8'))
print('v15 ok')
