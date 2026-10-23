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
