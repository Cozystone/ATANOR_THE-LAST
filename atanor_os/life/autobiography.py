"""The one autobiography of a Self: append-only, every record chained to the one before it by SHA-256 and fsync'd before
append() returns, so what is in it was durable before the next step was taken. Kinds are kept apart (mandate XVI: a
prediction does not become an observation by being written next to one); 'HOST' is the life's own bookkeeping (stages,
processes, checkpoints), not something the Self saw or was told.
"""
import hashlib
import json
import os
import threading
from pathlib import Path

from ..core.durable import repair_jsonl

KINDS = ('OBSERVATION', 'PREDICTION', 'ACTION_INTENT', 'ACTION_RESULT', 'EXTERNAL_EVENT', 'TESTIMONY', 'SELF_TRIAL', 'HOST',
         'INTEROCEPTION')                               # what the Self feels of itself (energy): not the world, not a prediction
GENESIS = '0' * 64


class ChainBroken(Exception):
    """A complete record does not follow from the one before it: the history was altered, not interrupted."""


def _digest(prev, seq, kind, data):
    body = json.dumps([seq, kind, data], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256((prev + body).encode('utf-8')).hexdigest()


def read(path):
    """All records in order, checked against the chain. A last line a kill left unfinished is not a record."""
    out, prev = [], GENESIS
    path = Path(path)
    if not path.exists():
        return out
    lines = path.read_bytes().split(b'\n')
    for i, line in enumerate(lines[:-1]):                  # only complete lines (the part after the last newline never is)
        try:
            r = json.loads(line)
        except ValueError:
            if i == len(lines) - 2:                        # the last complete line may have been cut mid-JSON
                break
            raise ChainBroken(f'record {i} is not readable')
        if r.get('seq') != i or r.get('prev') != prev or _digest(prev, i, r['kind'], r['data']) != r.get('sha'):
            raise ChainBroken(f'record {i} does not follow from the one before it')
        out.append(r)
        prev = r['sha']
    return out


class Autobiography:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        repair_jsonl(self.path)                            # only a torn tail goes; read() below refuses anything else
        rows = read(self.path)
        self.seq = len(rows)
        self.head = rows[-1]['sha'] if rows else GENESIS
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o644)

    def append(self, kind, **data):
        """-> the record's sequence number, after the record is on disk."""
        if kind not in KINDS:
            raise ValueError(f'not a kind of record: {kind}')
        with self.lock:
            data = json.loads(json.dumps(data, ensure_ascii=False, default=str))   # what is kept is what can be read back
            sha = _digest(self.head, self.seq, kind, data)
            row = {'seq': self.seq, 'kind': kind, 'prev': self.head, 'sha': sha, 'data': data}
            os.write(self.fd, (json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8'))
            os.fsync(self.fd)
            self.head = sha
            self.seq += 1
            return row['seq']

    def rows(self):
        return read(self.path)

    def close(self):
        os.close(self.fd)
