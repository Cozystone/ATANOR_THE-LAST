"""P8 raw observation adapter (perception, provided): each body's observations as ANONYMOUS attributes
a0, a1, ... and anonymous relations, with no human concept names and no derived attributes.

filesystem: a0 = exists (0/1), a1 = is_dir (0/1), a2 = name-suffix token, a3 = content digest
            (identity: only equality between objects is meaningful); relation r0(o, p): id(o) is id(p)
            without its last path segment (structural containment; not named).
view:       a0..a4 = the object's five observed tokens (kind, filter, sort, group, value), names removed;
            no relations.
board:      a0..a4 = the object's five observed tokens (kind, mark, tray, level, value), names removed;
            no relations.
clime:      a0..a4 = the object's five observed tokens (kind, heat, air, wing, value), names removed;
            no relations.
desk:       a0..a4 = the object's five observed tokens (kind, place, status, tag, value), names removed;
            no relations.
`to_human` is the deterministic inverse used only to hand predicted states to the planner and judge
(goals are written in the human attributes); it is an action interface, not concept learning.
"""
from .fs_world import parent_of

IDENTITY = {'fs': ('a3',), 'view': (), 'board': (), 'desk': (), 'clime': ()}
KIND_ATTRS = {'fs': ('a0', 'a1'), 'view': ('a0',), 'board': ('a0',), 'desk': ('a0',), 'clime': ('a0',)}       # provided: which raw attributes make up an argument's kind


def names_of(body, obj):
    """String attribute values of an object that a sentence may use to name it (identity and kind attributes excluded:
    a kind is what every object of that kind shares, not a name; the file body's kinds are 0/1 and never were names)."""
    return frozenset(v for k, v in raw_attrs(body, obj).items()
                     if k not in IDENTITY[body] and k not in KIND_ATTRS[body] and isinstance(v, str) and v not in ('-', '', None))


def raw_attrs(body, obj):
    if body == 'fs':
        k = obj.get('kind')
        return {'a0': 0 if k == 'absent' else 1, 'a1': 1 if k == 'dir' else 0, 'a2': obj.get('ext'), 'a3': obj.get('hash')}
    if body == 'board':
        return {'a0': obj.get('kind'), 'a1': obj.get('mark'), 'a2': obj.get('tray'), 'a3': obj.get('level'), 'a4': obj.get('value')}
    if body == 'desk':
        return {'a0': obj.get('kind'), 'a1': obj.get('place'), 'a2': obj.get('status'), 'a3': obj.get('tag'), 'a4': obj.get('value')}
    if body == 'clime':
        return {'a0': obj.get('kind'), 'a1': obj.get('heat'), 'a2': obj.get('air'), 'a3': obj.get('wing'), 'a4': obj.get('value')}
    return {'a0': obj.get('kind'), 'a1': obj.get('filter'), 'a2': obj.get('sort'), 'a3': obj.get('group'), 'a4': obj.get('value')}


def related(body, o_id, p_id):
    """r0(o, p) for the filesystem body; the view body has no relations."""
    return body == 'fs' and parent_of(p_id) == o_id and o_id != ''


def neighbours(body, state, p_id):
    """Observed objects o with r0(o, p)."""
    if body != 'fs':
        return []
    par = parent_of(p_id)
    return [par] if par and par in state else []


def to_human(body, raw, old):
    """Raw attributes -> the body's human attributes (planner/judge interface)."""
    if body == 'fs':
        kind = 'absent' if raw['a0'] == 0 else ('dir' if raw['a1'] == 1 else 'file')
        h = raw['a3'] if kind == 'file' else '-'
        return {**old, 'kind': kind, 'hash': h if h not in (None, 'unknown') or kind != 'file' else 'unknown', 'ext': raw['a2']}
    if body == 'board':
        return {**old, 'kind': raw['a0'], 'mark': raw['a1'], 'tray': raw['a2'], 'level': raw['a3'], 'value': raw['a4']}
    if body == 'desk':
        return {**old, 'kind': raw['a0'], 'place': raw['a1'], 'status': raw['a2'], 'tag': raw['a3'], 'value': raw['a4']}
    if body == 'clime':
        return {**old, 'kind': raw['a0'], 'heat': raw['a1'], 'air': raw['a2'], 'wing': raw['a3'], 'value': raw['a4']}
    return {**old, 'kind': raw['a0'], 'filter': raw['a1'], 'sort': raw['a2'], 'group': raw['a3'], 'value': raw['a4']}


def recompute_derived(body, state):
    """The filesystem's derived parent_kind (human interface only; never shown to the concept learner)."""
    if body == 'fs':
        for p, o in state.items():
            if 'parent_kind' in o:
                par = parent_of(p)
                o['parent_kind'] = 'dir' if par == '' else (state[par]['kind'] if par in state else 'unobserved')
    return state
