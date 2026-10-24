import sqlite3
import pytest
from packages.shared_world.sql_schema_sensor import schema_observation

def test_real_schema_not_names_or_row_values_and_permutation():
    with sqlite3.connect(':memory:') as con:
        con.execute('CREATE TABLE unfamiliar(k INTEGER PRIMARY KEY)')
        con.execute('CREATE TABLE other(k INTEGER PRIMARY KEY, ref INTEGER REFERENCES unfamiliar(k))')
        original=schema_observation(con,['unfamiliar','other','other'])
        assert original['scalars']==[.5,2/3,2/3]
        assert original['references']==[[0,0,0],[1,0,0],[1,0,0]]
        permuted=schema_observation(con,['other','unfamiliar','other'])
        order=[1,0,2]
        assert permuted['scalars']==[original['scalars'][i] for i in order]
        assert permuted['references']==[[original['references'][i][j] for j in order] for i in order]
        con.execute('ALTER TABLE unfamiliar RENAME TO renamed')
        assert schema_observation(con,['renamed','other','other'])==original
        con.execute('INSERT INTO renamed VALUES (87)')
        assert schema_observation(con,['renamed','other','other'])==original

def test_absent_binding_is_rejected():
    with sqlite3.connect(':memory:') as con:
        with pytest.raises(ValueError): schema_observation(con,['missing'])
