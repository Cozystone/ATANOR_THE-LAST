"""Test helper (run as a process by test_life_host.py): lives one stage and terminates itself, hard, at one exact point of
the record: LIFE_KILL = 'after:ACTION_INTENT:2' means right after the second ACTION_INTENT is on disk; 'before:ACTION_RESULT:1'
means when the body has answered and the result is not yet written."""
import os
import signal
import sys

from atanor_os.life import autobiography
from atanor_os.life.run import main

when, kind, k = os.environ['LIFE_KILL'].split(':')
k = int(k)
real, seen = autobiography.Autobiography.append, [0]


def append(self, rec_kind, **data):
    hit = rec_kind == kind
    if hit:
        seen[0] += 1
    if hit and when == 'before' and seen[0] == k:
        os.kill(os.getpid(), signal.SIGTERM)               # TerminateProcess on Windows: no cleanup runs
    seq = real(self, rec_kind, **data)
    if hit and when == 'after' and seen[0] == k:
        os.kill(os.getpid(), signal.SIGTERM)
    return seq


autobiography.Autobiography.append = append
sys.exit(main(sys.argv[1:]))
