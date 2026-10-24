"""P8: concept learner sees only anonymous raw observations; concepts are numbered, invented from
recurring rule parts, reused across tools, survive a bounded serialization and a revision."""
import json
from pathlib import Path

import pytest

from atanor_os.agent.concepts import ConceptModel, Representation, atoms, build, concept_use, revise
from atanor_os.eval.explore import explore

PKG = Path(__file__).resolve().parents[1]


def test_concept_learner_uses_no_human_concept_names():
    src = (PKG / 'agent' / 'concepts.py').read_text(encoding='utf-8')
    for word in ("'kind'", "'parent_kind'", "'same_content'", "'hash'", "'ext'", "'filter'", "'panel'", "'dir'", "'file'"):
        assert word not in src, word


def test_structural_atoms_are_raw():
    st = {'a': {'kind': 'dir', 'ext': '-', 'hash': '-', 'parent_kind': 'dir'},
          'a/b.txt': {'kind': 'absent', 'ext': 'txt', 'hash': '-', 'parent_kind': 'dir'}}
    at = atoms('fs', st, ('a/b.txt',))
    assert ('S', 0, 'a1', 1) in at and ('U', 0, 'a0', 0) in at and not any('kind' in map(str, a) for a in at)


@pytest.mark.fs
def test_build_bounded_revise_and_predict(tmp_path):
    es = explore(1, 300, tmp_path / 'x', policy='contrast')
    e1, e2 = es[:150], es[150:]
    r1 = build('fs', e1, 8192)
    assert r1.size() <= 8192 and r1.dictionary, r1.to_json()
    r2, change = revise(r1, e2, 8192)
    assert r2.size() <= 8192
    rep = Representation.loads(r2.dumps())                               # what survives a restart
    m = ConceptModel(rep)
    st = {'box': {'kind': 'dir', 'ext': '-', 'hash': '-', 'parent_kind': 'dir'},
          'box/new.txt': {'kind': 'absent', 'ext': 'txt', 'hash': '-', 'parent_kind': 'dir'}}
    post, status = m.predict(st, 'mkdir', ('box/new.txt',))
    assert status == 'learned' and post['box/new.txt']['kind'] == 'dir', (status, rep.rules.get('mkdir'))
    use = concept_use(rep.rules)
    assert any(len(t) >= 2 for t in use.values()), use                  # some invented concept serves >= 2 tools
