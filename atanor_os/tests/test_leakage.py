"""Leakage guards (v2): resolved import names, dynamic-import patterns, and no frozen research code."""
import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
LEARNER_SIDE = ('agent', 'core', 'world')
DYNAMIC = re.compile(r'importlib|__import__|sys\.modules|\beval\(|\bexec\(')


def _resolved_imports(path):
    """Absolute module names imported by a file (relative imports resolved against the package)."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    rel = path.relative_to(PKG.parent).with_suffix('').parts   # ('atanor_os', 'agent', 'models')
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(rel[:-node.level]) + ([node.module] if node.module else [])
                out += ['.'.join(base + [a.name]) for a in node.names]
            else:
                out += ['.'.join([node.module, a.name]) for a in node.names]
    return out


def test_learner_side_never_resolves_to_evaluator():
    for folder in LEARNER_SIDE:
        for p in (PKG / folder).rglob('*.py'):
            for name in _resolved_imports(p):
                assert not name.startswith('atanor_os.eval'), (p.name, name)
                assert '.eval.' not in name and not name.endswith('.eval'), (p.name, name)


def test_learner_side_has_no_dynamic_imports():
    for folder in LEARNER_SIDE:
        for p in (PKG / folder).rglob('*.py'):
            src = p.read_text(encoding='utf-8')
            assert not DYNAMIC.search(src), (p.name, DYNAMIC.search(src).group(0))


def test_no_import_of_frozen_research_code():
    for p in PKG.rglob('*.py'):
        if 'runs' in p.parts or 'results' in p.parts:
            continue
        for name in _resolved_imports(p):
            assert not re.match(r'^(packages|scripts)(\.|$)', name), (p.name, name)
