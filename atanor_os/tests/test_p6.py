"""P6 agent and judge, offline: a fake web stands in for the internet."""
import pytest

from atanor_os.agent.autonomy import Agent, norm
from atanor_os.agent.reader import Lexicon, NameReader, candidates
from atanor_os.core.journal import Journal
from atanor_os.eval.p6 import OracleAgent, fs_model, judge, make_task

SNAP = {'formats': {'png': {'label': 'Portable Network Graphics', 'aliases': ['PNG']},
                    'gif': {'label': 'Graphics Interchange Format', 'aliases': []},
                    'flac': {'label': 'Free Lossless Audio Codec', 'aliases': []}}}
PAGES = {
    'png': 'Portable Network Graphics (PNG) is a raster-graphics file format. Files use the .png extension.',
    'gif': 'The Graphics Interchange Format (GIF) is a bitmap image format. Extension .gif is common.',
    'flac': 'Free Lossless Audio Codec (FLAC) is an audio coding format. Files end in .flac.',
}


class FakeWeb:
    def __init__(self, conflict=()):
        self.conflict, self.requests = set(conflict), []

    def search(self, service, q):
        self.requests.append(('search', service, q))
        ext = q.lower().replace('.', ' ').split()[0]
        return {'ok': True, 'results': [f'https://a.test/{ext}', f'https://b.test/{ext}']} if ext in PAGES else {'ok': True, 'results': []}

    def open(self, url):
        self.requests.append(('open', url))
        host, ext = url.split('/')[2], url.rsplit('/', 1)[1]
        text = PAGES[ext]
        if ext in self.conflict and host == 'b.test':
            text = text.replace(SNAP['formats'][ext]['label'], 'Totally Different Name')
        return {'ok': True, 'url': url, 'text': text, 'links': [], 'sha256': 'x'}


def trained_reader():
    r = NameReader()
    for ext, text in PAGES.items():
        for _ in range(3):
            r.train(text, ext, ext, lambda n, e=ext: norm(n) == norm(SNAP['formats'][e]['label']))
    return r


def lexicon():
    lex = Lexicon(('folder', 'rename', 'copy'))
    for s, f in [('Put every file into a folder named after its format', 'folder'), ('Move each file into a folder for its format', 'folder'),
                 ('Rename each file to its format name', 'rename'), ('Give each file the format name as new name', 'rename'),
                 ('Copy each file into a folder for its format and keep the original', 'copy'), ('Make a copy of each file in a folder', 'copy')]:
        lex.learn(s, f)
    return lex


def test_candidates_find_expanded_name():
    names = [n for n, f in candidates(PAGES['png'], 'png') if f['paren_ext']]
    assert names == ['Portable Network Graphics']


@pytest.mark.fs
def test_agent_reads_compares_acts_and_stops(tmp_path):
    exts = ['png', 'gif', 'flac']
    sents = {'folder': ['Put every file into a folder named after its format'], 'rename': ['Rename each file to its format name'],
             'copy': ['Copy each file into a folder for its format and keep the original']}
    fs = fs_model()
    for idx in range(3):
        ws, task = make_task(idx, 'dev', tmp_path / f'w{idx}', SNAP, exts, sents, 1)
        a = Agent(fs, FakeWeb(), 'F', {}, lexicon(), trained_reader())
        res = a.run(task['sentence'], ws, Journal(tmp_path / f'j{idx}.sqlite'))
        v = judge(ws, task, SNAP, res)
        assert res['form'] == task['form'] and v['completed'], (task['form'], res, v)
        assert any(t['action'] == 'experiment' for t in a.trace) and any(t['action'] == 'compare' for t in a.trace)
    ws, task = make_task(0, 'dev', tmp_path / 'imp', SNAP, exts, sents, 1, impossible=True)
    a = Agent(fs, FakeWeb(conflict={'gif'}), 'F', {}, lexicon(), trained_reader())
    res = a.run(task['sentence'], ws, Journal(tmp_path / 'ji.sqlite'))
    v = judge(ws, task, SNAP, res)
    assert v['impossible_correct'], (res, v)
    statuses = {f: d['status'] for f, d in res['files'].items()}
    assert any(s in ('contradiction', 'single_source', 'done') for s in statuses.values())


@pytest.mark.fs
def test_no_web_condition_stops_and_oracle_completes(tmp_path):
    exts = ['png', 'gif', 'flac']
    sents = {f: ['Put every file into a folder named after its format'] for f in ('folder', 'rename', 'copy')}
    ws, task = make_task(0, 'dev', tmp_path / 'n', SNAP, exts, sents, 1)
    a = Agent(fs_model(), None, 'N', {}, lexicon(), trained_reader())
    res = a.run(task['sentence'], ws, Journal(tmp_path / 'jn.sqlite'))
    assert not judge(ws, task, SNAP, res)['completed'] and all(d['status'] == 'no_evidence' for d in res['files'].values())
    ws, task = make_task(0, 'dev', tmp_path / 'o', SNAP, exts, sents, 1)
    o = OracleAgent(fs_model(), SNAP, task['form'])
    res = o.run(task['sentence'], ws, Journal(tmp_path / 'jo.sqlite'))
    assert judge(ws, task, SNAP, res)['completed'], res
