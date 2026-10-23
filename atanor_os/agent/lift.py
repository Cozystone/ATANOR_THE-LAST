"""Lifting concrete observations to role variables (provided representation, BOOTSTRAP_MANIFEST §1).

Signature literals: ('kind'|'ext'|'parent_kind', (role,), value) and ('same_content', (i, j), bool).
Hash VALUES are instance-specific and never part of a signature; only hash equality is.
"""
from ..world.fs_world import parent_of

SIG_ATTRS = ('kind', 'ext', 'parent_kind')
EFFECT_ATTRS = ('kind', 'ext', 'hash')        # parent_kind is derived structure, never an effect


def lifted_pre(state, args):
    objs = [state.get(a) for a in args]
    lits = set()
    for i, o in enumerate(objs):
        if o is None:
            lits.add(('observed', (i,), False))
            continue
        for attr in SIG_ATTRS:
            lits.add((attr, (i,), o[attr]))
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
            lits.add(('same_content', (i, j), bool(a and b and a['hash'] != '-' and a['hash'] == b['hash'])))
    return frozenset(lits)


def lifted_effects(pre, post, args):
    """Per-role attribute changes: ('const', v), or ('copy', j) when the new hash equals role j's old hash."""
    eff = []
    for i, a in enumerate(args):
        if pre.get(a) is None or post.get(a) is None:
            continue
        for attr in EFFECT_ATTRS:
            v0, v1 = pre[a][attr], post[a][attr]
            if v0 == v1:
                continue
            spec = ('const', v1)
            if attr == 'hash' and v1 != '-':
                for j, b in enumerate(args):
                    if j != i and pre.get(b) is not None and pre[b]['hash'] == v1:
                        spec = ('copy', j)
                        break
            eff.append((i, attr, spec))
    return eff


def frame_changes(pre, post, args):
    """Objects outside the arguments whose kind/ext/hash changed."""
    return [p for p in pre if p in post and p not in args and any(pre[p][k] != post[p][k] for k in EFFECT_ATTRS)]


def apply_effects(state, args, effects):
    new = {p: dict(o) for p, o in state.items()}
    for i, attr, spec in effects:
        a = args[i]
        if a not in new:
            continue
        if spec[0] == 'const':
            new[a][attr] = spec[1]
        elif spec[0] == 'copy':
            src = state.get(args[spec[1]])
            new[a][attr] = src[attr] if src is not None else 'unknown'
        else:
            new[a][attr] = 'unknown'
    for p, o in new.items():
        par = parent_of(p)
        o['parent_kind'] = 'dir' if par == '' else (new[par]['kind'] if par in new else 'unobserved')
    return new
