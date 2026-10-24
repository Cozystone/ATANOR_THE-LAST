"""Opt-in path-topology observation closure; no effects or success predicates.

Preserve original handle positions, append all within-root ancestor paths so
their existence/type can be observed. This is not complete host-state sensing
(permissions, locks, concurrent writers, mount changes etc. remain outside it).
"""
from .world import _relative


def ancestor_closed_paths(paths):
    originals=[str(_relative(p)) for p in paths]
    if len({p.casefold() for p in originals})!=len(originals):
        raise ValueError('duplicate paths')
    known={p.casefold() for p in originals};extra={}
    for path in originals:
        for parent in _relative(path).parents:
            name=str(parent)
            if name!='.' and name.casefold() not in known:
                extra.setdefault(name.casefold(),name)
    return originals+sorted(extra.values(),key=lambda p:(p.count('/'),p.casefold()))


def observe_ancestors(body, handles, *, max_new):
    """Supervisor-side opt-in sensor, not a policy or authority receipt.

Read ancestors of selected existing handles within the already owned root.
Return an expanded native Frame and explicit newly observed handles. Original
action scope is untouched. No arbitrary caller paths or success predicates.
Budget exhaustion rejects before sensor reads, not silent truncation. A caller
must journal the request/result before using this in a persistent agent loop;
this primitive alone provides neither autonomous selection nor provenance proof.
"""
    from .world import Sandbox
    if type(body) is not Sandbox:
        raise ValueError('native body required')
    if (type(handles) not in (list, tuple) or not handles
            or any(type(h) is not str or h not in body.handles for h in handles)
            or len(set(handles)) != len(handles)):
        raise ValueError('select distinct existing handles')
    if type(max_new) is not int or max_new < 0:
        raise ValueError('nonnegative integer sensor budget required')
    original = [body._paths[h].relative_to(body.root).as_posix() for h in body.handles]
    selected = [original[body.handles.index(h)] for h in handles]
    candidates = ancestor_closed_paths(selected)[len(selected):]
    known = {p.casefold() for p in original}
    added = [p for p in candidates if p.casefold() not in known]
    if len(added) > max_new:
        raise ValueError('sensor expansion exceeds budget')
    # attach is read-only and repeats root/path/reparse-point validation.
    sensor = Sandbox.attach(body.root, original+added, protected=set(body.protected),
                            operations=body.schema.to_data(), relation_spec=body.relation_spec)
    return sensor.observe(), sensor.handles[len(original):]
