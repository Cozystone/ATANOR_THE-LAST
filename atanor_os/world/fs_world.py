"""Real filesystem workspace: the observation/execution adapter (charter §4).

Everything observable comes from disk; every tool acts on disk. Containment is a research
boundary (own root, relative POSIX paths, no '..', no symlinks), not a defense against a
hostile concurrent process. Tools enforce their own preconditions but do NOT export them in
machine-readable form: discovering them is the learner's job (BOOTSTRAP_MANIFEST.md §2).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
from pathlib import Path, PurePosixPath

TOOLS = {'mkdir': 1, 'copy': 2, 'move': 2, 'delete': 1, 'convert': 2}
CAPABILITY = {'delete': 'destroy', 'zap': 'destroy'}
ENV_VERSION = f'fsworld-1/py{sys.version_info.major}.{sys.version_info.minor}/{sys.platform}'


def rel(value):
    if type(value) is not str or not value or value[0] == '/' or '\\' in value or ':' in value:
        raise ValueError(f'bad path {value!r}')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p != p.strip() for p in parts):
        raise ValueError(f'bad path {value!r}')
    return PurePosixPath(value)


def parent_of(path):
    p = str(PurePosixPath(path).parent)
    return '' if p == '.' else p


def ancestors(path):
    out, p = [], parent_of(path)
    while p:
        out.append(p)
        p = parent_of(p)
    return out


def name_ext(path):
    name = PurePosixPath(path).name
    return name.rsplit('.', 1)[1] if '.' in name[1:] else '-'


class Workspace:
    BODY = 'fs'
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
    drift = frozenset()            # P8b: changed world rules, e.g. {'move_dirs'}; empty = the original world

    def __init__(self, root, create=True):
        root = Path(root).absolute()
        if create:
            root.mkdir(parents=True, exist_ok=False)
        if root.is_symlink() or not root.is_dir():
            raise ValueError('workspace root must be a real directory')
        self.root = root.resolve()
        self.env_version = ENV_VERSION

    def path(self, value):
        r = rel(value)
        cur = self.root
        for part in r.parts:
            cur = cur / part
            if cur.is_symlink():
                raise ValueError('symlink in path')
        if not cur.resolve().is_relative_to(self.root):
            raise ValueError('path escapes workspace')
        return cur

    def kind(self, value):
        p = self.path(value)
        return 'file' if p.is_file() else 'dir' if p.is_dir() else 'absent'

    def attrs(self, value):
        p = self.path(value)
        k = 'file' if p.is_file() else 'dir' if p.is_dir() else 'absent'
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:12] if k == 'file' else '-'
        par = parent_of(value)
        return {'kind': k, 'ext': name_ext(value), 'hash': h, 'parent_kind': 'dir' if par == '' else self.kind(par)}

    def lab_copy(self, root, objs, seen=None):
        """A fresh workspace holding copies of the named objects (same relative paths, kinds and contents); an object
        no longer present but seen earlier (seen: {path: kind}) is recreated with placeholder content."""
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = type(self)(root)
        lab.drift = self.drift
        for o in objs:
            if o is None:
                continue
            src, dst = self.path(o), lab.path(o)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copyfile(src, dst)
            elif src.is_dir():
                dst.mkdir(exist_ok=True)
            elif seen and seen.get(o) == 'file':
                dst.write_bytes(b'placeholder' + bytes([10]))
            elif seen and seen.get(o) == 'dir':
                dst.mkdir(exist_ok=True)
        return lab

    def lab_from_state(self, root, state):
        """A fresh workspace rebuilt from an observed state ({path: attrs}); contents are placeholders."""
        root = Path(root)
        if root.exists():
            shutil.rmtree(root)
        lab = type(self)(root)
        lab.drift = self.drift
        for path in sorted(state, key=lambda q: q.count('/')):
            k = state[path].get('kind')
            target = lab.path(path)
            if k == 'dir':
                target.mkdir(parents=True, exist_ok=True)
            elif k == 'file':
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'placeholder' + bytes([10]))
        return lab

    def existing(self):
        out = []
        for dirpath, dirs, files in os.walk(self.root):
            base = Path(dirpath).relative_to(self.root).as_posix()
            base = '' if base == '.' else base
            out += [f'{base}/{n}' if base else n for n in dirs + files]
        return sorted(out)

    def universe(self, paths):
        """Observable objects: everything that exists, every path the caller names, and all ancestors."""
        u = set(self.existing()) | set(paths)
        for p in list(u):
            u.update(ancestors(p))
        return sorted(u)

    def observe(self, paths):
        return {p: self.attrs(p) for p in self.universe(paths)}

    def actions(self_or_universe, universe=None):
        """Syntactically valid actions over a universe; permissions and preconditions are not consulted.
        Called on a workspace it uses that workspace's current tools; called on the class, the original tools."""
        tools = self_or_universe.tools() if universe is not None else TOOLS
        universe = self_or_universe if universe is None else universe
        out = []
        for tool, ar in tools.items():
            if ar == 1:
                out += [(tool, (a,)) for a in universe]
            else:
                out += [(tool, (a, b)) for a in universe for b in universe if a != b]
        return out

    def execute(self, tool, args, capabilities):
        """Real action. Failing a precondition is an ordinary failed action, not an exception."""
        t0 = time.perf_counter()
        tools = self.tools()
        if tool not in tools or len(args) != tools[tool] or len(set(args)) != len(args):
            raise ValueError('invalid action')
        cap = CAPABILITY.get(tool)
        if cap and not capabilities.get(cap):
            return {'ok': False, 'blocked': True, 'error': f'capability {cap} not granted', 'ms': 0.0}
        paths = [self.path(a) for a in args]
        try:
            ok, err = getattr(self, '_' + tool)(*paths), ''
        except OSError as e:
            ok, err = False, type(e).__name__
        return {'ok': ok, 'blocked': False, 'error': err, 'ms': (time.perf_counter() - t0) * 1000}

    # --- tool semantics (real) ---
    def _mkdir(self, p):
        p.mkdir()                      # fails if it exists or the parent is not a directory
        return True

    def tools(self):
        """The body's tool names and arity (all an agent is told). A changed world can retire and add tools."""
        t = dict(TOOLS)
        if 'copy_retired' in self.drift:
            t['replicate'] = 2
        if 'delete_retired' in self.drift:
            t['zap'] = 1
        if 'move_retired' in self.drift:
            t['shove'] = 2
        return t

    def _zap(self, p):
        """Changed world only: removes a file."""
        if 'delete_retired' not in self.drift or not p.is_file():
            return False
        p.unlink()
        return True

    def _shove(self, d, s):
        """Changed world only: moves a file, destination first."""
        if 'move_retired' not in self.drift:
            return False
        if not s.is_file() or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
        s.rename(d)
        return True

    def _replicate(self, d, s):
        """Changed world only: copies, destination first."""
        if 'copy_retired' not in self.drift:
            return False
        if not s.is_file() or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
        shutil.copyfile(s, d)
        return True

    def _copy(self, s, d):
        if 'copy_retired' in self.drift:
            return False                                         # changed world: the old copy no longer works
        if not s.is_file() or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
        shutil.copyfile(s, d)
        return True

    def _move(self, s, d):
        if 'move_retired' in self.drift:
            return False
        movable = s.is_file() or ('move_dirs' in self.drift and s.is_dir() and not s.is_symlink())
        if not movable or d.exists() or d.is_symlink() or not d.parent.is_dir():
            return False
        if s.is_dir() and s.resolve() in d.resolve().parents:       # a folder cannot move into itself
            return False
        s.rename(d)
        return True

    def _delete(self, p):
        if 'delete_retired' in self.drift:
            return False
        if not p.is_file():
            return False
        p.unlink()
        return True

    def _convert(self, s, d):
        if not s.is_file() or s.suffix != '.txt' or d.suffix != '.md' or d.exists() or not d.parent.is_dir():
            return False
        d.write_bytes(b'# converted\n' + s.read_bytes())
        return True
