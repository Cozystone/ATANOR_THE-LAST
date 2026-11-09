"""H_LEARNED_MEMORY_PLAN.md: the learned memory's contracts that broke once (padded layout) or must never break (no words
of a body in the code; a cipher keeps structure; an episode's query is answered from itself)."""
import random

import torch

from atanor_os.memory import episodic, relational as R


def _scene(body, tool, args, before, after, ok=True):
    return R.Scene(body, tool, args, before, after, 'ok' if ok else 'failed')


def test_targets_point_to_self_copy_blank_or_bucket():
    s = _scene('x', 't', ['a', 'b'],
               {'a': {'p': 'u', 'q': '-'}, 'b': {'p': 'v', 'q': 'w'}},
               {'a': {'p': 'v', 'q': 'w'}, 'b': {'p': 'v', 'q': '-'}})
    n = len(s.toks)                                         # a.p a.q b.p b.q
    assert s.tg[0] == 2                                     # a.p took b.p's value: copied from that token
    assert s.tg[1] == 3                                     # a.q took b.q's value
    assert s.tg[2] == 2                                     # b.p unchanged: itself
    assert s.tg[3] == n                                     # b.q blanked
    s2 = _scene('x', 't', ['a'], {'a': {'p': 'u'}}, {'a': {'p': 'zz'}})
    assert s2.tg[0] == 1 + 1 + R.h('zz', R.N_BUCKET)        # a value not in the scene: its bucket


def test_loss_and_predict_agree_on_the_padded_layout():
    torch.manual_seed(0)
    short = _scene('x', 't', ['a'], {'a': {'p': 'u', 'q': 'r'}}, {'a': {'p': 'u', 'q': '-'}})
    long = _scene('x', 't', ['a', 'b'], {'a': {'p': 'u', 'q': 'r'}, 'b': {'p': 's', 'q': 'r'}}, {'a': {'p': 's', 'q': 'r'}, 'b': {'p': 's', 'q': 'r'}})
    m = R.Memory(d=32, layers=1, heads=2)
    loss = m.loss([short, long], 'cpu')
    assert torch.isfinite(loss) and loss.item() < 50       # the 1e8 loss came from a target on a masked column
    R.train(m, [short, long] * 8, 'cpu', epochs=60, batch=4)
    assert R.score(m, [short, long], 'cpu', 0.0) == {'right': 2}


def test_cipher_keeps_structure_and_removes_every_word():
    s = _scene('x', 'dip', ['a', 'b'], {'a': {'hue': 'ecru', 'st': 'dry'}, 'b': {'hue': 'indigo', 'st': '4'}},
               {'a': {'hue': 'indigo', 'st': 'wet'}, 'b': {'hue': 'indigo', 'st': '3'}})
    c = R.cipher([s], random.Random(1))[0]
    words = {w for _, k, v in s.toks for w in (k, v) if w != '-' and not w.isdigit()}
    cwords = {w for _, k, v in c.toks for w in (k, v) if w != '-' and not w.isdigit()}
    assert not (words & cwords) and c.tg == s.tg and torch.equal(c.X, s.X) and c.tool != s.tool
    assert c.toks[3][2] == '4'                              # digits stay


def test_episode_answers_the_query_from_its_own_tokens():
    torch.manual_seed(0)
    ex = [_scene('x', 't', ['a', 'b'], {'a': {'p': 'u%d' % i, 'q': '-'}, 'b': {'p': 'v%d' % i, 'q': 'w'}},
                 {'a': {'p': 'v%d' % i, 'q': 'w'}, 'b': {'p': 'v%d' % i, 'q': 'w'}}) for i in range(6)]
    e = episodic.Episode(ex[:3], ex[3])
    assert e.q0 + e.n_q == len(e.rows) and e.n_q == 4
    m = episodic.Episodic(d=32, layers=1, heads=2)
    assert torch.isfinite(m.loss([e], 'cpu'))
    episodic.train(m, ex, 'cpu', steps=150, k=3, batch=8, lr=3e-3)
    r = episodic.score(m, ex[:5], [ex[5]], 'cpu', 3, random.Random(0))
    assert r == {'right': 1}                                # copy a.p <- b.p, a.q <- b.q: readable from the examples alone
