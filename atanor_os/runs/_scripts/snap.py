"""Snapshot the atanor_os package (without runs/results/caches) so a pre-registered run executes code that
later edits in the working tree cannot touch. Usage: python atanor_os/runs/_scripts/snap.py <dest_dir>"""
import shutil, sys
from pathlib import Path

dest = Path(sys.argv[1])
if dest.exists():
    shutil.rmtree(dest)
dest.mkdir(parents=True)
shutil.copytree('atanor_os', dest / 'atanor_os', ignore=shutil.ignore_patterns('runs', 'results', '__pycache__', '*.pyc'))
print('snapshot at', dest / 'atanor_os')
