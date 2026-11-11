"""P_KNOW_LIFE_PLAN.md: what the learner knows before trying, from the reader trained on other authors' worlds
(O_KNOW_COST_PLAN.md). Examples are only this body's own experiences in the learner's store (the course, its practice,
its work); nothing else is read. Used in two places of the learner next_know: practice skips a call the reader is sure
of, and at work a call the symbolic mind does not know is predicted by the reader when it is sure, before any lab test.
Reader: ATANOR_KNOW_READER (default probe-work/authors/reader-all5.pt).
"""
import json
import os
import random

TAU = float(os.environ.get('ATANOR_KNOW_TAU', '0.9'))    # R_GATE_PLAN.md / T_LIVED_PLAN.md: 0.9 with the gate
K = 10
GATE = float(os.environ.get('ATANOR_KNOW_GATE', '0.8'))  # R_GATE_PLAN.md: answer only on tools read at least this well here


def available():
    return os.environ.get('ATANOR_KNOW_KIND') == 'law' or os.path.exists(os.environ.get('ATANOR_KNOW_READER', DEFAULT))
DEFAULT = 'D:/ATANOR-experiments/probe-work/authors/reader-all5.pt'


class Knower:
    _model = None
    _trust = {}                                            # (body, tool, nargs, size band) -> share right in self-check

    def __init__(self, store, body, seed=0):
        import torch
        from .hybrid import reader
        if Knower._model is None:
            Knower.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            Knower._model = reader(os.environ.get('ATANOR_KNOW_READER', DEFAULT), Knower.device)
        self.store, self.body = store, body
        self.rng = random.Random(f'know-{body}-{seed}')
        self.seen, self.scenes, self.memo = 0, [], {}
        self.counts = {'asked': 0, 'sure': 0}

    def _sync(self):
        from .relational import scene_of
        items = self.store.items
        for e in items[self.seen:]:
            if e.get('action') and e.get('body', self.body) == self.body and isinstance(e.get('before'), dict) \
                    and isinstance(e.get('after'), dict) and e.get('response') is not None:
                try:
                    self.scenes.append(scene_of(dict(e, body=self.body)))
                except Exception:
                    pass
        self.seen = len(items)

    def _acc(self, tool, nargs, same):
        """Leave-one-out on this body's own experiences of this tool (up to 20 probes, K examples each): share right."""
        from .episodic import Episode, right
        tkey = (self.body, tool, nargs, len(same) // 10)
        if tkey not in Knower._trust:
            if len(same) < 3:
                Knower._trust[tkey] = 0.0
            else:
                rng = random.Random(f'gate-{self.body}-{tool}-{len(same) // 10}')
                probe = same if len(same) <= 20 else rng.sample(same, 20)
                eps = []
                for q in probe:
                    rest = [x for x in same if x is not q]
                    eps.append(Episode(rest if len(rest) <= K else rng.sample(rest, K), q))
                got = [right(e, v, a) == 'right' for e, (v, a, c) in zip(eps, Knower._model.predict(eps, Knower.device, 0.0))]
                Knower._trust[tkey] = sum(got) / len(got)
        return Knower._trust[tkey]

    def predict(self, tool, args, before):
        """-> an outcome dict as the symbolic mind gives ({('r',): answer, (i, attr): value after}) when the reader is sure,
        else None. before: list of per-argument dicts."""
        from .episodic import Episode
        from .relational import RESP, Scene
        if not all(isinstance(b, dict) and b for b in before):
            return None
        self._sync()
        same = [s for s in self.scenes if s.tool == tool and len(s.args) == len(args)]
        if not same:
            return None
        if GATE > 0 and self._acc(tool, len(args), same) < GATE:
            return None
        key = (tool, tuple(args), json.dumps(before, sort_keys=True, default=str), len(same))
        if key not in self.memo:
            self.counts['asked'] += 1
            ex = same if len(same) <= K else self.rng.sample(same, K)
            q = Scene(self.body, tool, list(args), dict(zip(args, before)))
            vals, ans, conf = Knower._model.predict([Episode(ex, q)], Knower.device, 0.0)[0]
            y = None
            if conf >= TAU and vals is not None and not any(isinstance(v, tuple) for v in vals) and ans in RESP:
                y = {('r',): ans}
                for (i, k, _), v in zip(q.toks, vals):
                    y[(i, k)] = str(v)
                self.counts['sure'] += 1
            self.memo[key] = y
            if os.environ.get('ATANOR_KNOW_LOG'):            # development diagnosis only
                with open(os.environ['ATANOR_KNOW_LOG'], 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'body': self.body, 'tool': tool, 'n': len(same), 'conf': round(float(conf), 3), 'ans': ans,
                                        'unk': vals is None or any(isinstance(v, tuple) for v in vals)}) + chr(10))
        return self.memo[key]


def knower(store, body, seed=0):
    """the organ asked before trying: the reader (default) or, with ATANOR_KNOW_KIND=law, the law memory from the Self's
    own lived experiences (CONTINUOUS_LIFE_PLAN.md)."""
    if os.environ.get('ATANOR_KNOW_KIND') == 'law':
        from .lawknow import LawKnower
        return LawKnower(store, body, seed)
    return Knower(store, body, seed)
