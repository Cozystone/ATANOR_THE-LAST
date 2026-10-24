"""Lifting concrete observations to role variables (provided representation, BOOTSTRAP_MANIFEST §1).

Body-generic since P3: every observed attribute enters a situation signature except identity-like
ones (IDENTITY_ATTRS: 'hash', whose values are instance-specific; only hash equality is lifted as
'same_content'), and every attribute can be an effect except derived structure (DERIVED_ATTRS:
'parent_kind', recomputed from kinds after effects are applied).
"""
from ..world.fs_world import parent_of

IDENTITY_ATTRS = ('hash',)
DERIVED_ATTRS = ('parent_kind',)
COPY_SOURCE_ATTRS = ('hash', 'value')      # attributes whose value can be carried into another role's attribute


def sig_attrs(obj):
    return [k for k in obj if k not in IDENTITY_ATTRS]


def effect_attrs(obj):
    return [k for k in obj if k not in DERIVED_ATTRS]


def lifted_pre(state, args):
    objs = [state.get(a) for a in args]
    lits = set()
    for i, o in enumerate(objs):
        if o is None:
            lits.add(('observed', (i,), False))
            continue
        for attr in sig_attrs(o):
            lits.add((attr, (i,), o[attr]))
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
            if a is not None and b is not None and 'hash' in a and 'hash' in b:
                lits.add(('same_content', (i, j), bool(a['hash'] != '-' and a['hash'] == b['hash'])))
    return frozenset(lits)


def lifted_effects(pre, post, args):
    """Per-role attribute changes: ('const', v); ('copy', j) when the new hash equals role j's old hash;
    ('copy', j, src_attr) when the new value equals role j's old `src_attr` (e.g. a panel's filter
    taking the name of the value object passed as the other argument)."""
    eff = []
    for i, a in enumerate(args):
        if pre.get(a) is None or post.get(a) is None:
            continue
        for attr in effect_attrs(pre[a]):
            v0, v1 = pre[a][attr], post[a][attr]
            if v0 == v1:
                continue
            spec = ('const', v1)
            if v1 not in ('-', 'unknown'):
                for j, b in enumerate(args):
                    if j == i or pre.get(b) is None:
                        continue
                    for sa in COPY_SOURCE_ATTRS:
                        if pre[b].get(sa) == v1:
                            spec = ('copy', j) if sa == attr else ('copy', j, sa)
                            break
                    if spec[0] == 'copy':
                        break
            eff.append((i, attr, spec))
    return eff


def effect_candidates(pre, post, args):
    """Effect hypothesis language for the rule learner: per changed (role, attr) the candidate specs in
    preference order. ('const', v) for non-identity attributes (identity values such as a hash are
    instance-specific, so only the markers '-'/'unknown' may be constants); then ('copy', j[, src_attr])
    for every other role j and every attribute of it whose old value equals the new value, same-attribute
    copies first (a compare panel inheriting the source panel's filter is ('copy', 1, 'filter')).
    `lifted_effects` keeps the single-spec form used by exact-signature retrieval (B)."""
    out = {}
    for i, a in enumerate(args):
        if pre.get(a) is None or post.get(a) is None:
            continue
        for attr in effect_attrs(pre[a]):
            v0, v1 = pre[a][attr], post[a][attr]
            if v0 == v1:
                continue
            cands = []
            if attr not in IDENTITY_ATTRS or v1 in ('-', 'unknown'):
                cands.append(('const', v1))
            if v1 not in ('-', 'unknown'):
                copies = []
                for j, b in enumerate(args):
                    if j == i or pre.get(b) is None:
                        continue
                    copies += [(sa != attr, j, sa) for sa in effect_attrs(pre[b]) if pre[b].get(sa) == v1]
                cands += [('copy', j) if sa == attr else ('copy', j, sa) for _, j, sa in sorted(copies)]
            out[(i, attr)] = cands
    return out


def frame_changes(pre, post, args):
    """Objects outside the arguments whose non-derived attributes changed."""
    return [p for p in pre if p in post and p not in args
            and any(pre[p][k] != post[p].get(k) for k in effect_attrs(pre[p]))]


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
            sa = spec[2] if len(spec) > 2 else attr
            new[a][attr] = src[sa] if src is not None and sa in src else 'unknown'
        else:
            new[a][attr] = 'unknown'
    for p, o in new.items():
        if 'parent_kind' in o:                                   # filesystem structure: parent_kind := kind(parent)
            par = parent_of(p)
            o['parent_kind'] = 'dir' if par == '' else (new[par]['kind'] if par in new else 'unobserved')
    return new
