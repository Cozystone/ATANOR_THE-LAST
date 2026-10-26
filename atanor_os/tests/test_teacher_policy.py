"""The synthetic teacher teaches only through the person's interface: it may read ATANOR's memory, never write it or
call the learner; its experience is recorded as 'synthetic_teacher', apart from human, pilot and program."""
import json
import re
from pathlib import Path

from atanor_os.teach.teacher_policy import run

SRC = (Path(__file__).resolve().parents[1] / 'teach' / 'teacher_policy.py').read_text(encoding='utf-8')


def test_the_teacher_never_writes_to_the_learner():
    code = re.sub(r'""".*?"""', '', SRC, flags=re.S)
    for forbidden in ('Grounder', '.bind(', 'name_phrase', 'learn_selection', 'learn_action', 'claims.add', '.revise(',
                      '.counter(', '.propose(', 'events.append', 'graph.link', '.obey(', '.reply('):
        assert forbidden not in code, forbidden
    assert 'Session(' in code                              # the person's interface


def test_a_short_course_is_recorded_as_the_teachers_with_reasons(tmp_path):
    t = run(tmp_path / 'c', seed=1, n_sessions=5, drift_from=None)
    root = tmp_path / 'c'
    events = [json.loads(l) for l in (root / 'mind' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert events and {e['source'] for e in events} == {'synthetic_teacher'}
    tl = [json.loads(l) for l in (root / 'teacher_log.jsonl').read_text(encoding='utf-8').splitlines()]
    assert tl and all(r['policy'] and r['reason'] and 'truth' in r and len(r['events']) == 2 for r in tl)
    assert {r['reason'] for r in tl} & {'new', 'combo', 'away', 'undecided', 'recheck'}
    assert json.loads((root / 'names.json').read_text(encoding='utf-8'))['sel']
