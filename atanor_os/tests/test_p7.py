"""P7: the language model is reachable only through agent/perception.py, its candidates are quote-verified
by ATANOR, every call is logged, and adoption still needs two agreeing pages (ATANOR's rule)."""
import json
from pathlib import Path

import pytest

from atanor_os.agent.autonomy import Agent
from atanor_os.agent.perception import Perception
from atanor_os.core.journal import Journal
from atanor_os.eval.p6 import fs_model, judge, make_task
from atanor_os.tests.test_p6 import SNAP, FakeWeb, lexicon, trained_reader

PKG = Path(__file__).resolve().parents[1]


class StubModel:
    """Answers like a model would; 'lie' makes it return a quote that is not in the excerpt."""
    model, digest = 'stub', 'none'

    def __init__(self, lie=False):
        self.lie, self.prompts = lie, []

    def complete(self, prompt):
        self.prompts.append(prompt)
        excerpt = prompt.split('"""')[1]
        for name in ('Portable Network Graphics', 'Graphics Interchange Format', 'Free Lossless Audio Codec'):
            if name in excerpt:
                q = name + ' (invented quote)' if self.lie else excerpt[excerpt.index(name):excerpt.index(name) + len(name) + 10]
                return json.dumps({'candidates': [{'value': name, 'quote': q}]}), {'prompt_tokens': 1, 'output_tokens': 1}
        return json.dumps({'candidates': []}), {}


def test_only_perception_module_reaches_a_model():
    for folder in ('agent', 'core', 'world'):
        for p in (PKG / folder).rglob('*.py'):
            src = p.read_text(encoding='utf-8')
            if p.name != 'perception.py':
                assert '11434' not in src and '/api/generate' not in src, p.name


def test_quotes_are_verified_and_calls_logged(tmp_path):
    log = tmp_path / 'calls.jsonl'
    ok = Perception(StubModel(), log).extract('Portable Network Graphics (PNG) is a format.', 'png')
    assert ok and ok[0]['value'] == 'Portable Network Graphics'
    bad = Perception(StubModel(lie=True), log).extract('Portable Network Graphics (PNG) is a format.', 'png')
    assert bad == []                                               # invented quote -> rejected by ATANOR
    rows = [json.loads(l) for l in log.read_text(encoding='utf-8').splitlines()]
    assert len(rows) == 2 and rows[1]['rejected'] and all(r['excerpt_sha256'] and r['prompt_version'] for r in rows)


@pytest.mark.fs
def test_model_on_agent_still_decides_by_agreement(tmp_path):
    stub = StubModel()
    per = Perception(stub, tmp_path / 'calls.jsonl')
    sents = {'folder': ['Put every file into a folder named after its format'], 'rename': ['Rename each file to its format name'],
             'copy': ['Copy each file into a folder for its format and keep the original']}
    ws, task = make_task(0, 'dev', tmp_path / 'w', SNAP, ['png', 'gif', 'flac'], sents, 1)
    a = Agent(fs_model(), FakeWeb(), 'F', {}, lexicon(), trained_reader(), perception=per)
    res = a.run(task['sentence'], ws, Journal(tmp_path / 'j.sqlite'))
    assert judge(ws, task, SNAP, res)['completed'], res
    assert per.calls > 0 and all('Question:' in p for p in stub.prompts)       # fixed prompt, no goal text sent
    assert not any(task['sentence'] in p for p in stub.prompts)
    assert any(t['action'] == 'compare' and len(t['sources']) >= 2 for t in a.trace)
