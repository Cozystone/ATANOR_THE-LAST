"""Human-provided prior knowledge (BOOTSTRAP_MANIFEST §2): tool signatures and documented effects.

The descriptions are true but incomplete: no preconditions, no failure conditions.
Effect specs: (role, attr, ('const', v) | ('copy', other_role)).
"""
DOCS = {
    'mkdir':   {'arity': 1, 'summary': 'creates a directory at ?a0',
                'effects': [(0, 'kind', ('const', 'dir'))]},
    'copy':    {'arity': 2, 'summary': 'copies file ?a0 to path ?a1',
                'effects': [(1, 'kind', ('const', 'file')), (1, 'hash', ('copy', 0))]},
    'move':    {'arity': 2, 'summary': 'moves ?a0 to path ?a1',
                'effects': [(0, 'kind', ('const', 'absent')), (0, 'hash', ('const', '-')),
                            (1, 'kind', ('const', 'file')), (1, 'hash', ('copy', 0))]},
    'delete':  {'arity': 1, 'summary': 'removes ?a0; needs capability destroy',
                'effects': [(0, 'kind', ('const', 'absent')), (0, 'hash', ('const', '-'))]},
    'convert': {'arity': 2, 'summary': 'writes a converted copy of ?a0 at ?a1',
                'effects': [(1, 'kind', ('const', 'file'))]},
}

# P3 view body: documented effects only, again without preconditions (which panel kinds accept which
# tool, that grouping needs the unfiltered list, that compare needs an absent target, ...).
VIEW_DOCS = {
    'open':    {'arity': 1, 'summary': 'opens list panel ?a0',
                'effects': [(0, 'kind', ('const', 'panel')), (0, 'filter', ('const', 'all')),
                            (0, 'sort', ('const', 'name')), (0, 'group', ('const', 'none'))]},
    'close':   {'arity': 1, 'summary': 'closes panel ?a0; needs capability close_panels',
                'effects': [(0, 'kind', ('const', 'absent')), (0, 'filter', ('const', '-')),
                            (0, 'sort', ('const', '-')), (0, 'group', ('const', '-'))]},
    'filter':  {'arity': 2, 'summary': 'panel ?a0 shows only items of extension ?a1',
                'effects': [(0, 'filter', ('copy', 1, 'value'))]},
    'sort':    {'arity': 2, 'summary': 'panel ?a0 is ordered by key ?a1',
                'effects': [(0, 'sort', ('copy', 1, 'value'))]},
    'group':   {'arity': 2, 'summary': 'panel ?a0 is grouped by ?a1',
                'effects': [(0, 'group', ('copy', 1, 'value'))]},
    'compare': {'arity': 2, 'summary': 'opens ?a0 as a comparison panel of ?a1 against the whole workspace',
                'effects': [(0, 'kind', ('const', 'compare'))]},
}
