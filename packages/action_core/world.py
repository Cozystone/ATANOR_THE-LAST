"""Owned temporary filesystem body; observations come from disk, not model claims.

Actions enumerate permission/schema possibilities, never hidden preconditions. This
is a single-process research body, not an OS sandbox against concurrent attackers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from .relations import validate_relations, validate_spec, observe_relations

from .schema import BASE_SCHEMA, TRANSFER_SCHEMA, bind_schema


@dataclass(frozen=True)
class Action:
    op: str
    args: tuple[str, ...]

    def to_dict(self):
        return {'op': self.op, 'args': list(self.args)}

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'op', 'args'} or
                type(value['op']) is not str or not value['op'] or
                type(value['args']) is not list or any(type(h) is not str for h in value['args']) or
                len(value['args']) not in (1, 2)):
            raise ValueError('invalid serialized action')
        # Syntax only: the independent body's bound schema grants permission.
        return cls(value['op'], tuple(value['args']))


@dataclass
class Frame:
    kinds: list[int]
    sizes: list[float]
    equal: list[list[float]]
    parent: list[list[float]]
    handles: tuple[str, ...]
    relations: dict = field(default_factory=dict)

    def __post_init__(self):
        n = len(self.handles)
        validate_relations(self.relations, n)
        if (not n or self.handles != tuple(f'n{i}' for i in range(n)) or
                len(self.kinds) != n or len(self.sizes) != n or
                any(type(k) is not int or k not in (0, 1, 2) for k in self.kinds)):
            raise ValueError('invalid frame vocabulary')
        if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
               for x in self.sizes):
            raise ValueError('invalid observed size')
        for matrix in (self.equal, self.parent):
            if len(matrix) != n or any(len(row) != n for row in matrix):
                raise ValueError('invalid relation dimensions')
            if any(type(x) not in (int, float) or x not in (0, 1)
                   for row in matrix for x in row):
                raise ValueError('invalid relation value')

    def to_dict(self):
        result = {'kinds': list(self.kinds), 'sizes': list(self.sizes),
                'equal': [list(r) for r in self.equal],
                'parent': [list(r) for r in self.parent], 'handles': list(self.handles)}
        if self.relations:
            result.update(view_version=2, relations={k: [list(r) for r in v] for k, v in self.relations.items()})
        return result

    @classmethod
    def from_dict(cls, value):
        legacy = {'kinds', 'sizes', 'equal', 'parent', 'handles'}
        if (type(value) is not dict or set(value) not in (legacy, legacy | {'view_version', 'relations'}) or
                ('view_version' in value and (value['view_version'] != 2 or not value['relations']))):
            raise ValueError('invalid frame fields')
        return cls(list(value['kinds']), list(value['sizes']),
                   [list(r) for r in value['equal']], [list(r) for r in value['parent']],
                   tuple(value['handles']), value.get('relations', {}))


def _relative(value):
    if type(value) is not str or not value or '\\' in value or ':' in value:
        raise ValueError('only nonempty relative POSIX paths are permitted')
    if any(ord(c) < 32 or c in '*?"<>|' for c in value):
        raise ValueError('invalid filesystem name')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts):
        raise ValueError('ambiguous or traversing path')
    if any(p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                     *(f'COM{i}' for i in range(10)),
                                     *(f'LPT{i}' for i in range(10))} for p in parts):
        raise ValueError('reserved device path')
    return PurePosixPath(value)


def _no_links(path):
    for part in reversed((path, *path.parents)):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('symlink/reparse path forbidden')


class Sandbox:
    @classmethod
    def attach(cls, root: Path, paths: list[str], protected: set[str] | None = None, operations=None,
               relation_spec=None, initial_links=None, context_initial=None):
        """Read-only reopening of a supervisor-bound research workspace.

        The supervisor, not the learner, supplies the authorized root and schema.
        This checks path containment and live filesystem state; it does NOT prove
        ownership from caller metadata or protect against a hostile host process.
        Episode resume separately binds the persisted goal/config/root/budget and
        compares native observations before dispatch. No initial files are rebuilt.
        """
        body = cls.__new__(cls)
        body.relation_spec = validate_spec(relation_spec)
        body.initial_links = dict(initial_links or {})
        body.context_initial = dict(context_initial or {})
        body.schema = cls._native_schema(operations)
        body.root = Path(root).absolute()
        _no_links(body.root)
        body.root = body.root.resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if (not body.root.is_relative_to(temp) or body.root == temp or
                not body.root.is_dir()):
            raise ValueError('attached root must be an existing directory below temporary root')
        if type(paths) is not list or not paths:
            raise ValueError('invalid attached path schema')
        relative = [_relative(p) for p in paths]
        if len({str(p).casefold() for p in relative}) != len(relative):
            raise ValueError('duplicate/aliased paths')
        body.handles = tuple(f'n{i}' for i in range(len(paths)))
        body.protected = frozenset(protected or ())
        if any(type(h) is not str or h not in body.handles for h in body.protected):
            raise ValueError('unknown protected handle')
        body._paths = dict(zip(body.handles, (body.root / str(p) for p in relative)))
        # Detect child reparse points too. Missing declared paths are valid state,
        # not a reason to reconstruct or materialize them.
        body.observe()
        body.evidence()
        return body

    def __init__(self, root: Path, paths: list[str], initial: dict[str, bytes | None],
                 protected: set[str] | None = None, operations=None, relation_spec=None, initial_links=None,
                 context_initial=None):
        self.relation_spec = validate_spec(relation_spec)
        self.initial_links = dict(initial_links or {})
        if context_initial is not None and type(context_initial) is not dict:
            raise ValueError('context initial state must be a dictionary')
        self.context_initial = dict(context_initial or {})
        self.schema = self._native_schema(operations)
        self.root = Path(root).absolute()
        _no_links(self.root)
        self.root = self.root.resolve()
        temp = Path(tempfile.gettempdir()).resolve()
        if (not self.root.is_relative_to(temp) or self.root == temp or
                os.path.lexists(self.root) or not self.root.parent.is_dir()):
            raise ValueError('root must be a new owned child under the temporary directory')
        if type(paths) is not list or not paths or type(initial) is not dict:
            raise ValueError('invalid body configuration')
        relative = [_relative(p) for p in paths]
        if len({str(p).casefold() for p in relative}) != len(relative):
            raise ValueError('duplicate/aliased paths')
        if any(k not in paths or (v is not None and type(v) is not bytes)
               for k, v in initial.items()):
            raise ValueError('initial entries must be declared paths with bytes or None')
        # Supervisor-owned environmental initial state, NOT learner observations
        # or additional action handles. All paths still stay in the owned root.
        context_paths = [str(_relative(p)) for p in self.context_initial]
        if (len({p.casefold() for p in paths+context_paths}) != len(paths)+len(context_paths)
                or any(v is not None and type(v) is not bytes for v in self.context_initial.values())):
            raise ValueError('invalid or overlapping environmental context')
        materialized = {**initial, **self.context_initial}
        for name in materialized:
            for parent in PurePosixPath(name).parents:
                if str(parent) != '.' and (str(parent) not in materialized or materialized[str(parent)] is not None):
                    raise ValueError('initial parent directories must be explicitly initialized')
        self.handles = tuple(f'n{i}' for i in range(len(paths)))
        self.protected = frozenset(protected or ())
        if any(type(h) is not str or h not in self.handles for h in self.protected):
            raise ValueError('unknown protected handle')
        self._paths = dict(zip(self.handles, (self.root / str(p) for p in relative)))
        protected_paths = {paths[self.handles.index(h)] for h in self.protected}
        for destination, source in self.initial_links.items():
            if (destination not in paths or source not in initial or type(initial[source]) is not bytes or
                    destination in initial or destination in protected_paths or source in protected_paths):
                raise ValueError('initial links must bind unprotected owned file paths')
            for parent in PurePosixPath(destination).parents:
                if str(parent) != '.' and (str(parent) not in materialized or materialized[str(parent)] is not None):
                    raise ValueError('initial link parent missing')
        self.root.mkdir()
        for name, value in sorted(materialized.items(), key=lambda item: (item[1] is not None, item[0].count('/'))):
            target = self.root / name
            if value is None:
                target.mkdir()
            else:
                with target.open('xb') as out:
                    out.write(value)
        for destination, source in self.initial_links.items():
            os.link(self.root / source, self.root / destination)

    def _checked(self, handle):
        path = self._paths[handle]
        _no_links(path)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('path escapes owned root')
        return path

    @staticmethod
    def _native_schema(operations):
        schema = bind_schema(operations)
        if any(row not in TRANSFER_SCHEMA.entries for row in schema.entries):
            raise ValueError('body has no such native operation')
        return schema

    def _permitted(self, action):
        # Permission checks depend only on declared paths, not success state.
        mutated = action.args if action.op == 'rename' else action.args[-1:]
        for handle in mutated:
            target = self._paths[handle]
            for protected in self.protected:
                p = self._paths[protected]
                if target == p or (action.op == 'rename' and p.is_relative_to(target)):
                    return False
        return True

    def _validate(self, action):
        if type(action) is not Action:
            raise ValueError('invalid action type')
        self.schema.index(action)
        if (any(h not in self._paths for h in action.args) or
                (len(action.args) == 2 and action.args[0] == action.args[1])):
            raise ValueError('invalid action schema')
        if not self._permitted(action):
            raise ValueError('mutation of protected path or subtree')
        paths = tuple(self._checked(h) for h in action.args)
        if action.op == 'rename' and paths[0].is_dir():
            # Native rename can transport a subtree; reject links anywhere in it.
            # This guard does not predict normal action success and is not a
            # hostile concurrent-process sandbox.
            for directory, folders, files in os.walk(paths[0], followlinks=False):
                for name in folders + files:
                    _no_links(Path(directory) / name)
        return paths

    def actions(self):
        # Preserve the old public ordering, then append new schema operations.
        ordered = sorted(enumerate(self.schema.entries), key=lambda row: (row[1][1], row[0]))
        result = []
        for _, (op, arity) in ordered:
            args = ((h,) for h in self.handles) if arity == 1 else (
                (s, d) for s in self.handles for d in self.handles if s != d)
            result.extend(Action(op, a) for a in args if self._permitted(Action(op, a)))
        return result

    def observe(self):
        paths = [self._checked(h) for h in self.handles]
        contents = [p.read_bytes() if p.is_file() else None for p in paths]
        kinds = [1 if p.is_file() else 2 if p.is_dir() else 0 for p in paths]
        sizes = [min(1., math.log1p(len(c)) / 16) if c is not None else 0. for c in contents]
        equal = [[float(a is not None and b is not None and a == b) for b in contents]
                 for a in contents]
        # parent[i][j] means node i is the direct filesystem parent of node j.
        parent = [[float(a == b.parent) for b in paths] for a in paths]
        return Frame(kinds, sizes, equal, parent, self.handles,
                     observe_relations(paths, self.relation_spec))

    def evidence(self):
        """Supervisor-only native receipts; never supplied as learner observations."""
        result = {}
        for handle in self.handles:
            path = self._checked(handle)
            if path.is_file():
                payload = path.read_bytes()
                result[handle] = {'kind': 1, 'sha256': hashlib.sha256(payload).hexdigest(),
                                  'size_bytes': len(payload)}
            else:
                result[handle] = {'kind': 2 if path.is_dir() else 0,
                                  'sha256': None, 'size_bytes': None}
        return result

    def step(self, action: Action):
        paths = self._validate(action)  # Reject unsafe requests before any filesystem mutation.
        try:
            if action.op == 'mkdir':
                paths[0].mkdir()
            elif action.op == 'empty':
                paths[0].write_bytes(b'')
            elif action.op == 'copy':
                shutil.copyfile(paths[0], paths[1])
            elif action.op == 'rename':
                paths[0].rename(paths[1])
            else:
                paths[0].unlink()
        except OSError:
            return False
        return True
