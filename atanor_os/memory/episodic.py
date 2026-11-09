"""H_LEARNED_MEMORY_PLAN.md, second form: learning to use examples. The model sees, in one input, k EXAMPLES of an action
(each argument's observations before and after, and the body's answer) and one QUERY (before only), all from the same
body and tool, and answers the query. It is trained on five bodies with episodes drawn that way, and meets the sixth
body with k of its course experiences as examples and no weight update. What it can carry across bodies is therefore
only HOW to read examples: which token to copy from, what stays, what blanks, how the answer follows from the start.
Words are hashed as in relational.py; in a new body they are new, so only their equalities within the episode help.
"""
import math
import random
from collections import Counter, defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F

from .relational import BLANK, MAX_ARGS, N_BUCKET, N_HASH, RESP, Scene, cipher, h

ROLE = {'ex_before': 0, 'ex_after': 1, 'query': 2}


def tok_rows(scene, role, ex_id):
    """Tokens of one scene in a role: (role, ex_id, arg, attr, value, same-attr-equal-to-other-arg, blank)."""
    rows = []
    toks = scene.toks
    if role == 'ex_after':
        n = len(toks)
        vals = []
        for t in scene.tg:
            vals.append(toks[t][2] if t < n else (BLANK if t == n else f'#{t - n - 1}'))
        toks = [(i, k, v) for (i, k, _), v in zip(scene.toks, vals)]
    for p, (i, k, v) in enumerate(toks):
        eq_other = any(i2 != i and k2 == k and v2 == v for (i2, k2, v2) in toks) and v != BLANK
        eq_same = any(q != p and i2 == i and v2 == v for q, (i2, k2, v2) in enumerate(toks)) and v != BLANK
        rows.append((role, ex_id, i, k, v, eq_other, eq_same, p))
    return rows


class Episode:
    """k example scenes (with outcomes) and one query scene; the query's targets, if known, for the loss."""
    def __init__(self, examples, query):
        self.examples, self.query = examples, query
        rows = []
        for j, ex in enumerate(examples):
            rows += tok_rows(ex, 'ex_before', j)
            rows += tok_rows(ex, 'ex_after', j)
            rows.append(('ex_resp', j, 0, '', RESP[ex.resp], False, False, -1))
        self.q0 = len(rows)
        rows += tok_rows(query, 'query', len(examples))
        self.rows = rows
        self.n_q = len(query.toks)
        # a value not among the query's own tokens may still be in the episode (an example's state after): the answer may
        # point there. Else it is a bucket. -> per query token: a row index in the whole episode, or None (bucket/blank)
        self.src = []
        n = self.n_q
        for p, t in enumerate(query.tg):
            if t < n:
                self.src.append(self.q0 + t)
            elif t == n:
                self.src.append(None)
            else:
                want = self._new_value(p, examples)
                k_attr = query.toks[p][1]
                cands = [i for i, r in enumerate(rows[:self.q0]) if r[0] == 'ex_after' and r[4] == want and r[3] == k_attr] or                         [i for i, r in enumerate(rows[:self.q0]) if r[0] in ('ex_after', 'ex_before') and r[4] == want]
                self.src.append(cands[0] if cands else None)

    def _new_value(self, p, examples):
        """The query token's true value after, when it is not in the query (known only when the query has a truth)."""
        return getattr(self.query, 'after_values', None) and self.query.after_values[p]

    def query_new_value(self, t):
        return getattr(self.query, 'after_values', None) and None


class Episodic(nn.Module):
    def __init__(self, d=160, layers=4, heads=8, use_pos=False):
        super().__init__()
        self.use_pos = use_pos
        self.word = nn.Embedding(N_HASH, 32)
        self.role = nn.Embedding(4, 16)
        self.ex = nn.Embedding(34, 16)
        self.arg = nn.Embedding(MAX_ARGS, 8)
        self.pos = nn.Embedding(64, 8)
        self.inp = nn.Linear(32 * 2 + 16 + 16 + 8 + 8 + 2, d)
        enc = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.q = nn.Linear(d, d)
        self.k = nn.Linear(d, d)
        self.blank = nn.Linear(d, 1)
        self.bucket = nn.Linear(d, N_BUCKET)
        self.resp = nn.Linear(d, len(RESP))
        self.d = d

    def encode(self, eps, device):
        B = len(eps)
        n = max(len(e.rows) for e in eps)
        names = torch.zeros(B, n, dtype=torch.long, device=device)
        vals = torch.zeros(B, n, dtype=torch.long, device=device)
        role = torch.zeros(B, n, dtype=torch.long, device=device)
        exid = torch.zeros(B, n, dtype=torch.long, device=device)
        arg = torch.zeros(B, n, dtype=torch.long, device=device)
        pos = torch.zeros(B, n, dtype=torch.long, device=device)
        flags = torch.zeros(B, n, 2, device=device)
        mask = torch.ones(B, n, dtype=torch.bool, device=device)
        for b, e in enumerate(eps):
            m = len(e.rows)
            names[b, :m] = torch.tensor([h(r[3]) for r in e.rows], device=device)
            vals[b, :m] = torch.tensor([h(r[4]) for r in e.rows], device=device)
            role[b, :m] = torch.tensor([ROLE.get(r[0], 3) for r in e.rows], device=device)
            exid[b, :m] = torch.tensor([min(r[1], 33) for r in e.rows], device=device)
            arg[b, :m] = torch.tensor([r[2] for r in e.rows], device=device)
            if self.use_pos:                            # off by default: a token's place in its object let the model memorise
                pos[b, :m] = torch.tensor([min(max(r[7], 0), 63) for r in e.rows], device=device)   # per-body patterns by position
            flags[b, :m, 0] = torch.tensor([float(r[5]) for r in e.rows], device=device)
            flags[b, :m, 1] = torch.tensor([float(r[6]) for r in e.rows], device=device)
            mask[b, :m] = False
        z = torch.cat([self.word(names), self.word(vals), self.role(role), self.ex(exid), self.arg(arg), self.pos(pos), flags], -1)
        return self.enc(self.inp(z), src_key_padding_mask=mask), mask

    def forward(self, eps, device):
        z, mask = self.encode(eps, device)
        B, n, _ = z.shape
        att = torch.einsum('bqd,bkd->bqk', self.q(z), self.k(z)) / math.sqrt(self.d)
        att = att.masked_fill(mask[:, None, :], -1e9)
        return z, att, mask

    def _query_slices(self, eps):
        return [(e.q0, e.q0 + e.n_q) for e in eps]

    def loss(self, eps, device):
        z, att, mask = self(eps, device)
        B, n, _ = att.shape
        tot, cnt = 0.0, 0
        rl, rt = [], []
        for b, e in enumerate(eps):
            a, c = e.q0, e.q0 + e.n_q
            qz = z[b, a:c]                                  # [n_q, d]
            m = len(e.rows)
            pointer = att[b, a:c, :m]                       # a query token's value after: from any token of the episode
            logits = torch.cat([pointer, self.blank(qz), self.bucket(qz)], -1)
            tg = torch.tensor([s_ if s_ is not None else (m if t == e.n_q else m + 1 + (t - e.n_q - 1)) for s_, t in zip(e.src, e.query.tg)], device=device)
            tot = tot + F.cross_entropy(logits, tg, reduction='sum')
            cnt += e.n_q
            rl.append(qz.mean(0))
            rt.append(e.query.resp)
        lr = F.cross_entropy(self.resp(torch.stack(rl)), torch.tensor(rt, device=device))
        return tot / max(cnt, 1) + lr

    @torch.no_grad()
    def predict(self, eps, device, tau=0.0):
        self.eval()
        z, att, mask = self(eps, device)
        out = []
        for b, e in enumerate(eps):
            a, c = e.q0, e.q0 + e.n_q
            qz = z[b, a:c]
            m = len(e.rows)
            logits = torch.cat([att[b, a:c, :m], self.blank(qz), self.bucket(qz)], -1)
            P = logits.softmax(-1)
            vals, conf = [], []
            n = e.n_q
            for p in range(n):
                row = P[p, :m].tolist() + [P[p, m].item(), P[p, m + 1:].max().item()]
                j = max(range(len(row)), key=row.__getitem__)
                conf.append(row[j])
                vals.append(e.rows[j][4] if j < m else (BLANK if j == m else ('<bucket>', int(P[p, m + 1:].argmax()))))
            pr = self.resp(qz.mean(0, keepdim=True)).softmax(-1)[0]
            ans = RESP[int(pr.argmax())]
            cmin = min(conf + [pr.max().item()])
            out.append((vals if cmin >= tau else None, ans if cmin >= tau else None, cmin))
        return out


def by_tool(scenes):
    d = defaultdict(list)
    for s in scenes:
        d[(s.body, s.tool, len(s.args))].append(s)
    return d


def episodes(scenes, rng, k, n, augment=False):
    """n training episodes: k examples and a query of one body and tool. augment: every word of the episode replaced by a
    nonsense word drawn afresh for that episode, so words carry nothing between episodes and only the equalities inside
    the episode can be used - the form the model must have in a body whose words it has never seen."""
    pool = {key: v for key, v in by_tool(scenes).items() if len(v) >= 2}
    keys = list(pool)
    out = []
    while len(out) < n:
        key = rng.choice(keys)
        v = pool[key]
        kk = min(rng.randint(1, k), len(v) - 1)
        q = rng.choice(v)
        ex = rng.sample([s for s in v if s is not q], kk)
        if augment:
            c = cipher(ex + [q], rng)
            ex, q = c[:-1], c[-1]
        out.append(Episode(ex, q))
    return out


def train(model, scenes, device, steps=3000, k=8, batch=32, lr=3e-4, seed=0, log=None, augment=False):
    rng = random.Random(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    model.to(device)
    for step in range(steps):
        model.train()
        eps = episodes(scenes, rng, k, batch, augment)
        loss = model.loss(eps, device)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        if log and step % 200 == 0:
            log(f'step {step} loss {loss.item():.4f}')
    return model


def right(e, vals, ans):
    from .relational import right as r
    return r(e.query, vals, ans)


def score(model, shots, queries, device, k, rng, tau=0.0):
    """Queries of the new body answered with k of its course experiences as examples (same tool when there are any)."""
    pool = by_tool(shots)
    c = Counter()
    eps = []
    for q in queries:
        same = pool.get((q.body, q.tool, len(q.args)), [])
        ex = same if len(same) <= k else rng.sample(same, k)
        if not ex:
            c['never_seen'] += 1
            continue
        eps.append(Episode(ex, q))
    for i in range(0, len(eps), 64):
        bs = eps[i:i + 64]
        for e, (vals, ans, conf) in zip(bs, model.predict(bs, device, tau)):
            c[right(e, vals, ans)] += 1
    return dict(c)
