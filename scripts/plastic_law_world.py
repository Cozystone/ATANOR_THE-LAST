"""Evaluation bodies only: actual SQLite FK laws, never learner solutions."""
import importlib.util
from pathlib import Path

SOURCE = Path(r'C:\0.ASKIM ALL-VIN\27., ATANOR DEMO\packages\mind\fk_world.py')
spec = importlib.util.spec_from_file_location('original_fk_law', SOURCE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class LawWorld(native.FKWorld):
    def __init__(self, seed, n=4, prefill=2, law='restrict'):
        if law not in ('restrict', 'null', 'cascade'):
            raise ValueError('unknown experimental law')
        super().__init__(seed, n=n, prefill=0)
        self.con.execute('DROP TABLE row_')
        suffix = {'restrict':'', 'null':' ON DELETE SET NULL', 'cascade':' ON DELETE CASCADE'}[law]
        self.con.execute('CREATE TABLE row_ (k INTEGER PRIMARY KEY, ref INTEGER REFERENCES anchor(k)'+suffix+')')
        if prefill:
            self.con.execute('INSERT INTO anchor VALUES (0)')
            self.con.executemany('INSERT INTO row_ VALUES (?, NULL)', [(i,) for i in range(1,n)])
            for i in self.rng.choice(range(1,n), size=min(prefill,n-1), replace=False):
                self.con.execute('UPDATE row_ SET ref=0 WHERE k=?', (int(i),))
        self.con.commit()

