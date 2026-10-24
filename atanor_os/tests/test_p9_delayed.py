"""P9 delayed runner: refuses early runs without consuming the attempt, never repeats an attempt, detects code changes."""
import json
import time

import pytest

from atanor_os.eval import p9_delayed as d


@pytest.fixture
def tmp_out(tmp_path, monkeypatch):
    monkeypatch.setattr(d, 'FREEZE', tmp_path / 'delayed_freeze.json')
    monkeypatch.setattr(d, 'STATUS', tmp_path / 'delayed_status.json')
    monkeypatch.setattr(d, 'REFUSALS', tmp_path / 'delayed_refusals.json')
    per, total = d.code_hashes()
    d.FREEZE.write_text(json.dumps({'code_sha': total, 'code_files': per, 'lexicon_sha': {}, 'r1_sha': '',
                                    'lexicon_frozen_at': time.time(), 'min_hours_since_lexicon_freeze': 72}), encoding='utf-8')
    return tmp_path


def test_early_run_is_refused_without_consuming_the_attempt(tmp_out):
    with pytest.raises(SystemExit, match='too early'):
        d.run()
    assert not d.STATUS.exists() and json.loads(d.REFUSALS.read_text(encoding='utf-8'))


def test_an_attempt_is_never_repeated(tmp_out):
    d.STATUS.write_text('{"state": "failed"}', encoding='utf-8')
    with pytest.raises(SystemExit, match='never repeated'):
        d.run()


def test_code_hash_covers_the_evaluation_code():
    per, total = d.code_hashes()
    assert 'eval/p9.py' in per and 'eval/p9_delayed.py' in per and 'agent/language.py' in per and len(total) == 64
