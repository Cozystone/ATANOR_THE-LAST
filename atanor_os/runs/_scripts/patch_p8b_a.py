import pathlib


def patch(rel, pairs):
    p = pathlib.Path(rel)
    s = p.read_text(encoding='utf-8')
    for old, new in pairs:
        assert old in s, f'{rel}: {old[:90]}'
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('atanor_os/agent/concepts.py', [
    # induce: optional synthetic failures (stored evidence) and per-atom evidence counts
    ("""def induce(body, exps, families=FAMILIES_ALL, concepts=None):
    \"\"\"{tool: [group dicts]} by contrast-based induction over atoms (most general consistent conjunction per type group).\"\"\"""",
     """def induce(body, exps, families=FAMILIES_ALL, concepts=None, extra_fails=None):
    \"\"\"{tool: [group dicts]} by contrast-based induction over atoms (most general consistent conjunction per type group).
    extra_fails (P8b): {tool: [(atom set, weight)]} stored evidence re-entered as synthetic failures. Each kept atom gets
    an evidence count = weight of failures that only it excludes (group['ev'])."""
    extra_fails = extra_fails or {}"""),
    ("""        fails = [atoms(body, e.pre, e.args, families, concepts) for e in es if not e.succeeded]
""", """        fails = [(atoms(body, e.pre, e.args, families, concepts), 1) for e in es if not e.succeeded] + list(extra_fails.get(tool, []))
"""),
    ("""            unexplained = [s for s in fails if pre <= s]
            rest = [s for s in fails if not pre <= s]
            for a in sorted(pre, key=lambda a: (a[0] == 'U' and a[2] == 'a0', repr(a))):   # the type-like atom last
                if not any((pre - {a}) <= s for s in rest):
                    pre.discard(a)
            groups.append({'pre': sorted(pre, key=repr), 'eff': _effects(body, g), 'support': len(g), 'unexplained': len(unexplained)})
        rules[tool] = groups
    return rules""", """            unexplained = [s for s, w in fails if pre <= s]
            rest = [(s, w) for s, w in fails if not pre <= s]
            for a in sorted(pre, key=lambda a: (a[0] == 'U' and a[2] == 'a0', repr(a))):   # the type-like atom last
                if not any((pre - {a}) <= s for s, w in rest):
                    pre.discard(a)
            ev = {repr(a): sum(w for s, w in rest if (pre - {a}) <= s and a not in s) for a in pre}
            groups.append({'pre': sorted(pre, key=repr), 'eff': _effects(body, g), 'support': len(g), 'unexplained': len(unexplained), 'ev': ev})
        # tools that were tried but never succeeded keep no rule
        rules[tool] = groups
    for tool, ex in extra_fails.items():                     # a tool absent from the new experience keeps nothing new
        rules.setdefault(tool, [])
    return rules"""),
    # rewrite carries evidence to concept atoms (max of members) and back
    ("""            ng.append({**g, 'pre': sorted(set(new), key=repr)})""",
     """            ev = dict(g.get('ev', {}))
            for a in new:
                if a[0] == 'C':
                    members = [_inst(tuple(x), a[1]) for x in dictionary[a[2]]]
                    ev[repr(a)] = max([ev.get(repr(m), 0) for m in members] + [0])
            ng.append({**g, 'pre': sorted(set(new), key=repr), 'ev': {repr(a): ev.get(repr(a), 0) for a in set(new)}})"""),
    ("""                'rules': {t: [{'p': g['pre'], 'e': g['eff'], 's': g['support']} for g in gs] for t, gs in self.rules.items()},""",
     """                'rules': {t: [{'p': g['pre'], 'e': g['eff'], 's': g['support'], **({'v': [g['ev'].get(repr(tuple(a)), 0) for a in g['pre']]} if g.get('ev') else {})}
                              for g in gs] for t, gs in self.rules.items()},"""),
    ("""        rules = {t: [{'pre': [tuple(a) for a in g['p']], 'eff': g['e'], 'support': g['s']} for g in gs] for t, gs in d['rules'].items()}""",
     """        rules = {t: [{'pre': [tuple(a) for a in g['p']], 'eff': g['e'], 'support': g['s'],
                      **({'ev': {repr(tuple(a)): c for a, c in zip(g['p'], g['v'])}} if 'v' in g else {})} for g in gs] for t, gs in d['rules'].items()}"""),
])

print('replacements ok')
