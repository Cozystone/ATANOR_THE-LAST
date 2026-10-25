"""v6: the core no longer names the file body. Each world provides its name, its kind signature, which attribute
values can serve as names, a lab copy and a state rebuild; a wanted change copies attributes between roles
('=o.hash', '=D.value') instead of knowing about content hashes; the second object of a change may be named by a
new token (a folder name) or by a value it carries (a screen value object), as the demonstration showed."""
import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:70]}'
        s = s.replace(old, new, 1)
    p.write_bytes(s.encode('utf-8'))


# ---------------------------------------------------------------- raw observations: per-body tables
patch('atanor_os/world/raw_obs.py', [
    ("""IDENTITY = {'fs': ('a3',), 'view': ()}""",
     """IDENTITY = {'fs': ('a3',), 'view': ()}
KIND_ATTRS = {'fs': ('a0', 'a1'), 'view': ('a0',)}       # provided: which raw attributes make up an argument's kind


def names_of(body, obj):
    \"\"\"String attribute values of an object that a sentence may use to name it (identity attributes excluded).\"\"\"
    return frozenset(v for k, v in raw_attrs(body, obj).items()
                     if k not in IDENTITY[body] and isinstance(v, str) and v not in ('-', '', None))"""),
])

# ---------------------------------------------------------------- file body: lab copy and state rebuild
patch('atanor_os/world/fs_world.py', [
    ("""class Workspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY""", """class Workspace:
    BODY = 'fs'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY"""),
    ("""    def existing(self):""", """    def lab_copy(self, root, objs, seen=None):
        \"\"\"A fresh workspace holding copies of the named objects (same relative paths, kinds and contents); an object
        no longer present but seen earlier (seen: {path: kind}) is recreated with placeholder content.\"\"\"
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = type(self)(root)
        lab.drift = self.drift
        for o in objs:
            if o is None:
                continue
            src, dst = self.path(o), lab.path(o)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copyfile(src, dst)
            elif src.is_dir():
                dst.mkdir(exist_ok=True)
            elif seen and seen.get(o) == 'file':
                dst.write_bytes(b'placeholder' + bytes([10]))
            elif seen and seen.get(o) == 'dir':
                dst.mkdir(exist_ok=True)
        return lab

    def lab_from_state(self, root, state):
        \"\"\"A fresh workspace rebuilt from an observed state ({path: attrs}); contents are placeholders.\"\"\"
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = type(self)(root)
        lab.drift = self.drift
        for path in sorted(state, key=lambda q: q.count('/')):
            k = state[path].get('kind')
            target = lab.path(path)
            if k == 'dir':
                target.mkdir(parents=True, exist_ok=True)
            elif k == 'file':
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'placeholder' + bytes([10]))
        return lab

    def existing(self):"""),
])

# ---------------------------------------------------------------- screen body: the same interface
patch('atanor_os/world/view_world.py', [
    ("""class ViewWorkspace:
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY""", """class ViewWorkspace:
    BODY = 'view'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY"""),
    ("""    def universe(self, paths=()):""", """    def tools(self):
        return dict(TOOLS)

    def existing(self):
        \"\"\"Every object the screen has: panels (open or not) and the value objects tools take.\"\"\"
        return sorted(set(PANELS) | set(VALUE_OBJECTS))

    def kind(self, obj):
        return self.attrs_of(self._read(), obj)['kind']

    def lab_copy(self, root, objs=(), seen=None):
        \"\"\"A fresh screen with the same specification, showing the same data (tools never change the data).\"\"\"
        root = Path(root)
        if root.exists():
            import shutil
            shutil.rmtree(root)
        lab = ViewWorkspace(root, self.data, spec=self._read())
        lab.drift = self.drift
        return lab

    def lab_from_state(self, root, state):
        root = Path(root)
        if root.exists():
            import shutil
            shutil.rmtree(root)
        spec = {p: {k: state[p][k] for k in ('kind', 'filter', 'sort', 'group')} for p in PANELS if state.get(p, {}).get('kind', 'absent') != 'absent'}
        lab = ViewWorkspace(root, self.data, spec=spec)
        lab.drift = self.drift
        return lab

    def universe(self, paths=()):"""),
])

# ---------------------------------------------------------------- the core
patch('atanor_os/agent/life.py', [
    ("""from ..world.raw_obs import raw_attrs""", """from ..world.raw_obs import KIND_ATTRS, names_of, raw_attrs"""),
    # kind signature per body
    ("""    def kinds(self, state, args):
        return tuple((raw_attrs(self.body, state[a])['a0'], raw_attrs(self.body, state[a])['a1']) if a in state else None for a in args)""",
     """    def kinds(self, state, args):
        ks = KIND_ATTRS[self.body]
        return tuple(tuple(raw_attrs(self.body, state[a])[k] for k in ks) if a in state else None for a in args)"""),
    # lexicon: an object may carry several names; a token may also be an object's id
    ("""        common = frozenset.intersection(*[a for a, _ in view.values()]) if view else frozenset()""",
     """        common = frozenset.intersection(*[a for a, _ in view.values()]) if view else frozenset()""") if False else ("""        inter = frozenset.intersection(*sel) if sel else frozenset()
        cur = {repr(a) for a in inter}
        values = {v for _, v in view.values()}""", """        inter = frozenset.intersection(*sel) if sel else frozenset()
        cur = {repr(a) for a in inter}
        values = set().union(*[vs for _, vs in view.values()]) if view else set()"""),
    ("""        for w in set(toks):
            if w in values:
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and set(selected) <= {o for o, (_, v) in view.items() if v == w})""",
     """        for w in set(toks):
            if w in values:
                self.value_rule[1] += 1
                self.value_rule[0] += int(bool(selected) and set(selected) <= {o for o, (_, vs) in view.items() if w in vs})"""),
    ("""    def _shape(self, toks, view, dest):
        values = {v for _, v in view.values()}""", """    def _shape(self, toks, view, dest):
        values = set().union(*[vs for _, vs in view.values()]) if view else set()"""),
    ("""    def interpret(self, toks, view, takes_dest):
        values = {v for _, v in view.values()}""", """    def interpret(self, toks, view, takes_dest):
        values = set().union(*[vs for _, vs in view.values()]) if view else set()"""),
    ("""            vals = [t for t in toks if t in values]
            cons = {a for a in cons if not a.startswith("('U', 0, 'a2'")} | {repr(a) for o, (at, v) in view.items() if v in vals for a in at if a[0] == 'U' and a[2] == 'a2'}""",
     """            vals = [t for t in toks if t in values]
            named = {repr(a) for o, (at, vs) in view.items() if vs & set(vals) for a in at if a[0] == 'U' and a[3] in vals}
            keys = {a.split(',')[2] for a in named}
            cons = {a for a in cons if a.split(',')[2] not in keys} | named"""),
    ("""        hits, opp = self.value_rule
        if opp >= 2 and hits / opp >= 0.8:
            for t in toks:
                if t != dest and t in values:
                    cons = {a for a in cons if not a.startswith("('U', 0, 'a2'")}
                    cons |= {repr(a) for o, (at, v) in view.items() if v == t for a in at if a[0] == 'U' and a[2] == 'a2'}
        a2 = {a for a in cons if a.startswith("('U', 0, 'a2'")}
        contradiction = len(a2) > 1
        sel = [] if contradiction else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})""",
     """        hits, opp = self.value_rule
        if opp >= 2 and hits / opp >= 0.8:
            for t in toks:
                if t != dest and t in values:
                    named = {repr(a) for o, (at, vs) in view.items() if t in vs for a in at if a[0] == 'U' and a[3] == t}
                    keys = {a.split(',')[2] for a in named}
                    cons = {a for a in cons if not (a.startswith("('U'") and a.split(',')[2] in keys)} | named
        by_key = defaultdict(set)
        for a in cons:
            if a.startswith("('U'"):
                by_key[a.split(',')[2]].add(a)
        contradiction = any(len(v) > 1 for v in by_key.values())
        ids = [t for t in toks if t in view and t != dest]
        if ids:
            sel, support = sorted(set(ids)), True                # tokens that are objects' own ids name them directly
        else:
            sel = [] if contradiction else sorted(o for o, (at, _) in view.items() if cons <= {repr(a) for a in at})"""),
    # what ATANOR sees: atoms and the names an object carries
    ("""    def view(self, ws=None):
        ws = ws or self.home
        objs = ws.existing()
        st = ws.observe(objs)
        return {o: (frozenset(a for a in atoms('fs', st, (o,), FAMILIES_ALL) if a[0] != 'E'), raw_attrs('fs', st[o])['a2']) for o in objs}""",
     """    def view(self, ws=None):
        ws = ws or self.home
        objs = ws.existing()
        st = ws.observe(objs)
        return {o: (frozenset(a for a in atoms(self.body, st, (o,), FAMILIES_ALL) if a[0] != 'E'), names_of(self.body, st[o])) for o in objs}"""),
    ("""        self.home, self.dir, self.lab_root, self.user = home, Path(mind_dir), Path(lab_root), user""",
     """        self.home, self.dir, self.lab_root, self.user = home, Path(mind_dir), Path(lab_root), user
        self.body = getattr(home, 'BODY', 'fs')"""),
    ("""        rp = self.dir / 'procedures.json'""", """        mp2 = self.dir / 'pattern_meta.json'
        self.pattern_meta = json.loads(mp2.read_text(encoding='utf-8')) if mp2.exists() else {}
        rp = self.dir / 'procedures.json'"""),
    ("""        (self.dir / 'procedures.json').write_text(json.dumps(self.procedures, indent=1), encoding='utf-8')""",
     """        (self.dir / 'procedures.json').write_text(json.dumps(self.procedures, indent=1), encoding='utf-8')
        (self.dir / 'pattern_meta.json').write_text(json.dumps(self.pattern_meta, indent=1), encoding='utf-8')"""),
    ("""            self._model = WorldModel(self.episodes, generalize=self.generalize, notice_change=self.notice_change, retired=retired,
                                     cache=self._cache)""", """            self._model = WorldModel(self.episodes, body=self.body, generalize=self.generalize, notice_change=self.notice_change,
                                     retired=retired, cache=self._cache)"""),
    ("""                sig = (tool, self.model.kinds(state, args), tuple(atoms('fs', state, args, FAMILIES_ALL)) if not self.generalize else None)""",
     """                sig = (tool, self.model.kinds(state, args), tuple(atoms(self.body, state, args, FAMILIES_ALL)) if not self.generalize else None)"""),
    # irreversibility from the learned change itself
    ("""        gone = any(it[0] == 'o' and it[1] == 'kind' and it[2] == 'absent' for it in pat)
        kept = any(it[1] == 'hash' and it[2] == '=o' and it[3:] != ['keep'] for it in pat)
        return gone and not kept""", """        gone = any(it[0] == 'o' and it[1] == 'kind' and it[2] == 'absent' for it in pat)
        kept = any(it[0] != 'o' and isinstance(it[2], str) and it[2].startswith('=o.') and it[1] != 'kind' and it[3:] != ['keep'] for it in pat)
        return gone and not kept"""),
    # the shown change, in roles, with attribute copies between roles
    ("""    def _pattern(self, before, after, o, dest):
        rels = {o: 'o'}
        if dest:
            rels.update({dest: 'D', f'{dest}/{name_of(o)}': 'D/o'})
        pat = []
        changed = [p for p in sorted(set(before) | set(after)) if any(before.get(p, {}).get(k) != after.get(p, {}).get(k) for k in ('kind', 'hash'))]
        if any(p not in rels for p in changed):
            return None
        needed = set(changed) | {q for q in rels if any(c.startswith(q + '/') for c in changed)}
        for p in sorted(needed):
            b, a = before.get(p, {}), after.get(p, {})
            for k in ('kind', 'hash'):
                if k == 'kind' or b.get(k) != a.get(k):
                    if k != 'kind' and self._implied(a.get('kind'), k, a.get(k)):
                        continue                               # learned: every object of this kind seen so far had this value
                    v = '=o' if k == 'hash' and a.get(k) == before[o].get('hash') and a.get(k) != '-' else a.get(k)
                    pat.append([rels[p], k, v])
        if pat and before.get(o, {}).get('kind') == after.get(o, {}).get('kind') == 'file':
            pat += [['o', 'kind', 'file', 'keep'], ['o', 'hash', '=o', 'keep']]     # what the shown change left as it was
        return pat or None""", """    def _pattern(self, before, after, o, dest):
        rels = {o: 'o'}
        if dest:
            rels.update({dest: 'D', f'{dest}/{name_of(o)}': 'D/o'})
        attrs = sorted({k for st in (before, after) for ob in st.values() for k in ob})
        changed = [p for p in sorted(set(before) | set(after)) if any(before.get(p, {}).get(k) != after.get(p, {}).get(k) for k in attrs)]
        if any(p not in rels for p in changed):
            return None
        needed = set(changed) | {q for q in rels if any(c.startswith(q + '/') for c in changed)}
        roles = [(rels[q], q) for q in rels if q in before]

        def encode(k, value):
            \"\"\"A value that equals an attribute of a role before the change is a copy; the same attribute is preferred.\"\"\"
            if value in ('-', None):
                return value
            for rel, q in roles:
                if before[q].get(k) == value:
                    return f'={rel}.{k}'
            for rel, q in roles:
                for k2, v2 in before[q].items():
                    if v2 == value and k2 != 'kind':
                        return f'={rel}.{k2}'
            return value
        pat = []
        for p in sorted(needed):
            b, a = before.get(p, {}), after.get(p, {})
            for k in attrs:
                if k == 'kind' or b.get(k) != a.get(k):
                    if k != 'kind' and self._implied(a.get('kind'), k, a.get(k)):
                        continue                               # learned: every object of this kind seen so far had this value
                    pat.append([rels[p], k, a.get('kind') if k == 'kind' else encode(k, a.get(k))])
        if pat and o not in changed and before.get(o, {}).get('kind') not in ('absent', None):
            for k in attrs:                                    # what the shown change left as it was
                if k == 'kind' or not self._implied(before[o]['kind'], k, before[o].get(k)):
                    pat.append(['o', k, before[o]['kind'] if k == 'kind' else encode(k, before[o].get(k)), 'keep'])
        return pat or None"""),
    # the goal from a change: roles resolve to paths, copies resolve from the current state
    ("""        st = self.home.observe(interp['selected'])
        must, keep, universe = [], [], set()
        for o in interp['selected']:
            path = {'o': o, 'D': interp['dest'], 'D/o': f"{interp['dest']}/{name_of(o)}" if interp['dest'] else None}
            for item in pat:
                rel, k, v = item[:3]
                if path[rel] is None:
                    return None
                val = st[o]['hash'] if v == '=o' else v
                (keep if item[3:] == ['keep'] else must).append(Literal(k, (path[rel],), val))
                universe.add(path[rel])""", """        st = self.home.observe(list(interp['selected']) + ([interp['dest']] if interp['dest'] else []))
        must, keep, universe = [], [], set()
        for o in interp['selected']:
            path = {'o': o, 'D': interp['dest'], 'D/o': f"{interp['dest']}/{name_of(o)}" if interp['dest'] else None}
            for item in pat:
                rel, k, v = item[:3]
                if path[rel] is None:
                    return None
                if isinstance(v, str) and v.startswith('=') and '.' in v:
                    r2, k2 = v[1:].split('.', 1)
                    if path[r2] is None or path[r2] not in st:
                        return None
                    val = st[path[r2]].get(k2)
                else:
                    val = v
                (keep if item[3:] == ['keep'] else must).append(Literal(k, (path[rel],), val))
                universe.add(path[rel])"""),
    # relevance from raw effects, body-generic
    ("""        want = set()
        for l in goal.must:
            if l.pred == 'kind':
                want |= {('a0', 0)} if l.value == 'absent' else ({('a0', 1), ('a1', 1)} if l.value == 'dir' else {('a0', 1)})
            elif l.pred == 'hash':
                want.add(('a3', 'copy'))
        out = set()""", """        want = set()
        state = self.home.observe(goal.universe)
        for l in goal.must:
            cur = state.get(l.args[0], {})
            now, then = raw_attrs(self.body, cur), raw_attrs(self.body, {**cur, l.pred: l.value})
            for k in then:
                if then[k] != now.get(k):
                    want.add((k, then[k]))
                    want.add((k, 'copy'))
        out = set()"""),
    # the lab and the rebuild are the world's business
    ("""        past = [i for i, e in enumerate(self.episodes) if e.tool == tool and e.succeeded and not e.blocked]
        if not past:
            return
        e = self.episodes[past[-1]]
        if self.lab_root.exists():
            shutil.rmtree(self.lab_root)
        lab = type(self.home)(self.lab_root)
        lab.drift = getattr(self.home, 'drift', frozenset())
        for path in sorted(e.pre, key=lambda q: q.count('/')):
            k = e.pre[path].get('kind')
            target = lab.path(path)
            if k == 'dir':
                target.mkdir(parents=True, exist_ok=True)
            elif k == 'file':
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'placeholder' + bytes([10]))
        before = len(self.episodes)""", """        past = [i for i, e in enumerate(self.episodes) if e.tool == tool and e.succeeded and not e.blocked]
        if not past:
            return
        e = self.episodes[past[-1]]
        lab = self.home.lab_from_state(self.lab_root, e.pre)
        before = len(self.episodes)"""),
    ("""    def _lab(self, objs, dest, seen=None):
        \"\"\"A fresh lab mirroring the relevant objects of home (same relative paths, kinds and contents); an object no
        longer in home but seen earlier (seen: {path: kind}) is recreated with placeholder content.\"\"\"
        if self.lab_root.exists():
            shutil.rmtree(self.lab_root)
        lab = type(self.home)(self.lab_root)
        lab.drift = getattr(self.home, 'drift', frozenset())     # the lab is a copy of the world as it is now
        for o in objs:
            if o is None:
                continue
            src = self.home.path(o)
            dst = lab.path(o)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copyfile(src, dst)
            elif src.is_dir():
                dst.mkdir(exist_ok=True)
            elif seen and seen.get(o) == 'file':
                dst.write_bytes(b'placeholder' + bytes([10]))
            elif seen and seen.get(o) == 'dir':
                dst.mkdir(exist_ok=True)
        return lab""", """    def _lab(self, objs, dest, seen=None):
        \"\"\"A fresh lab: the world's own copy of the relevant objects, as the world is now.\"\"\"
        return self.home.lab_copy(self.lab_root, [o for o in objs if o is not None], seen)"""),
    # how the second object was named in the demonstration is remembered with the change
    ("""        self.patterns[pid] = pattern
        self._taught = {'command': command, 'pid': pid, 'selected': sorted(objs), 'dest': dest}""",
     """        self.patterns[pid] = pattern
        if dest:
            d_by = 'token' if dest in toks else ('value' if names_of(self.body, before.get(dest, {})) & set(toks) else None)
            self.pattern_meta[pid] = {'D_by': d_by, 'D_kind': before.get(dest, {}).get('kind')}
        self._taught = {'command': command, 'pid': pid, 'selected': sorted(objs), 'dest': dest}"""),
    # resolve a second object named by a value it carries
    ("""    def _proposal(self, r):""", """    def _resolve_dest(self, r, toks, view):
        \"\"\"A change whose second object was named by a value it carries: find the unselected object with that value.\"\"\"
        meta = self.pattern_meta.get(r['pid'] or '', {})
        if r.get('dest') or meta.get('D_by') != 'value':
            return r
        cands = [o for o, (at, vs) in view.items() if o not in r['selected'] and vs & set(toks)
                 and any(a[0] == 'U' and a[2] == 'a0' and a[3] == meta.get('D_kind') for a in at)]
        return {**r, 'dest': cands[0]} if len(cands) == 1 else r

    def _proposal(self, r):"""),
    ("""            r = self.lex.interpret(toks, view, True)
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:""", """            r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
            if r['unknown'] and self.user is not None:
                if not self.patterns or '<shape>' in r['unknown']:"""),
    ("""        r = self.lex.interpret(toks, view, True)
        if pointed is not None and r['pid'] in self.patterns:""", """        r = self._resolve_dest(self.lex.interpret(toks, view, True), toks, view)
        if pointed is not None and r['pid'] in self.patterns:"""),
    # merging changes carries their meta
    ("""        for q, keep in alias.items():
            self.patterns.pop(q, None)""", """        for q, keep in alias.items():
            self.patterns.pop(q, None)
            if q in self.pattern_meta and keep not in self.pattern_meta:
                self.pattern_meta[keep] = self.pattern_meta[q]
            self.pattern_meta.pop(q, None)"""),
])

# ---------------------------------------------------------------- names are sets: store them as lists, restore as sets
patch('atanor_os/agent/life.py', [
    ("""                'view_at_start': {o: ([repr(a) for a in at], v) for o, (at, v) in view.items()}}""",
     """                'view_at_start': {o: ([repr(a) for a in at], sorted(v)) for o, (at, v) in view.items()}}"""),
    ("""    return {o: (frozenset(ast.literal_eval(a) for a in at), v) for o, (at, v) in d.items()}""",
     """    return {o: (frozenset(ast.literal_eval(a) for a in at), frozenset(v) if isinstance(v, list) else v) for o, (at, v) in d.items()}"""),
])
print('names ok')
print('ok')

# ---------------------------------------------------------------- the second object may appear only inside a copied value
import subprocess, sys
subprocess.run([sys.executable, 'atanor_os/runs/_scripts/fix_dest.py', 'atanor_os/agent/life.py'], check=True)
subprocess.run([sys.executable, 'atanor_os/runs/_scripts/fix_surprise.py', 'atanor_os/agent/life.py'], check=True)
subprocess.run([sys.executable, 'atanor_os/runs/_scripts/fix_universe.py', 'atanor_os/agent/life.py'], check=True)
subprocess.run([sys.executable, 'atanor_os/runs/_scripts/fix_ids.py', 'atanor_os/agent/life.py'], check=True)
subprocess.run([sys.executable, 'atanor_os/runs/_scripts/fix_caps.py', 'atanor_os/agent/life.py'], check=True)
