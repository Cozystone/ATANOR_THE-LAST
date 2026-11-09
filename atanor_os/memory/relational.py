"""H_LEARNED_MEMORY_PLAN.md: a relational effect model over the arguments of a call.

An example is one experience: the tool, the arguments' observations before, and what was observed after plus the body's
answer. Every attribute of every argument is one token. A token carries
  word-free relational features  blank or not; equal to another attribute of the same object; equal to the same-named
                                 attribute of another argument; equal to any attribute of another argument; which argument
  hashed word embeddings         the attribute name and the value as strings, hashed into small tables (useful within a
                                 body, near random in a new one - how much the model leans on them is what it learns)
The model answers, for every token, where its value after the call comes from: itself (unchanged), another token in the
scene (copied), blank, or a value not in the scene (a hashed value bucket). And the body's answer: ok / failed / blocked.
It abstains when any of those is below tau. Nothing in here names a body, an attribute or a value.
"""
import hashlib
import json
import math
import random
from collections import Counter

import torch
import torch.nn as nn
import torch.nn.functional as F

BLANK = '-'
RESP = ('ok', 'failed', 'blocked')
N_HASH = 4096          # hashed word tables (attribute names and values share one table)
N_BUCKET = 1024        # values not in the scene
MAX_ARGS = 4


def h(s, n=N_HASH):
    return int(hashlib.blake2b(str(s).encode('utf-8'), digest_size=4).hexdigest(), 16) % n


def resp_of(e):
    r = e.get('response') or {}
    if r.get('guard') or r.get('blocked'):
        return 'blocked'
    return 'ok' if r.get('ok') else 'failed'


def tokens_of(tool, args, before):
    """-> list of tokens (arg index, attr, value) in a fixed order."""
    out = []
    for i, a in enumerate(args[:MAX_ARGS]):
        o = before.get(a) if isinstance(before, dict) else before[i]
        for k in sorted((o or {}).keys()):
            out.append((i, k, str((o or {}).get(k, BLANK))))
    return out


def features(toks):
    """Word-free relations among the tokens of one scene. -> [n, F] floats."""
    n = len(toks)
    X = torch.zeros(n, 6 + MAX_ARGS)
    for p, (i, k, v) in enumerate(toks):
        X[p, 0] = v == BLANK
        X[p, 1] = any(q != p and i2 == i and v2 == v for q, (i2, k2, v2) in enumerate(toks)) and v != BLANK
        X[p, 2] = any(i2 != i and k2 == k and v2 == v for (i2, k2, v2) in toks) and v != BLANK
        X[p, 3] = any(i2 != i and v2 == v for (i2, k2, v2) in toks) and v != BLANK
        X[p, 4] = v.isdigit()
        X[p, 5] = len(v) > 8
        X[p, 6 + i] = 1.0
    return X


def targets(toks, args, after, resp):
    """Per token: index of the source token (itself if unchanged, another if copied), n -> blank, n+1+bucket -> a value not
    in the scene. -> list[int], and the answer class."""
    n = len(toks)
    tg = []
    for p, (i, k, v) in enumerate(toks):
        a = args[i]
        o = after.get(a) if isinstance(after, dict) else after[i]
        nv = str((o or {}).get(k, BLANK))
        if nv == v:
            tg.append(p)
        elif nv == BLANK:
            tg.append(n)
        else:
            src = [q for q, (i2, k2, v2) in enumerate(toks) if v2 == nv and v2 != BLANK]
            same_name = [q for q in src if toks[q][1] == k]
            tg.append((same_name or src)[0] if src else n + 1 + h(nv, N_BUCKET))
    return tg, RESP.index(resp)


class Scene:
    __slots__ = ('tool', 'args', 'toks', 'X', 'tg', 'resp', 'body', 'after_values')

    def __init__(self, body, tool, args, before, after=None, resp=None):
        self.body, self.tool, self.args = body, tool, list(args)
        self.toks = tokens_of(tool, self.args, before)
        self.X = features(self.toks)
        if after is not None:
            self.tg, self.resp = targets(self.toks, self.args, after, resp)
            self.after_values = [str(((after.get(a_) if isinstance(after, dict) else after[i]) or {}).get(k, BLANK)) for i, k, _ in self.toks for a_ in [self.args[i]]]
        else:
            self.tg, self.resp, self.after_values = None, None, None


def scene_of(e):
    return Scene(e.get('body'), e['action']['tool'], e['action']['args'], e['before'], e['after'], resp_of(e))


def cipher(scenes, rng):
    """Every word (attribute name and value, except blank and digits) replaced consistently by a nonsense word: a control
    that keeps structure and removes every word the model might have seen."""
    table = {}

    def w(s):
        if s == BLANK or s.isdigit():
            return s
        if s not in table:
            table[s] = ''.join(rng.choice('bcdfghjklmnprstvz') + rng.choice('aeiou') for _ in range(3)) + str(len(table))
        return table[s]
    out = []
    for s in scenes:
        c = Scene.__new__(Scene)
        c.body, c.tool, c.args, c.tg, c.resp = s.body, w(s.tool), s.args, s.tg, s.resp
        c.toks = [(i, w(k), w(v)) for i, k, v in s.toks]
        c.after_values = None if s.after_values is None else [w(v) for v in s.after_values]
        c.X = s.X
        out.append(c)
    return out


class Memory(nn.Module):
    def __init__(self, d=128, layers=3, heads=4):
        super().__init__()
        self.word = nn.Embedding(N_HASH, 24)
        self.tool = nn.Embedding(N_HASH, 24)
        self.inp = nn.Linear(6 + MAX_ARGS + 24 * 3, d)
        enc = nn.TransformerEncoderLayer(d, heads, 4 * d, dropout=0.1, batch_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.q = nn.Linear(d, d)
        self.k = nn.Linear(d, d)
        self.blank = nn.Linear(d, 1)
        self.bucket = nn.Linear(d, N_BUCKET)
        self.resp = nn.Linear(d, len(RESP))
        self.d = d

    def encode(self, scenes, device):
        B = len(scenes)
        n = max(len(s.toks) for s in scenes)
        X = torch.zeros(B, n, 6 + MAX_ARGS, device=device)
        names = torch.zeros(B, n, dtype=torch.long, device=device)
        vals = torch.zeros(B, n, dtype=torch.long, device=device)
        tools = torch.zeros(B, n, dtype=torch.long, device=device)
        mask = torch.ones(B, n, dtype=torch.bool, device=device)
        for b, s in enumerate(scenes):
            m = len(s.toks)
            X[b, :m] = s.X.to(device)
            names[b, :m] = torch.tensor([h(k) for _, k, _ in s.toks], device=device)
            vals[b, :m] = torch.tensor([h(v) for _, _, v in s.toks], device=device)
            tools[b, :m] = h(s.tool)
            mask[b, :m] = False
        z = torch.cat([X, self.word(names), self.word(vals), self.tool(tools)], -1)
        z = self.enc(self.inp(z), src_key_padding_mask=mask)
        return z, mask

    def forward(self, scenes, device):
        z, mask = self.encode(scenes, device)
        att = torch.einsum('bqd,bkd->bqk', self.q(z), self.k(z)) / math.sqrt(self.d)
        att = att.masked_fill(mask[:, None, :], -1e9)
        logits = torch.cat([att, self.blank(z), self.bucket(z)], -1)      # [B, n, n + 1 + N_BUCKET]
        pooled = (z * (~mask)[..., None]).sum(1) / (~mask).sum(1, keepdim=True)
        return logits, self.resp(pooled), mask

    def loss(self, scenes, device):
        logits, r, mask = self(scenes, device)
        B, n, _ = logits.shape
        tg = torch.full((B, n), -100, dtype=torch.long, device=device)
        for b, s in enumerate(scenes):
            m = len(s.toks)                                # a scene's own layout [0..m) blank buckets -> the padded one
            tg[b, :m] = torch.tensor([t if t < m else (n if t == m else n + 1 + (t - m - 1)) for t in s.tg], device=device)
        l1 = F.cross_entropy(logits.reshape(B * n, -1), tg.reshape(-1), ignore_index=-100)
        l2 = F.cross_entropy(r, torch.tensor([s.resp for s in scenes], device=device))
        return l1 + l2

    @torch.no_grad()
    def predict(self, scenes, device, tau=0.9):
        """-> per scene: (values after per token or None if abstained, answer, min confidence)."""
        self.eval()
        logits, r, mask = self(scenes, device)
        P = logits.softmax(-1)
        pr = r.softmax(-1)
        out = []
        N = logits.shape[1]                                # the padded layout: blank at N, buckets after
        for b, s in enumerate(scenes):
            n = len(s.toks)
            conf, vals = [], []
            for p in range(n):
                row = P[b, p, :n].tolist() + [P[b, p, N].item()] + [P[b, p, N + 1:].max().item()]
                j = max(range(len(row)), key=row.__getitem__)
                conf.append(row[j])
                if j < n:
                    vals.append(s.toks[j][2])
                elif j == n:
                    vals.append(BLANK)
                else:
                    vals.append(('<bucket>', int(P[b, p, N + 1:].argmax())))
            ans = RESP[int(pr[b].argmax())]
            c = min(conf + [pr[b].max().item()])
            out.append((vals if c >= tau else None, ans if c >= tau else None, c))
        return out


def right(s, vals, ans):
    """The whole outcome: every token's value after and the answer. A bucket counts as right only if it is the bucket of the
    true value (the word itself is not produced; the symbolic layer would have to name it)."""
    if vals is None:
        return 'unknown'
    if ans != RESP[s.resp]:
        return 'wrong'
    for p, (t, v) in enumerate(zip(s.tg, vals)):
        n = len(s.toks)
        truth = s.toks[t][2] if t < n else (BLANK if t == n else ('<bucket>', t - n - 1))
        if v != truth and not (t > n and s.after_values is not None and v == s.after_values[p]):   # the word itself, pointed to
            return 'wrong'
    return 'right'


def train(model, scenes, device, epochs=30, lr=3e-4, batch=64, seed=0, log=None):
    rng = random.Random(seed)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    model.to(device)
    for ep in range(epochs):
        model.train()
        idx = list(range(len(scenes)))
        rng.shuffle(idx)
        tot = 0.0
        for i in range(0, len(idx), batch):
            bs = [scenes[j] for j in idx[i:i + batch]]
            loss = model.loss(bs, device)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += loss.item() * len(bs)
        if log:
            log(f'epoch {ep} loss {tot / max(1, len(scenes)):.4f}')
    return model


def score(model, scenes, device, tau):
    c = Counter()
    for i in range(0, len(scenes), 128):
        bs = scenes[i:i + 128]
        for s, (vals, ans, conf) in zip(bs, model.predict(bs, device, tau)):
            c[right(s, vals, ans)] += 1
    return dict(c)
