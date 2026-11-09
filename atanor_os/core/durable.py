"""Small durability helpers: replace a file whole or not at all, and cut a torn last line off an append-only log."""
import json
import os
from pathlib import Path


def atomic_write(path, data):
    """path holds the old content or the new content, whatever moment the process dies at."""
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'wb') as f:
        f.write(data.encode('utf-8') if isinstance(data, str) else data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def repair_jsonl(path):
    """Cuts an unfinished or unparsable last line; every complete line stays. -> number of bytes removed."""
    path = Path(path)
    if not path.exists():
        return 0
    raw = path.read_bytes()
    end = raw.rfind(b'\n') + 1                             # past the last newline: half written by a kill
    if end:                                                # the last complete line may still have been cut mid-JSON
        start = raw.rfind(b'\n', 0, end - 1) + 1
        try:
            json.loads(raw[start:end])
        except ValueError:
            end = start
    if end == len(raw):
        return 0
    with open(path, 'r+b') as f:
        f.truncate(end)
    return len(raw) - end
