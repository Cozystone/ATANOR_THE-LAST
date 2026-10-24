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

p = pathlib.Path('atanor_os/agent/concepts.py')
s = p.read_text(encoding='utf-8')
s += '''

# ---------------- P8b: evidence-preserving revision ----------------
UNCERTAIN_BELOW = 2          # provided: a condition backed by fewer stored counter-examples is uncertain, not a fact


def uncertain_atoms(group):
    return sorted(a for a in map(tuple, group['pre']) if group.get('ev', {}).get(repr(a), 0) < UNCERTAIN_BELOW)


def _synthetic(rep):
    """Stored evidence -> synthetic failures: for condition a of a rule with conjunction P, a failure in which
    everything in P but a held (weight = its evidence count)."""
    out = defaultdict(list)
    for tool, groups in rep.rules.items():
        for gi, g in enumerate(groups):
            pre = set(map(tuple, g['pre']))
            for a in pre:
                w = g.get('ev', {}).get(repr(a), 0)
                if w > 0:
                    out[tool].append({'group': gi, 'atom': a, 'set': frozenset(pre - {a}), 'w': w})
    return out


def revise_b(rep, new_exps, budget=None, verifier=None):
    """P8b revision. Stored evidence enters as synthetic failures, so a condition is not dropped merely because
    the new experience did not test it. A new success that satisfies everything but a stored condition
    conflicts with that condition's evidence; ATANOR then re-verifies (a small experiment through `verifier`,
    in the current world), revises (retires the evidence), or holds (keeps it, marks the condition uncertain)."""
    concepts = {n: [tuple(a) for a in d] for n, d in rep.dictionary.items()}
    synth = _synthetic(rep)
    succ_atoms = defaultdict(list)
    for e in new_exps:
        if not e.blocked and e.succeeded:
            succ_atoms[e.tool].append(atoms(rep.body, e.pre, e.args, rep.families, concepts))
    decisions, retired, uncertain = [], set(), set()
    for tool, items in synth.items():
        for it in items:
            if not any(it['set'] <= s and it['atom'] not in s for s in succ_atoms.get(tool, [])):
                continue                                     # no conflict: the stored evidence stands
            d = {'tool': tool, 'atom': list(it['atom']), 'evidence': it['w']}
            outcome = verifier(rep.body, tool, it['set'], it['atom'], concepts) if verifier else None
            if outcome is True:
                d['decision'], d['why'] = 'revise', 're-verified: the action succeeds now without this condition'
                retired.add((tool, it['group'], it['atom']))
            elif outcome is False:
                d['decision'], d['why'] = 'keep', 're-verified: the action still fails without this condition'
            elif it['w'] < UNCERTAIN_BELOW:
                d['decision'], d['why'] = 'revise', 'stored evidence is weak and new evidence contradicts it'
                retired.add((tool, it['group'], it['atom']))
            else:
                d['decision'], d['why'] = 'hold', 'could not re-verify; keep the evidence, condition marked uncertain'
                uncertain.add((tool, it['atom']))
            d['verified'] = outcome
            decisions.append(d)
    extra = {t: [(it['set'], it['w']) for it in items if (t, it['group'], it['atom']) not in retired] for t, items in synth.items()}
    new_rules = induce(rep.body, new_exps, rep.families, concepts, extra)
    merged = {}
    new_fail_atoms = defaultdict(list)
    for e in new_exps:
        if not e.blocked and not e.succeeded:
            new_fail_atoms[e.tool].append(atoms(rep.body, e.pre, e.args, rep.families, concepts))
    kept_old = dropped_old = 0
    for tool in sorted(set(rep.rules) | set(new_rules)):
        new_g = new_rules.get(tool, [])
        new_keys = {_key_of(g) for g in new_g}
        old = []
        for g in rep.rules.get(tool, []):
            pre = frozenset(map(tuple, g['pre']))
            if any(pre <= s for s in new_fail_atoms.get(tool, [])) or any((tool, gi, a) in retired for gi, gg in enumerate(rep.rules[tool]) if gg is g for a in pre):
                dropped_old += 1                             # contradicted by a new failure, or relies on retired evidence
                continue
            if _key_of(g) in new_keys:
                continue
            old.append(g)
            kept_old += 1
        merged[tool] = new_g + old
    expanded = {t: [{**g, 'pre': _expand(g['pre'], concepts), 'ev': _expand_ev(g, concepts)} for g in gs] for t, gs in merged.items()}
    new_dict, new_rules2 = invent(expanded)
    for t, gs in new_rules2.items():                         # carry the hold decisions as uncertainty marks
        for g in gs:
            g['held'] = sorted(repr(a) for a in map(tuple, g['pre']) if (t, a) in uncertain)
    old_defs = {frozenset(map(tuple, d)): n for n, d in rep.dictionary.items()}
    new_defs = {frozenset(map(tuple, d)): n for n, d in new_dict.items()}
    change = {'kept': sorted(old_defs[d] for d in old_defs if d in new_defs), 'removed': sorted(old_defs[d] for d in old_defs if d not in new_defs),
              'added': sorted(new_defs[d] for d in new_defs if d not in old_defs), 'old_rules_kept': kept_old, 'old_rules_dropped': dropped_old,
              'decisions': decisions, 'counts': dict(Counter(d['decision'] for d in decisions)),
              'experiments': sum(1 for d in decisions if d['verified'] is not None)}
    out = Representation(rep.body, new_dict, new_rules2, rep.families,
                         history=list(rep.history) + [{'step': 'revise_b', 'experiences': len(new_exps), 'concepts': len(new_dict),
                                                       'counts': change['counts'], 'experiments': change['experiments']}])
    if budget:
        out.history[-1]['pruned'] = out.prune_b(budget)
    return out, change


def _key_of(g):
    return tuple(sorted(repr(tuple(a)) for a in g['pre'] if tuple(a)[0] == 'U' and tuple(a)[2] == 'a0'))


def _expand_ev(g, concepts):
    ev = {}
    for a in map(tuple, g['pre']):
        c = g.get('ev', {}).get(repr(a), 0)
        if a[0] == 'C' and a[2] in concepts:
            for x in concepts[a[2]]:
                m = _inst(tuple(x), a[1])
                ev[repr(m)] = max(ev.get(repr(m), 0), c)
        else:
            ev[repr(a)] = max(ev.get(repr(a), 0), c)
    return ev


def _prune_b(self, budget):
    """ATANOR chooses what to keep under the budget: first the least valuable evidence entries
    (count x rule support), then rule groups by explained experiences per byte, then unused concepts."""
    dropped = {'evidence': 0, 'groups': 0}
    while self.size() > budget:
        evs = [(g.get('ev', {}).get(k, 0) * g['support'], t, i, k) for t, gs in self.rules.items() for i, g in enumerate(gs)
               for k in g.get('ev', {}) if g['ev'][k] > 0]
        if evs:
            _, t, i, k = min(evs)
            self.rules[t][i]['ev'][k] = 0                    # the condition stays; its evidence is forgotten (now uncertain)
            dropped['evidence'] += 1
            continue
        dropped['groups'] += self.prune(budget)
        break
    return dropped


Representation.prune_b = _prune_b


class ConceptModelB(ConceptModel):
    """Same predictions; statuses tell whether the chosen rule leans on an uncertain or held condition."""

    def predict(self, state, tool, args, sig=None):
        post, st = super().predict(state, tool, args, sig)
        if st == 'learned':
            at = atoms(self.rep.body, state, args, self.rep.families, self.concepts)
            g = self._cache.get((tool, at))
            if g is not None and (uncertain_atoms(g) or g.get('held')):
                st = 'learned_uncertain'
        return post, st
'''
p.write_text(s, encoding='utf-8')
print('ok')
