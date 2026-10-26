"""The real-person interface: the learner's questions wait for answers from the screen; what it learns is recorded with
source 'human' (apart from the program tutor), and a name taught in one session is used alone on new cards later."""
import json
import time

from atanor_os.ui.teach_server import Session, classify


def answer(sess, fn, timeout=10):
    t0 = time.time()
    while sess.person.pending is None:
        assert time.time() - t0 < timeout, 'no question came'
        time.sleep(0.01)
    p = sess.person.pending
    sess.person.answers.put(fn(p))
    while sess.person.pending is p:
        time.sleep(0.01)


def finish(sess):
    sess.job.join(10)
    assert not sess.job.is_alive()


def test_a_lesson_from_the_screen_is_reused_alone_in_a_later_session(tmp_path):
    sess = Session(tmp_path / 'sb', seed=1)
    cards = sess.home._read()['cards']
    marks = {}
    for c, a in cards.items():
        marks.setdefault(a['mark'], []).append(c)
    mark = next(m for m, cs in marks.items() if len(cs) >= 2)
    meant = set(marks[mark])
    assert sess.start('teach')
    answer(sess, lambda p: {'objects': sorted(meant)[:2]})
    while True:                                            # contrast questions until the demonstration is asked for
        while sess.person.pending is None:
            time.sleep(0.01)
        if sess.person.pending['kind'] != 'contrast':
            break
        answer(sess, lambda p: {'yes': p['object'] in meant})
    target = next(c for c in sorted(meant) if cards[c]['tray'] != 't3')
    answer(sess, lambda p: {'tool': 'lodge', 'args': [target, 't3']})
    answer(sess, lambda p: {'ok': True})
    answer(sess, lambda p: {'selection': 'mip', 'action': 'dax'})
    finish(sess)
    sess.new_session()
    assert sess.start('command', text='dax mip', alone=True)
    for _ in range(50):
        if sess.person.pending or not sess.job.is_alive():
            break
        time.sleep(0.02)
    if sess.person.pending:
        answer(sess, lambda p: {'ok': True})
    finish(sess)
    rows = [json.loads(l) for l in (tmp_path / 'sb' / 'log.jsonl').read_text(encoding='utf-8').splitlines()]
    cmd = [r for r in rows if r['event'] == 'command'][-1]
    assert cmd['taught_words']['mip']['session'] == 1 and cmd['outcome'] in ('success', 'held')
    events = [json.loads(l) for l in (tmp_path / 'sb' / 'mind' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert events and all(e['source'] == 'human' for e in events)
    assert all(c['source'] == 'human' for c in sess.memory_view())


def test_failures_are_only_classified():
    assert classify({'outcome': 'held', 'why': 'ambiguous generalization'}).startswith('safety hold')
    assert classify({'outcome': 'wrong', 'reason': 'result'}).startswith('tool model')
    assert classify({'outcome': 'success'}) is None
