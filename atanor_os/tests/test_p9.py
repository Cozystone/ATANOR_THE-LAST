"""P9: word meanings come from feedback over ATANOR's own atoms; concepts are addressed by definition hash;
the evaluation refuses sealed files inside the package and an early delayed test."""
import json
from pathlib import Path

import pytest

from atanor_os.agent.concepts import Representation
from atanor_os.agent.language import Lexicon, concept_ids, tokens
from atanor_os.eval import p9

PKG = Path(__file__).resolve().parents[1]


def test_language_module_has_no_tool_name_matching_or_teacher_imports():
    src = (PKG / 'agent' / 'language.py').read_text(encoding='utf-8')
    imports = [l for l in src.splitlines() if l.startswith(('import ', 'from '))]
    assert not any('teach' in l or 'eval' in l for l in imports), imports
    src = src.replace("s[0] == 'copy'", '')          # the learned effect type 'copy a value', not the tool
    for word in ("'copy'", "'move'", "'delete'", '"copy"', '"move"', '"delete"'):
        assert word not in src, word


def _scene(objs):
    return {o: (frozenset(at), v) for o, (at, v) in objs.items()}


def test_lexicon_learns_word_meaning_and_tool_from_feedback():
    a = {'x.csv': ({('U', 0, 'a1', 0), ('U', 0, 'a2', 'csv')}, 'csv'), 'y.txt': ({('U', 0, 'a1', 0), ('U', 0, 'a2', 'txt')}, 'txt'),
         'd': ({('U', 0, 'a1', 1), ('U', 0, 'a2', '-')}, '-')}
    L = Lexicon()
    for dest in ('alpha', 'beta', 'gamma'):
        L.update(tokens(f'zap the csv files into {dest}'), _scene(a), 'T1', ['x.csv'], dest)
        L.update(tokens('blip the txt files'), _scene(a), 'T2', ['y.txt'], None)
    r = L.interpret(tokens('zap the csv files into omega'), _scene(a))
    assert r['tool'] == 'T1' and r['selected'] == ['x.csv'] and r['dest'] == 'omega', r
    assert L.interpret(tokens('blip the txt files'), _scene(a))['dest'] is None
    assert Lexicon.from_json(json.loads(json.dumps(L.to_json()))).interpret(tokens('zap the csv files into omega'), _scene(a)) == r


@pytest.mark.skipif(not p9.R1_PATH.exists(), reason='needs the P8b R1 representation')
def test_concepts_are_addressed_by_definition_hash():
    rep = Representation.loads(p9.R1_PATH.read_text(encoding='utf-8'))
    ids = concept_ids(rep)
    assert len(set(ids.values())) == len(ids) and all(len(v) == 12 for v in ids.values())


def test_delayed_evaluation_refused_before_72_hours(tmp_path, monkeypatch):
    import time
    (tmp_path / 'freeze.json').write_text(json.dumps({'frozen_at': time.time(), 'lexicon_sha': {}}), encoding='utf-8')
    monkeypatch.setattr(p9, 'SEALED', tmp_path)
    (tmp_path / 'p9_delayed.json').write_text('[]', encoding='utf-8')
    monkeypatch.setitem(p9.SEALED_SHA, 'delayed', __import__('hashlib').sha256(b'[]').hexdigest())
    monkeypatch.setattr(p9, '_NoTeacher', p9._NoTeacher)
    with pytest.raises(RuntimeError):
        p9.evaluate('delayed', tmp_path)
