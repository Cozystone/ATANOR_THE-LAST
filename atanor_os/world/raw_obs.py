"""P8 raw observation adapter (perception, provided): each body's observations as ANONYMOUS attributes
a0, a1, ... and anonymous relations, with no human concept names and no derived attributes.

filesystem: a0 = exists (0/1), a1 = is_dir (0/1), a2 = name-suffix token, a3 = content digest
            (identity: only equality between objects is meaningful); relation r0(o, p): id(o) is id(p)
            without its last path segment (structural containment; not named).
view:       a0..a4 = the object's five observed tokens (kind, filter, sort, group, value), names removed;
            no relations.
`to_human` is the deterministic inverse used only to hand predicted states to the planner and judge
(goals are written in the human attributes); it is an action interface, not concept learning.
"""
from .fs_world import parent_of

IDENTITY = {'fs': ('a3',), 'view': ()}


def raw_attrs(body, obj):
    if body == 'fs':
        k = obj.get('kind')
        return {'a0': 0 if k == 'absent' else 1, 'a1': 1 if k == 'dir' else 0, 'a2': obj.get('ext'), 'a3': obj.get('hash')}
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
    return {**old, 'kind': raw['a0'], 'filter': raw['a1'], 'sort': raw['a2'], 'group': raw['a3'], 'value': raw['a4']}


def recompute_derived(body, state):
    """The filesystem's derived parent_kind (human interface only; never shown to the concept learner)."""
    if body == 'fs':
        for p, o in state.items():
            if 'parent_kind' in o:
                par = parent_of(p)
                o['parent_kind'] = 'dir' if par == '' else (state[par]['kind'] if par in state else 'unobserved')
    return state
