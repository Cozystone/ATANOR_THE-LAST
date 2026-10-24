"""Read native schema structure for already-bound entities; no action semantics.

Entity-to-table binding belongs to the body, not inferred from caller authority.
Returned numbers/edges omit SQL identifiers, primary-key values and solutions.
Not a generic authentication boundary or an independently discovered ontology.
"""

def schema_observation(connection, entity_tables):
    tables=tuple(entity_tables)
    existing={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables or any(type(t) is not str or t not in existing for t in tables):
        raise ValueError('entity binding refers to absent native table')
    metadata={}
    for table in set(tables):
        columns=list(connection.execute('SELECT * FROM pragma_table_info(?)',(table,)))
        references={r[2] for r in connection.execute('SELECT * FROM pragma_foreign_key_list(?)',(table,))}
        metadata[table]=(len(columns),references)
    return {'scalars':[metadata[t][0]/(1+metadata[t][0]) for t in tables],
            'references':[[int(right in metadata[left][1]) for right in tables] for left in tables]}
