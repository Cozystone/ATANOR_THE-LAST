# -*- coding: utf-8 -*-
"""A STATEFUL real system + goal achievement: acting in the world, not just learning its structure.

Every world before this reset before each act, so the Core learned WHICH operations succeed on
WHICH object kinds but never had to reach a target STATE. Here actions CHANGE real state and
persist, and the task is to reach a goal configuration -- the mandate's demo core, "accomplishes
practical goals". The system is a real filesystem: each slot is absent / a file / a directory,
and mkfile / mkdir / rm are real os operations with real preconditions (mkfile fails on an
occupied slot; rm fails on an absent one). Nothing about those preconditions is told to the
agent; it learns the transition model (state, action) -> next state from its own acts and plans
over it.

THE POINT is not the filesystem; it is that the same learning principle the Core uses for
structure -- observe (situation, action) -> outcome, generalize -- applied to STATE TRANSITIONS
lets the agent achieve goals a memoryless/random agent cannot.
"""
from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np

NSLOT = 6
from collections import Counter as _CC
#: non-behavioural. Where a life's looks actually come from -- kept because a
#: whole arc was once built on a guess about this.
LOOK_CAUSE = _CC()

ACTIONS = ("mkfile", "mkdir", "rm")
ABSENT, FILE, DIR = 0, 1, 2


class StatefulFS:
    """A real directory of NSLOT slots whose state persists across actions. Verdicts are POSIX's."""

    parents = (-1,) * NSLOT                  #: flat: every slot sits in the world root

    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.root = tempfile.mkdtemp(prefix="atanor_sf_")
        self.paths = [os.path.join(self.root, "s%d" % i) for i in range(NSLOT)]

    def state(self, i):
        p = self.paths[i]
        if os.path.isfile(p):
            return FILE
        if os.path.isdir(p):
            return DIR
        return ABSENT

    def config(self):
        return tuple(self.state(i) for i in range(NSLOT))

    def do(self, action, i):
        """One real, state-changing operation. Its precondition is POSIX's, not told to anyone."""
        p = self.paths[i]
        try:
            if action == "mkfile":
                if self.state(i) != ABSENT:
                    return False
                open(p, "w").close()
                return True
            if action == "mkdir":
                if self.state(i) != ABSENT:
                    return False
                os.mkdir(p)
                return True
            if action == "rm":
                s = self.state(i)
                if s == FILE:
                    os.remove(p)
                    return True
                if s == DIR:
                    os.rmdir(p)
                    return True
                return False
        except OSError:
            return False
        return False

    def dispose(self):
        shutil.rmtree(self.root, ignore_errors=True)


def random_goal(seed):
    return tuple(int(x) for x in np.random.default_rng(seed).integers(0, 3, NSLOT))


def random_agent(world, goal, budget):
    """No model: act at random until the goal or the budget runs out."""
    for step in range(budget):
        if world.config() == goal:
            return step
        world.do(ACTIONS[int(world.rng.integers(0, 3))], int(world.rng.integers(0, NSLOT)))
    return budget if world.config() != goal else budget


def model_agent(world, goal, budget, rng):
    """Learns the transition model (state, action) -> next state from its own acts, then acts
    toward the goal: for a slot not yet at its target, pick an action whose LEARNED effect from
    the slot's current state reaches the target, else explore. The same observe-and-generalize
    principle the Core uses for structure, applied to state transitions."""
    effect = {}                         # (state, action) -> set of resulting states observed
    steps = 0
    while steps < budget:
        cfg = world.config()
        if cfg == goal:
            return steps
        wrong = [i for i in range(NSLOT) if cfg[i] != goal[i]]
        rng.shuffle(wrong)
        i = wrong[0]
        cur, want = cfg[i], goal[i]
        chosen = None
        for a in ACTIONS:
            res = effect.get((cur, a))
            if res and want in res:
                chosen = a
                break
        if chosen is None:                      # nothing known to reach `want`: explore
            chosen = ACTIONS[int(rng.integers(0, 3))]
        before = world.state(i)
        world.do(chosen, i)
        after = world.state(i)
        effect.setdefault((before, chosen), set()).add(after)
        steps += 1
    return budget


class StatefulSQLite:
    """A SECOND real stateful system: rows in a real SQLite table. Each of NSLOT keys is absent /
    a plain row / a flagged row; actions insert / flag / delete change persistent state with
    SQL's own preconditions (insert fails on an existing key; flag fails on an absent one). Same
    goal-achievement contract as the filesystem, a different real ontology -- so reaching goals
    here tests whether the approach generalises across real systems, not just one."""

    def __init__(self, seed):
        import sqlite3
        self.rng = np.random.default_rng(seed)
        self.con = sqlite3.connect(":memory:")
        self.con.execute("CREATE TABLE t (k INTEGER PRIMARY KEY, flag INTEGER)")
        self.con.commit()

    def state(self, i):
        r = self.con.execute("SELECT flag FROM t WHERE k=?", (i,)).fetchone()
        if r is None:
            return ABSENT               # 0
        return DIR if r[0] else FILE     # flagged=2, plain=1

    def config(self):
        return tuple(self.state(i) for i in range(NSLOT))

    def do(self, action, i):
        cur = self.con.cursor()
        try:
            if action == "mkfile":                      # insert a plain row
                if self.state(i) != ABSENT:
                    return False
                cur.execute("INSERT INTO t VALUES (?, 0)", (i,)); self.con.commit(); return True
            if action == "mkdir":                       # flag a row (must exist and be plain)
                if self.state(i) != FILE:
                    return False
                cur.execute("UPDATE t SET flag=1 WHERE k=?", (i,)); self.con.commit(); return True
            if action == "rm":                          # delete a row (must exist)
                if self.state(i) == ABSENT:
                    return False
                cur.execute("DELETE FROM t WHERE k=?", (i,)); self.con.commit(); return True
        except Exception:
            return False
        return False

    def dispose(self):
        self.con.close()


def feature_agent(world, goal, budget, rng, nslot=None):
    """Plans via FEATURE-LEVEL action effects -- (slot_state, action) -> new_state -- learned from
    its own acts, so it generalises to configurations never visited: in an 8-slot world there are
    3^8 = 6561 configurations, unenumerable at any reasonable budget, but only 3 slot-states, and
    a slot's transition depends only on its own observable state. This is feature generalization
    (the FEATURE INTEGRATION capability) applied to transitions: learn per-feature effects, plan
    anywhere."""
    n = nslot or NSLOT
    effect = {}
    steps = 0
    while steps < budget:
        cfg = world.config()
        if cfg == goal:
            return steps
        wrong = [i for i in range(n) if cfg[i] != goal[i]]
        rng.shuffle(wrong)
        i = wrong[0]
        cur, want = cfg[i], goal[i]
        chosen = None
        for a in ACTIONS:
            if effect.get((cur, a)) == want:
                chosen = a
                break
        if chosen is None:
            for a in ACTIONS:                       # two-step route via ABSENT
                if effect.get((cur, a)) == ABSENT and want != cur:
                    chosen = a
                    break
        if chosen is None:
            # systematic discovery: try an action UNTRIED in this state before repeating known
            # ones -- there are only 9 (state, action) effects to learn, and random repetition
            # was measured wasting the budget (5/20 goals interleaved vs 20/20 with a dedicated
            # observation phase). Untried-first closes that gap without any world knowledge.
            untried = [a for a in ACTIONS if (cur, a) not in effect]
            chosen = untried[0] if untried else ACTIONS[int(rng.integers(0, 3))]
        before = world.state(i)
        world.do(chosen, i)
        effect[(before, chosen)] = world.state(i)
        steps += 1
    return budget


class StatefulFS8(StatefulFS):
    """The real filesystem, 8 slots: 6561 possible configurations -- far beyond enumeration at a
    60-act budget, so only feature-level generalization can plan here."""

    parents = (-1,) * 8

    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        import tempfile as _tf
        self.root = _tf.mkdtemp(prefix="atanor_sf8_")
        self.paths = [os.path.join(self.root, "s%d" % i) for i in range(8)]

    def config(self):
        return tuple(self.state(i) for i in range(8))


# --- DEPENDENT-STATE world: the parts of a real system are not independent ---------------------

# two chains of depth 3: root -> mid -> two leaves.  8 slots.
#   0: d0        1: d0/m       2: d0/m/x     3: d0/m/y
#   4: d1        5: d1/m       6: d1/m/x     7: d1/m/y
PARENT = (-1, 0, 1, 1, -1, 4, 5, 5)
NN = len(PARENT)


def parent_of(i):
    """Slot index of i's parent directory, or -1 for a top-level slot (whose parent is the
    world root, a real directory that always exists)."""
    return PARENT[i]


class NestedFS:
    """A real DIRECTORY TREE whose slots depend on each other, three levels deep: children
    live INSIDE their parent slot, so a child operation succeeds only while its parent is a
    real directory (POSIX decides, nobody is told), and removing a parent directory removes
    everything under it (rm -r). The flat per-slot transition key that plans perfectly in
    StatefulFS is structurally ambiguous here -- the same (state, action) succeeds or fails
    depending on another slot -- and at depth 3 the ambiguity compounds: a leaf is blocked
    until its mid exists, which is blocked until its root exists, so context-blind entries
    flip between success and failure and poison every level at once."""

    NAMES = ("d0", "m", "x", "y", "d1", "m", "x", "y")
    parents = PARENT

    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.root = tempfile.mkdtemp(prefix="atanor_nest_")

    def path(self, i):
        p = parent_of(i)
        if p < 0:
            return os.path.join(self.root, self.NAMES[i])
        return os.path.join(self.path(p), self.NAMES[i])

    def state(self, i):
        q = self.path(i)
        if os.path.isfile(q):
            return FILE
        if os.path.isdir(q):
            return DIR
        return ABSENT

    def config(self):
        return tuple(self.state(i) for i in range(NN))

    def do(self, action, i):
        q = self.path(i)
        try:
            if action == "mkfile":
                if self.state(i) != ABSENT:
                    return False
                open(q, "w").close()        # OSError if the parent is absent or a file
                return True
            if action == "mkdir":
                if self.state(i) != ABSENT:
                    return False
                os.mkdir(q)
                return True
            if action == "rm":
                s = self.state(i)
                if s == FILE:
                    os.remove(q)
                    return True
                if s == DIR:
                    shutil.rmtree(q)        # cascades onto children, like the real rm -r
                    return True
                return False
        except OSError:
            return False
        return False

    def dispose(self):
        shutil.rmtree(self.root, ignore_errors=True)


def nested_goal(seed):
    """A random REACHABLE configuration: a child exists only under a DIR parent."""
    rng = np.random.default_rng(seed)
    g = [ABSENT] * NN
    for c in (0, 4):                            # chain roots
        depth = int(rng.integers(1, 4))         # 1: root only, 2: +mid, 3: +leaves
        if depth == 1:
            g[c] = int(rng.integers(1, 3))      # FILE or DIR
            continue
        g[c] = DIR
        if depth == 2:
            g[c + 1] = int(rng.integers(1, 3))
            continue
        g[c + 1] = DIR
        g[c + 2] = int(rng.integers(0, 3))
        g[c + 3] = int(rng.integers(0, 3))
        if g[c + 2] == ABSENT and g[c + 3] == ABSENT:
            g[c + 2 + int(rng.integers(0, 2))] = int(rng.integers(1, 3))
    return tuple(g)


def dep_agent(world, goal, budget, rng, claims=None, table=None):
    """Learns CONDITIONAL action effects -- (parent_state, own_state, action) -> own_state --
    from its own acts, and works where learned progress is possible: first a wrong slot with a
    KNOWN action reaching its target under the CURRENT context, then a known two-step route via
    ABSENT, then a slot with an untried (context, state, action), then random. Creation order
    (parents before children) is never coded; it emerges because blocked children yield only
    no-change entries while parents yield productive ones. The context key also TRANSFERS:
    effects learned on top-level slots (whose parent, the world root, is a real directory)
    apply verbatim to children under DIR parents.

    `claims` (LEVEL 4): candidate entries from a SOURCE (help text), consulted only where the
    agent's OWN action has not yet spoken -- observation always outranks testimony, every acted
    key is recorded from what really happened, and untried-first exploration ignores claims
    entirely. Trust attaches to the SOURCE, not the sentence (doctrine: SOURCE S CLAIMS X):
    the first time reality contradicts a claimed entry, every remaining claim from that source
    is dropped -- a manual caught lying once stops being consulted. Measured necessity: without
    this, a deranged manual taxed one wasted act per false key (15 keys) and broke the sealed
    safety margin on concentrated seeds (gate attempt 1, docs/ATANOR_language_accel_verdict1.md)."""
    effect = table if table is not None else {}   #: pass a dict to LIVE INTO it (a life
    prior = dict(claims) if claims else {}        #: across episodes, savable to disk)

    def known(k):
        return effect[k] if k in effect else prior.get(k)
    steps = 0
    par = getattr(world, "parents", PARENT)  #: world topology; flat worlds are all -1
    acts = getattr(world, "actions", ACTIONS)
    n = len(par)
    ctx = lambda cfg, i: DIR if par[i] < 0 else cfg[par[i]]
    while steps < budget:
        cfg = world.config()
        if cfg == goal:
            return steps
        wrong = [i for i in range(n) if cfg[i] != goal[i]]
        rng.shuffle(wrong)
        i = chosen = None
        for j in wrong:                                        # tier 1: known productive act
            for a in acts:
                if known((ctx(cfg, j), cfg[j], a)) == goal[j]:
                    i, chosen = j, a
                    break
            if i is not None:
                break
        if i is None:                                          # tier 2: known two-step via ABSENT
            for j in wrong:
                for a in acts:
                    if known((ctx(cfg, j), cfg[j], a)) == ABSENT and goal[j] != cfg[j] != ABSENT:
                        i, chosen = j, a
                        break
                if i is not None:
                    break
        if i is None:                                          # tier 3: untried in this context
            for j in wrong:
                untried = [a for a in acts if (ctx(cfg, j), cfg[j], a) not in effect]
                if untried:
                    i, chosen = j, untried[0]
                    break
        if i is None:                                          # tier 4: nothing known anywhere
            i = wrong[int(rng.integers(0, len(wrong)))]
            chosen = acts[int(rng.integers(0, len(acts)))]
        before, c0 = cfg[i], ctx(cfg, i)
        bit = world.do(chosen, i)
        pred = known((c0, before, chosen))
        if pred is None:
            after = world.state(i)              # a key it has never seen: it must look
        else:
            moved = (pred != before)
            if moved != bool(bit):
                # THE WORLD JUST CONTRADICTED THE MIND. Its model said this act would
                # move (or not) and the world did the opposite -- which is what a peer's
                # commit or a changed rule feels like from the inside. Pay for a look
                # and start believing again from what is actually there.
                cfg = world.config()
                bel = list(cfg)
                after = cfg[i]
                before = before if pred is None else before
            else:
                after = pred if bit else before
        k = (c0, before, chosen)
        if prior and k in prior and prior[k] != after:
            prior.clear()                       # the source lied once: drop ALL its claims
        effect[k] = after
        steps += 1
    return budget


def flat_tiered_agent(world, goal, budget, rng):
    """ABLATION arm: the SAME tiered work selection as dep_agent but with the sealed flat key
    (own_state, action) -- so a gate difference against dep_agent isolates the conditional
    context key, not the selection policy."""
    effect = {}
    steps = 0
    while steps < budget:
        cfg = world.config()
        if cfg == goal:
            return steps
        wrong = [i for i in range(NN) if cfg[i] != goal[i]]
        rng.shuffle(wrong)
        i = chosen = None
        for j in wrong:
            for a in ACTIONS:
                if effect.get((cfg[j], a)) == goal[j]:
                    i, chosen = j, a
                    break
            if i is not None:
                break
        if i is None:
            for j in wrong:
                for a in ACTIONS:
                    if effect.get((cfg[j], a)) == ABSENT and goal[j] != cfg[j] != ABSENT:
                        i, chosen = j, a
                        break
                if i is not None:
                    break
        if i is None:
            for j in wrong:
                untried = [a for a in ACTIONS if (cfg[j], a) not in effect]
                if untried:
                    i, chosen = j, untried[0]
                    break
        if i is None:
            i = wrong[int(rng.integers(0, len(wrong)))]
            chosen = ACTIONS[int(rng.integers(0, 3))]
        before = world.state(i)
        world.do(chosen, i)
        effect[(before, chosen)] = world.state(i)
        steps += 1
    return budget


def save_life(effect, path):
    """Serialize a lived effect table -- (parent_state, own_state, action) -> own_state -- to
    JSON. This file IS the past self a later process can consult (as a SOURCE, not as truth)."""
    import json
    io_ = open(path, "w", encoding="utf-8")
    io_.write(json.dumps({"%d,%d,%s" % k: v for k, v in effect.items()}))
    io_.close()


def load_life(path):
    import json
    raw = json.loads(open(path, encoding="utf-8").read())
    out = {}
    for k, v in raw.items():
        c, s_, a = k.split(",")
        out[(int(c), int(s_), a)] = int(v)
    return out


def scramble_life(effect, seed):
    """A CORRUPTED past: same keys, outcomes permuted among themselves (a derangement where
    possible) -- the wrong-life control for compounding gates."""
    rng = np.random.default_rng(seed)
    keys = list(effect)
    vals = [effect[k] for k in keys]
    if len(set(vals)) > 1:
        perm = rng.permutation(len(vals))
        tries = 0
        while all(vals[perm[i]] == vals[i] for i in range(len(vals))) and tries < 20:
            perm = rng.permutation(len(vals)); tries += 1
        return {k: vals[perm[i]] for i, k in enumerate(keys)}
    return dict(effect)


# --- REAL GIT world: chains deeper than one act, judged by real git --------------------------

GIT_NSLOT = 5
GIT_ACTIONS = ("create", "add", "commit", "rm")
G_ABSENT, G_UNTRACKED, G_STAGED, G_COMMITTED = 0, 1, 2, 3


class GitWorld:
    """A REAL git repository: each slot is a file that is absent / untracked / staged /
    committed, moved by real git commands whose preconditions real git enforces (nothing can
    be committed that was not staged; nothing staged that is not on disk). The state chain is
    four deep, so reaching "committed" from nothing exceeds any one known act -- the venue
    where planning over a LEARNED transition graph becomes necessary. `rm` is one world
    action that performs the real removal (and, for a committed file, the deletion commit) --
    a macro on the world side; the agent sees only state before and after."""

    parents = (-1,) * GIT_NSLOT
    actions = GIT_ACTIONS

    def __init__(self, seed):
        import subprocess
        self._sub = subprocess
        self.rng = np.random.default_rng(seed)
        self.root = tempfile.mkdtemp(prefix="atanor_git_")
        self._git("init", "-q")
        self._git("config", "user.email", "atanor@local")
        self._git("config", "user.name", "atanor")
        self.names = ["f%d.txt" % i for i in range(GIT_NSLOT)]

    def _git(self, *args):
        return self._sub.run(("git",) + args, cwd=self.root, capture_output=True, text=True)

    def state(self, i):
        nm = self.names[i]
        on_disk = os.path.exists(os.path.join(self.root, nm))
        r = self._git("status", "--porcelain", "--", nm).stdout.strip()
        if not on_disk:
            return G_ABSENT
        if r.startswith("??"):
            return G_UNTRACKED
        if r[:1] == "A" or r[:1] == "M":
            return G_STAGED
        if r == "":
            return G_COMMITTED           # tracked and clean
        return G_UNTRACKED

    def config(self):
        return tuple(self.state(i) for i in range(GIT_NSLOT))

    def do(self, action, i):
        nm = self.names[i]
        p = os.path.join(self.root, nm)
        s = self.state(i)
        try:
            if action == "create":
                if s != G_ABSENT:
                    return False
                open(p, "w").write("x")
                return True
            if action == "add":
                return self._git("add", "--", nm).returncode == 0 and os.path.exists(p)
            if action == "commit":
                if s != G_STAGED:
                    return False         # real git: "no changes added to commit"
                return self._git("commit", "-q", "-m", "c", "--", nm).returncode == 0
            if action == "rm":
                if s == G_ABSENT:
                    return False
                if s == G_UNTRACKED:
                    os.remove(p)
                    return True
                self._git("rm", "-f", "-q", "--", nm)
                if s == G_COMMITTED:
                    self._git("commit", "-q", "-m", "rm", "--", nm)
                return True
        except OSError:
            return False
        return False

    def dispose(self):
        shutil.rmtree(self.root, ignore_errors=True)


def git_goal(seed):
    g = tuple(int(x) for x in np.random.default_rng(seed).integers(0, 4, GIT_NSLOT))
    return g if any(g) else (G_COMMITTED,) + g[1:]


class DictStore:
    """The hand-keyed effect table as a pluggable store (the sealed incumbent's memory)."""

    def __init__(self, table=None):
        self.d = table if table is not None else {}

    def get(self, k):
        return self.d.get(k)

    def has(self, k):
        return k in self.d

    def put(self, k, v, step=0):
        self.d[k] = v


class CoreStore:
    """ONE MIND: the ConstructionMind itself as the transition model. Each act is absorbed as
    a situation whose ENTITY is the state-situation id (parent_state * 5 + own_state) and
    whose ACTION is the verb -- so GROUP(entity) over state-situations IS the conditional
    effect table, but INVENTED by MDL rather than hand-keyed, readable in the leader, and
    carried by the same library as every other construction. Queries poll the mode among
    experiences sharing the leader's key (predict_categorical); the episodic record
    (mind.cells) answers "have I tried this here" for untried-first exploration. Parity
    discipline: predictions are offered only for episodically-known keys, so any capability
    difference against DictStore is attributable to the substrate, not extra guessing."""

    def __init__(self, world, seed, refine="off", synth_lib=None, world_tag=None, library=None,
                 reach="off"):
        from .construction_mind import ConstructionMind
        #: WHAT THE MIND MAY DO WHEN MEMORY IS SILENT.
        #: "off"    -- nothing, and it goes and looks. This was parity discipline for the
        #:            substrate comparison (CORE-CURVE), which is sealed; kept as default
        #:            so every sealed capability is untouched.
        #: "leader" -- the Core's own learned partition answers. Claude's machinery.
        #: "word"   -- ATANOR'S OWN VOCABULARY answers, or stays silent. The only channel
        #:            through which an invented word can reach real work, which is why
        #:            three honest vocabularies in a row were worth exactly zero.
        self.reach = reach
        #: 돌파-6 channel (opt-in): ATANOR's rulebook about ITS OWN COGNITION. The
        #: experience stream is its belief-outcome record; the rules it induces there
        #: -- "in context c, a belief of s holds" -- are licensed per context by their
        #: own predictions and, where licensed, replace the refresh look. Claude names
        #: the channel; the mappings, licenses and retirements are all ATANOR's.
        self.cognition = None
        self._cog_record = {}
        self._cog_n = 0
        #: order-13 allocator: the learned outcome model over epistemic actions.
        self.episteme = None
        #: proprioception plumbing: the mind feels its own deliberation through the
        #: same episteme as every other epistemic event (set by the driver)
        #: ATANOR's rulebook: bounded program synthesis over the raw record.
        #: Opt-in; None leaves every sealed behavior untouched.
        self.rulebook = None
        self._record = {}        #: (ctx, s, verb) -> Counter of outcomes
        self.world_tag = world_tag
        # PERCEPT WIDTH IS AN ORGAN FACT. A mind with no eye and one body has NO visual
        # or body positions in its observation vector -- not zero-filled ones -- so a
        # word grown in that mind keeps meaning the same quantity when the vector is
        # replayed later. An eye or a second body WIDENS the percept; words do not
        # transfer across unlike-bodied minds by index, and that is disclosed, not
        # papered over with padding.
        self._seen = ()
        self._body = ()
        self._seed, self._refine = seed, refine
        self._sm = None
        self._spoken = {}        #: key -> (word, what it said), until the world answers
        self.mind = ConstructionMind(seed=seed, refine=refine, synth_lib=synth_lib,
                                     world_tag=world_tag, library=library)
        self.acts = tuple(getattr(world, "actions", ACTIONS))
        self.step = 0

    def replay(self, k, v):
        """FALLBACK binding 1: a transition the Self itself lived in an earlier segment
        of the same source, re-entered as evidence -- the record and the mind, nothing
        else (no testimony credit, no rule judgement: those were paid when it was
        lived). The planner's own predictions start from what it already knows."""
        ctx, s_, a = k
        if a not in self.acts:
            return False
        e, ai = self._ea(k)
        rec = self._record.setdefault((ctx, s_, a), [])
        rec.append(int(v))
        del rec[:-24]
        self.mind.absorb(e, ai, 0, self.step, float(v) * self.Y_UNIT,
                         feats=(float(s_ * self.Y_UNIT), float(ctx * self.Y_UNIT))
                         + getattr(self, "obs", ()))
        self.step += 1
        return True

    #: the situation's identity. The old stride of 5 silently ASSUMED fewer than five
    #: states per slot, which held for every sealed family and is FALSE in a
    #: seven-state world: (ctx=1,state=0) and (ctx=0,state=5) both landed on entity 5,
    #: so twelve genuinely different situations were conflated into six, and the mind
    #: was handed contradictions that were ours, not the world's. Found while auditing
    #: what the mind kept splitting on. The stride now clears any world under sixteen
    #: states; nothing else about the encoding changes.
    ENTITY_STRIDE = 16

    def _ea(self, k):
        ctx, s_, a = k
        return ctx * self.ENTITY_STRIDE + s_, self.acts.index(a)

    #: states are fed to the mind in a unit where their differences exceed its noise floor
    #: (SIGMA_FLOOR is calibrated on 4-vs-20 worlds; ids 0..3 have spread ~1 and would leave
    #: the mind asleep). Scaling is perception physiology -- the mandate's own category --
    #: and the adapter unscales on read; the Core is untouched.
    Y_UNIT = 8.0

    def get(self, k):
        # the Core's categorical path is cell-first itself (answer-order surgery), so the
        # store runs the REAL path; the has() gate keeps parity discipline (planning
        # consults predictions only where episodically known -- generalization to unseen
        # keys is examined by its own gate, not smuggled into planning).
        e, a = self._ea(k)
        ctx, s_, _ = k
        fq = (float(s_ * self.Y_UNIT), float(ctx * self.Y_UNIT)) + getattr(self, "obs", ())
        if (e, a, 0) not in self.mind.cells:
            if self.rulebook is not None:
                y = self.rulebook.speak(ctx, s_, k[2])
                if y is not None:
                    return int(y)
            if self.reach == "off":
                return None
            if self.reach == "word":
                said = self.mind.speak_unseen(a, fq)
                if said is None:
                    return None
                w = self.mind._speak.get(a)
                if w is not None and w[1] is not None:
                    self._spoken[k] = (w[1], said)
                return int(round(said / self.Y_UNIT))
            return int(round(self.mind.predict_categorical(e, a, 0, feats=fq)
                             / self.Y_UNIT))
        return int(round(self.mind.predict_categorical(e, a, 0, feats=fq) / self.Y_UNIT))

    #: KNOWING WHETHER TO TRUST YOURSELF is a thing that can be learned from experience
    #: like any other, and the experience is free: every act returns a bit saying whether
    #: the belief it was taken on held. So the mind keeps a second record about ITSELF,
    #: read by the same Core and refined by the SAME vocabulary -- a word invented about
    #: the world may be tried on the self, and the other way round. What Claude supplies
    #: here is one generic quantity, the AGE of the belief; what to make of it is not
    #: Claude's to say.
    def _self_mind(self):
        if getattr(self, "_sm", None) is None:
            from .construction_mind import ConstructionMind
            self._sm = ConstructionMind(seed=self._seed, refine=self._refine,
                                        synth_lib=self.mind.synth_lib,
                                        world_tag=self.world_tag)
            # ONE SELF, MANY BODIES: this mind deliberates with the same vocabulary
            # and burns the same organism-wide clock as the primary, so it wears the
            # same proprioception and the same think gate. Measured before these two
            # lines: the Self felt the burn, selected it, authored its law -- and the
            # law never reached the body doing ~all of the burning.
            self._sm.episteme_ref = getattr(self.mind, "episteme_ref", None)
            self._sm.invented_ref = getattr(self.mind, "invented_ref", {})
            self._sm.world_id = getattr(self.mind, "world_id", 0.0)
            self._sm.shop_ref = getattr(self.mind, "shop_ref", None)
        return self._sm

    def belief_query(self, ctx, believed, age, vis=0.0):
        """Will what I believe about this slot still be true? The eye's per-slot delta
        rides the same question: a slot whose look changed since the last glance is a
        slot the world may have moved under."""
        e = ctx * self.ENTITY_STRIDE + believed
        m = self._self_mind()
        # THE EYE IS PART OF THE SITUATION, NOT A FOOTNOTE TO IT. As a trailing feature
        # the visual delta was inert -- the cells-first path answers by KEY and nothing
        # reads the feats (measured: byte-identical lives with and without the eye). A
        # slot whose appearance changed since the last glance is a DIFFERENT situation
        # from one that looks untouched, so the change-bit joins the situation identity:
        # separate cells, separate answers, no threshold beyond "any change at all".
        # REVERTED same-day: keying the cells by the change-bit split young decay
        # records into two thin populations and cost the churn seat 57% (645 -> 276).
        # Three eye designs measured: global scalars inert, per-slot feats inert (the
        # cells-first path answers by key), keyed bit harmful. The mechanism is the
        # world's, not the eye's: DeepGitWorld porcelain is information-complete for
        # decisions, and a peer's push does not touch the working tree (the pixels)
        # until pull. The eye stays as percept physiology; it cannot pay here.
        if (e, 0, 0) not in m.cells:
            return None
        y = m.predict_categorical(e, 0, 0,
                                  feats=(float(believed * self.Y_UNIT),
                                         float(ctx * self.Y_UNIT), float(age),
                                         float(vis)))
        return y >= self.Y_UNIT / 2.0

    def belief_learn(self, ctx, believed, age, held, vis=0.0):
        """EVERY LOOK IS A LESSON ABOUT HOW FAST BELIEF DECAYS, and the mind threw all of
        them away -- fourteen hundred to two thousand free labelled samples per life.
        Whenever it pays to see the world it now also learns, per slot, whether what it
        believed was still true and how old that belief was.

        This also breaks a censorship the first version could not escape: when the mind
        distrusted a belief it looked, and looking made the belief fresh, so it never
        found out whether the distrust was warranted -- a pessimistic cell stayed
        pessimistic for ever. Learning at the LOOK instead of at the ACT takes the mind's
        own decision out of its own sampling."""
        e = ctx * self.ENTITY_STRIDE + believed
        if self.cognition is not None:
            from collections import Counter
            k6 = (ctx, believed, "hold")
            self._cog_record.setdefault(k6, Counter())[1 if held else 0] += 1
            self.cognition.judge(ctx, believed, "hold", 1 if held else 0)
            self._cog_n += 1
            if self._cog_n % 50 == 0:
                self.cognition.induce(self._cog_record)
        self._self_mind().absorb(e, 0, 0, self.step,
                                 self.Y_UNIT if held else 0.0,
                                 feats=(float(believed * self.Y_UNIT),
                                        float(ctx * self.Y_UNIT), float(age),
                                        float(vis)))

    def query(self, k):
        """The GENERALIZATION path: answer any key, absorbed or not, through the full
        Core (cells first, leader where memory is silent), with the query entity's
        observable features supplied by perception (decoded from the key)."""
        e, a = self._ea(k)
        ctx, s_, _ = k
        y = self.mind.predict_categorical(e, a, 0, feats=(float(s_ * self.Y_UNIT),
                                                          float(ctx * self.Y_UNIT)))
        return int(round(y / self.Y_UNIT))

    #: THE TRIED LEDGER. "I performed this act at this key" is a fact about the LIFE,
    #: not about the value observed -- and the two were fused: has() answered from value
    #: memory, so episodic "experienced" only grew when an outcome was WRITTEN. That
    #: fusion is what let the forgery hide (writes granted tried-ness) and what starved
    #: the mind when writing became honest (rules answered, nothing was written, the
    #: same keys stayed "untried" forever, 850 -> 824 -> 3). Trying is recorded at the
    #: act; observing is recorded at the write; neither may impersonate the other.
    def mark_tried(self, k):
        if not hasattr(self, "tried"):
            self.tried = set()
        self.tried.add(k)

    def has(self, k):
        if getattr(self, "tried", None) and k in self.tried:
            return True
        e, a = self._ea(k)
        return (e, a, 0) in self.mind.cells

    def contested(self, k):
        """A key whose OWN RECORD disagrees with itself and which the mind's
        refinement search has not explained. Knowledge that is WRONG, not merely
        absent -- and the mind can only resolve it by going back and looking."""
        e, a = self._ea(k)
        vs = self.mind.cell_vals.get((e, a, 0))
        return bool(vs) and len(vs) >= 2 and self.mind.refinements.get((e, a, 0)) is None

    #: PERCEPTION (2026-08-28): what the eye saw at this moment, in a world-agnostic
    #: vocabulary -- how many slots stood in each state. It names no verb, no slot and
    #: no world; it is the same summary in a filesystem, a repository or a database,
    #: and it is what lets a mind ask whether an outcome turned on the situation at
    #: large. `observe` is called by the agents where they already read the world.
    OBS_STATES = 8

    def observe(self, cfg):
        h = [0.0] * self.OBS_STATES
        for v in cfg:
            if 0 <= int(v) < self.OBS_STATES:
                h[int(v)] += 1.0
        self.obs = tuple(x * self.Y_UNIT for x in h) + self._seen + self._body

    def see(self, frame):
        """VISUAL EVIDENCE ABOUT THE SAME WORLD: how much the picture changed since the
        last glance, and in how many places. Two quantities from real pixels, joined to
        the same observation vector every experience already carries -- so ATANOR's own
        words may build on them, or ignore them, exactly as evidence dictates. No new
        mind; the same one, with an eye."""
        if frame is None:
            return
        prev = getattr(self, "_frame", None)
        self._frame = frame
        if prev is None or len(prev) != len(frame):
            self._seen = (0.0, 0.0)
            self._slot_vis = (0.0,) * len(frame)
            return
        deltas = [abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(frame, prev)]
        changed = sum(1 for d in deltas if d > 1e-9)
        self._seen = (float(sum(deltas)), float(changed))
        #: WHICH file's appearance changed since the mind last looked -- per-slot, so
        #: the eye can answer the one question porcelain answers late: has the world
        #: moved under THIS belief. Content changes before status does.
        self._slot_vis = tuple(min(d, 1.0) * self.Y_UNIT for d in deltas)

    def embody(self, body):
        """Which body this experience arrives through -- a perceivable fact about the
        moment, nothing more. One Self; the body is context, not identity."""
        self._body = (float(body) * self.Y_UNIT,)

    #: COGNITION IS ALSO A PLACE WHERE THE MIND LIVES. Consulting costs a unit; a dry
    #: consult buys nothing. Whether a given lookup pays is a fact about the mind's own
    #: process, learnable from its own record like any other fact -- same cells, same
    #: refinement, same words. Claude fixes only the hook and the label; what predicts
    #: payoff is ATANOR's to discover. Context 2 keeps the cognitive record from ever
    #: colliding with world experience.
    consult_policy = False

    def consult_worth(self, verb):
        if not self.consult_policy:
            return None
        e = self.acts.index(verb)
        m = self._self_mind()
        if (e, 0, 2) not in m.cells:
            return None                     # no record yet: find out by doing
        y = m.predict_categorical(e, 0, 2, feats=(float(e * self.Y_UNIT),) + self.obs)
        return y >= self.Y_UNIT / 2.0

    def consult_learn(self, verb, taught):
        if not self.consult_policy:
            return
        if verb not in self.acts:
            return          # a verb from another body's world; not this alphabet
        e = self.acts.index(verb)
        self._self_mind().absorb(e, 0, 2, self.step,
                                 self.Y_UNIT if taught else 0.0,
                                 feats=(float(e * self.Y_UNIT),) + self.obs)

    def put(self, k, v, step=None, fresh=True):
        e, a = self._ea(k)
        # THE WORLD HAS NOW ANSWERED a key one of ATANOR's words spoke for. This is the
        # only judgement that matters: not how much the word compressed, but whether the
        # mind is better off for having listened to it.
        kn = getattr(self, "knowledge", None)
        if kn is not None:
            kn.lived(k, v)      # testimony is licensed by the mind's own record
        heard = self._spoken.pop(k, None)
        if heard is not None:
            w, said = heard
            if abs(said - v * self.Y_UNIT) < self.Y_UNIT / 2.0:
                # NOTHING WAS OBSERVED HERE. The value coming back is the mind's own
                # answer returning as if it were experience, and writing it down would
                # be manufacturing a memory of something never seen -- which is exactly
                # what made the governor inert: a word could not be charged for being
                # wrong because its guess had been filed as fact. The world's move-bit
                # did not contradict it, so it is credited with the look it saved, and
                # the record stays a record of what actually happened.
                w.saved += 1
                return
            w.wasted += 1
        ctx, s_, _ = k
        # FALLBACK bookkeeping: every transition actually lived this segment, in order,
        # exactly (the per-key record below is a capped window and cannot say what was
        # new) -- what the carried memory may take from this segment
        lived = getattr(self, "_lived", None)
        if lived is None:
            lived = self._lived = []
        lived.append((ctx, s_, k[2], int(v), bool(fresh)))
        del lived[:-2000]
        if self.rulebook is not None:
            from collections import Counter as _C
            self.rulebook.judge(ctx, s_, k[2], int(v))
            rec = self._record.setdefault((ctx, s_, k[2]), [])
            rec.append(int(v))
            del rec[:-24]                    # the record is a lived window, not an archive
            self._n_obs = getattr(self, "_n_obs", 0) + 1
            if self._n_obs % 64 == 0:       # induction is periodic, not per-act
                self.rulebook.induce(self._record)
        # the state IS an observable feature of the situation (in mind units, so a
        # value-keyed FPROJ bucket and the outcome scale agree), and the moment's
        # observation rides with it
        self.mind.absorb(e, a, 0, self.step if step is None else step,
                         float(v) * self.Y_UNIT,
                         feats=(float(s_ * self.Y_UNIT), float(ctx * self.Y_UNIT))
                         + getattr(self, "obs", ()))
        self.step += 1


#: non-behavioural: where a life's looks actually come from. Kept because a
#: whole arc was once built on a guess about this.

def _consult_worth(store, k5):
    """Is this consult worth paying for? The mind's OWN synthesized program answers
    first, where it has one and it speaks; its frequency ledger answers second; the
    default is the structural opportunity itself. Claude wrote the order of courts,
    never a verdict."""
    if not getattr(store, "cog_consult_gate", True):
        return None
    prog = getattr(store, "invented", {}).get("consult")
    if prog is not None:
        pv = prog.side((float(k5[1]), float(k5[0]),
                        float(getattr(store, "world_id", 0.0))),
                       getattr(getattr(store, "mind", None), "synth_lib", None))
        if pv is not None:
            return 1 if pv else 0
    epi = getattr(store, "episteme", None)
    if epi is not None:
        return epi.worth(k5[0], k5[1], "consult")
    return None


def plan_agent(world, goal, budget, rng, claims=None, table=None, store=None, consult=None,
               knowledge=None,
               exo=None):
    """PLANS over its own learned transition graph: per wrong slot, breadth-first search from
    the current state to the target through KNOWN (context, state, action) -> state edges --
    so chains of any depth are one lookup once each link has been experienced ONCE. Falls back
    to untried-first exploration, then random. Claims (a manual, a past life) join the graph
    through the sealed #24 channel: consulted only until the agent's own acts speak, the whole
    source dropped on the first observed contradiction. Subsumes dep_agent's tiers 1-2 (a
    known one-step route IS a length-1 BFS path); dep_agent stays frozen as the greedy
    control arm."""
    store = store if store is not None else DictStore(table)
    prior = dict(claims) if claims else {}
    src_of = {k: "claims" for k in prior}       #: per-source trust: a fuse per page/manual
    consulted = set()
    distrusted = set()                          #: sources whose fuse blew; never merged again
    if knowledge is not None:
        # WHAT WAS LEARNED FROM OUTSIDE, EARLIER, IS STILL KNOWN NOW. The call-local
        # prior/fuse discipline is unchanged; knowledge is simply where it persists
        # across slices and lives, with provenance, until reality kills it.
        for k2, v2 in knowledge.offer().items():
            if k2 not in prior:
                prior[k2] = v2
                src_of[k2] = knowledge.src[k2]
        distrusted |= knowledge.distrusted
    acts = getattr(world, "actions", ACTIONS)
    par = getattr(world, "parents", PARENT)
    n = len(par)

    def known(k):
        v = store.get(k)
        return v if v is not None else prior.get(k)

    def first_step(c0, cur, want):
        # BFS over known edges within this context; returns the first action of a shortest path
        from collections import deque
        q = deque([(cur, None)])
        seen = {cur}
        parent = {}
        while q:
            s, _ = q.popleft()
            for a in acts:
                nxt = known((c0, s, a))
                if nxt is None or nxt in seen or nxt == s:
                    continue
                parent[nxt] = (s, a)
                if nxt == want:
                    while parent[nxt][0] != cur:
                        nxt = parent[nxt][0]
                    return parent[nxt][1]
                seen.add(nxt)
                q.append((nxt, None))
        return None

    steps = 0
    ctx = lambda cfg, i: DIR if par[i] < 0 else cfg[par[i]]
    #: BELIEF (2026-08-28, order-7 attempt 1). The mind used to re-read the whole world
    #: at the top of every step. Where looking is free that is merely redundant; where
    #: looking costs what acting costs it consumed three quarters of a life -- measured
    #: on the Mountain: 3068 looks against 932 acts. A mind that knows what its own acts
    #: do does not need to be told the world again after each one. It carries the world
    #: forward itself and looks only when it has no belief, or when the world has just
    #: contradicted it. Refreshing on contradiction is what keeps this from becoming
    #: fantasy: another body's work, or a rule change, shows up as an act that did not
    #: do what the mind's own model said it would.
    #: A MIND THAT MOVES ITS ATTENTION SHOULD NOT FORGET THE WORLD. Belief used to live
    #: in this call, so every shift of attention -- every slice, every goal switch --
    #: threw away everything the mind believed and paid to read the whole world again.
    #: Measured on the Mountain: of 2058 looks in a life, 450 were this and exactly 1 was
    #: a key it had never met. Carrying belief is opt-in per store, so every sealed
    #: capability keeps the old behaviour; what makes it safe rather than fantasy is
    #: unchanged -- an act that comes out differently refreshes it, and victory is still
    #: never declared on belief alone.
    carry = getattr(store, "carry_belief", False)
    selfmod = getattr(store, "self_model", False)
    age = 0

    def learn_decay(old, seen):
        # the look has already been paid for; the lesson inside it is free -- and it
        # includes what the eye saw per slot, when there is an eye
        if not selfmod or old is None:
            return
        sv = getattr(store, "_slot_vis", None)
        cog = getattr(store, "cognition", None)
        changed = any(o != s2 for o, s2 in zip(old, seen))
        for j2 in range(len(seen)):
            if cog is not None:
                # THE LOOK EVENT, judged in life currency: a refresh that revealed
                # nothing anywhere was a unit spent for nothing; one that caught the
                # world moving was necessary. The mind's own rulebook learns where
                # each kind lives -- no one tells it looking is good or bad. The event
                # both scores existing rules (judge) and enters the record so new
                # rules can be BORN of it (the first wiring judged only, so no look
                # rule could ever exist -- measured, cog 0 forever).
                cog.judge(ctx(seen, j2), old[j2], "look", 1 if changed else 0)
            epi = getattr(store, "episteme", None)
            if epi is not None:
                epi.note(ctx(seen, j2), old[j2], "look", changed,
                         feats=(float(old[j2]), float(ctx(seen, j2)), float(age),
                                float(getattr(store, "world_id", 0.0))))
            store.belief_learn(ctx(seen, j2), old[j2], age, old[j2] == seen[j2],
                               vis=(sv[j2] if sv and j2 < len(sv) else 0.0))
    bel = getattr(store, "bel", None) if carry else None
    fresh = False
    while steps < budget:
        if bel is None:
            LOOK_CAUSE["no belief yet"] += 1
            cfg = world.config()
            learn_decay(bel, cfg)
            bel = list(cfg)
            if carry:
                store.bel = bel
            fresh = True
            age = 0
        else:
            cfg = tuple(bel)
            fresh = False
        if hasattr(store, "observe"):
            store.observe(cfg)          # the mind sees what the eye saw
        if exo is not None:
            # EXOGENOUS PERCEPTION: a slot whose state differs from the last state the mind
            # read there, without the mind having acted on it, changed BY THE WORLD. The
            # observation is recorded against the state it changed FROM -- learned evidence
            # about what decays, with no state or rate named in code.
            last = exo.setdefault("last", [None] * n)
            vol = exo.setdefault("vol", {})
            acted = exo.get("acted")
            for j in range(n):
                if last[j] is not None and cfg[j] != last[j] and j != acted:
                    vol[last[j]] = vol.get(last[j], 0) + 1
            exo["last"] = list(cfg)
            exo["acted"] = None
        # PARTIAL GOALS (ruling-5 §XIV organism change, sealed by L2b's finding: a
        # goal slot of None is DON'T-CARE, making repo-level intentions expressible
        # without conjoining file views. Full goals behave bit-identically: for
        # all-non-None goals both tests reduce to the original comparisons and the
        # rng stream is untouched.
        if all(g is None or c == g for c, g in zip(cfg, goal)):
            # A MIND MAY NOT DECLARE VICTORY ON BELIEF ALONE (order-7 attempt 2).
            # Attempt 1 carried the world forward and tripled the work it got done --
            # and then, when a rule landed that made a successful act land somewhere
            # else, it believed it had finished and stopped. Forever: 440 turns, all
            # three standing goals frozen, nothing completed. The act succeeded, so
            # nothing contradicted it; only the DESTINATION was wrong, and it never
            # looked. So: believing you are done is worth exactly one look. If the
            # world agrees, stop. If it does not, that is the contradiction the belief
            # could not otherwise feel -- adopt what is really there and keep working.
            if fresh:
                return steps
            _gs = next((j9 for j9 in range(n) if goal[j9] is not None), 0)
            _epi9 = getattr(store, "episteme", None)
            _vgate = getattr(store, "verify_gate", False)
            _vprog = getattr(store, "invented", {}).get("verify")
            _vsay = None
            # the decision-time moment, kept for the note below (audit N6: the note
            # was written after the look had reset age and refreshed cfg)
            _vfeats = (float(cfg[_gs]), float(ctx(cfg, _gs)), float(age), float(steps),
                       float(getattr(store, "world_id", 0.0)))
            if _vgate and _vprog is not None:
                _pv9 = _vprog.side(_vfeats, getattr(store.mind, "synth_lib", None))
                _vsay = None if _pv9 is None else (1 if _pv9 else 0)
            if _vgate and (_vsay == 0 or (_vsay is None and _epi9 is not None
                    and _epi9.worth(ctx(cfg, _gs), cfg[_gs], "verify") == 0)):
                # ITS OWN RECORD says victory claims from here usually fail the look.
                # The law stands -- no victory without verification -- but a claim not
                # worth making is not made yet, and a belief not worth claiming is a
                # belief to DOUBT: the goal slots return to the worklist and the mind
                # keeps acting on them instead of paying a look to be told no.
                _deferred = True
            else:
                LOOK_CAUSE["verify a claimed victory"] += 1
                cfg = world.config()
                learn_decay(bel, cfg)
                bel = list(cfg)
                if carry:
                    store.bel = bel      # a verified world is the freshest belief there is
                age = 0
                fresh = True
                won = all(g is None or c == g for c, g in zip(cfg, goal))
                if _epi9 is not None:
                    _epi9.note(int(_vfeats[1]), int(_vfeats[0]), "verify", won,
                               feats=_vfeats)
                if won:
                    return steps
        if locals().get("_deferred"):
            _deferred = False
            wrong = [i for i in range(n) if goal[i] is not None]
        else:
            wrong = [i for i in range(n) if goal[i] is not None and cfg[i] != goal[i]]
        rng.shuffle(wrong)
        if exo is not None and exo.get("vol"):
            # decay-aware ORDER, read off the learned table: fix stable targets first so
            # the volatile ones are freshest when the configuration must stand
            vol = exo["vol"]
            wrong.sort(key=lambda j: vol.get(goal[j], 0))
        i = chosen = None
        # THE PROPOSE SITE (machine shop): if the mind has a procedure of its own on
        # trial or promoted, its ranking of the acts it could take speaks first. Its
        # moments are the same tuples recorded below for every act it takes.
        _shop = getattr(store, "shop", None)
        if _shop is not None and wrong and _shop._live_one("propose") is not None:
            from .machine_shop import token as _tok
            _wid = float(getattr(store, "world_id", 0.0))
            _epi_p = getattr(store, "episteme", None)
            _hist = [f for f, _ in _epi_p.moments("act", len(_shop.observers))[-8:]] \
                if _epi_p is not None else ()
            # the act is an OPAQUE token (the provenance rule): no enumeration order
            _moments = [((j, a), (float(cfg[j]), float(ctx(cfg, j)), float(goal[j]),
                                   float(age), _wid, _tok(a)))
                        for j in wrong for a in acts]
            _pick = _shop.propose(_moments, _hist, getattr(store.mind, "synth_lib", None),
                                  rng)
            if _pick is not None:
                i, chosen = _pick
        for j in (wrong if i is None else ()):                 # tier 1: a known route, any depth
            a = first_step(ctx(cfg, j), cfg[j], goal[j])
            if a is not None:
                i, chosen = j, a
                break
        # REVERTED 2026-08-28: a tier that sent the mind back to keys whose record
        # contradicted itself. It was a measured REGRESSION -- isolated arm by arm in a
        # world that changes its rules: with it 572 acts / 29 reached, without it
        # 313 / 37 (and 475/28 vs 225/35 on a second seed). Seeking contradictions is
        # not the same as being able to resolve them, and a mind that returns to a key
        # it cannot yet explain simply pays twice. The organ that DOES pay is the
        # workshop, which changes what the mind believes rather than where it walks.
        if i is None:                                          # tier 2: untried here
            for j in wrong:
                untried = [a for a in acts if not store.has((ctx(cfg, j), cfg[j], a))]
                if untried:
                    i, chosen = j, untried[0]
                    break
        # L5: CONSULT BEFORE GUESSING BLIND -- about to explore an untried act whose verb
        # has never been looked up: spend THIS act fetching its page instead (a real HTTP
        # GET, priced like any act). The page is a SOURCE: its parsed claims join `prior`
        # under its own fuse and never overwrite experience or another source's entry.
        _k5 = None if i is None else (ctx(cfg, i), cfg[i], chosen)
        if _k5 is None and consult is not None:
            # No untried act anywhere -- but ignorance's second form may be present: a
            # wrong slot whose key's own record contradicts itself. That key is the
            # consult subject; the ACT still comes from the normal tiers below.
            for j5 in wrong:
                for a5 in acts:
                    k5c = (ctx(cfg, j5), cfg[j5], a5)
                    if a5 not in consulted and k5c not in prior                             and getattr(store, "contested", lambda k: False)(k5c):
                        _k5, chosen5 = k5c, a5
                        break
                if _k5 is not None:
                    break
        else:
            chosen5 = chosen
        # Ignorance has two structural forms, and both are consult opportunities: a key
        # never tried anywhere, and a key whose OWN RECORD contradicts itself (which is
        # what a landed rule or a peer's work feels like from inside -- measured: a
        # competent life meets zero never-tried keys and its knowledge loop starves).
        # Neither form says consulting is WISE; the mind's own licenses and its learned
        # veto still decide that.
        if (_k5 is not None and consult is not None and chosen5 not in consulted
                and (not store.has(_k5)
                     or getattr(store, "contested", lambda k: False)(_k5))
                and _k5 not in prior
                and getattr(store, "consult_worth", lambda v: None)(chosen5)
                    is not False
                and _consult_worth(store, _k5) != 0):
            text = consult(chosen5)
            _cog6 = getattr(store, "cognition", None)
            if _cog6 is not None and knowledge is not None:
                # THE CONSULT EVENT: judged later by whether anything this source said
                # got verified by the mind's own living (the earned ledger moves). A
                # pending judgement, in life currency, closed by knowledge.settle().
                knowledge.pending.append((_k5[0], _k5[1],
                                          {kk: vv for kk, vv in
                                           knowledge.earned.items()},
                                          getattr(store, "world_id", 0.0)))
            got = 0
            was_distrusted = False
            if text:
                import hashlib as _h
                src = "page:" + _h.sha256(text.encode("utf-8")).hexdigest()[:12]
                was_distrusted = src in distrusted
                if not was_distrusted:
                    from .grounded_language import claimed_transitions
                    ns = getattr(consult, "noun_state", None)
                    for line in text.splitlines():     # a man page: one verb's frame per line
                        verb = line.split(":")[0].strip()
                        for k2, v2 in claimed_transitions(line, verb, noun_state=ns).items():
                            if k2 not in prior and not store.has(k2):
                                prior[k2] = v2
                                src_of[k2] = src       # fuse = the fetched page
                                got += 1
                    if knowledge is not None and got:
                        knowledge.merge({k2: prior[k2] for k2, s2 in src_of.items()
                                         if s2 == src and k2 in prior}, src)
            if hasattr(store, "consult_learn"):
                store.consult_learn(chosen, got > 0)
            if got or text is None or was_distrusted:
                # a useful page answers the verb; a dry search closes it; a DISTRUSTED hit
                # closes it too (refetching a known liar forever burned the budget --
                # measured: demo part 10's lying arm fell 17 -> 60 before this line).
                # Only a FRESH junk hit leaves the verb open, and there the search body's
                # cursor guarantees the next attempt tries the NEXT hit.
                consulted.add(chosen5)
            steps += 1
            continue
        if i is None:                                          # tier 3: nothing known anywhere
            i = wrong[int(rng.integers(0, len(wrong)))]
            chosen = acts[int(rng.integers(0, len(acts)))]
        before, c0 = cfg[i], ctx(cfg, i)
        # THE MIND ASKS ITSELF WHETHER IT STILL BELIEVES ITSELF. Acting on a belief that
        # has gone stale costs the act AND the look that discovers it; looking first costs
        # only the look. So a prediction that this belief will break is worth exactly one
        # unit when it is right and costs exactly one when it is wrong -- break-even at
        # half, and nothing here is tuned.
        _sv = getattr(store, "_slot_vis", None)
        _cog = getattr(store, "cognition", None)
        _say = _cog.speak(c0, before, "hold") if _cog is not None else None
        _epi = getattr(store, "episteme", None)
        _prog = getattr(store, "invented", {}).get("look")
        if _prog is not None:
            _pv = _prog.side((float(before), float(c0), float(age),
                              float(getattr(store, "world_id", 0.0))),
                             getattr(store.mind, "synth_lib", None))
            _worth = (1 if _pv else 0) if _pv is not None else (
                _epi.worth(c0, before, "look") if _epi is not None else None)
        else:
            _worth = _epi.worth(c0, before, "look") if _epi is not None else None
        if _worth == 0:
            _stale = False               # its own record says this look reveals nothing
        elif _say is not None:
            _stale = (_say == 0)         # ATANOR'S OWN RULE decides, where licensed
        else:
            _stale = store.belief_query(
                c0, before, age,
                vis=(_sv[i] if _sv and i < len(_sv) else 0.0)) is False
        if selfmod and not fresh and _stale:
            cfg = world.config()
            learn_decay(bel, cfg)
            bel = list(cfg)
            store.bel = bel
            fresh = True
            age = 0
            before, c0 = cfg[i], ctx(cfg, i)
            steps += 1
            if steps >= budget:
                break
        bit = world.do(chosen, i)
        if hasattr(store, "mark_tried"):
            store.mark_tried((c0, before, chosen))   # trying is a fact of the life
        age += 1
        _own = store.get((c0, before, chosen))
        pred = _own if _own is not None else prior.get((c0, before, chosen))
        _epi_a = getattr(store, "episteme", None)
        _age_pre = age - 1
        observed = False
        if pred is None:
            LOOK_CAUSE["key never met"] += 1
            after = world.state(i)
            observed = True              # a key it has never seen: it must look
        elif _own is None:
            # TESTIMONY IS WORTH EXACTLY ONE LOOK (2026-09-10). The prediction came from
            # a claim -- a page's, or the earlier Self's -- not from anything this mind
            # observed. Believing it unseen let a claim whose destination was wrong,
            # while its "moves / does not move" bit happened to be right, pass every
            # check below: the one-lie tribunal only sees observed outcomes, so the
            # lie was never caught, the belief went wrong, and the next acts were filed
            # under a state the slot was never in (measured: 79 self claims, 3 caught,
            # a third of the goals). A claim may plan the act; the act's outcome must
            # be seen. Seen once, the key is the mind's own and the claim is spent.
            LOOK_CAUSE["verify a claim"] += 1
            after = world.state(i)
            observed = True
        else:
            moved = (pred != before)
            if moved != bool(bit):
                # THE WORLD JUST CONTRADICTED THE MIND. Its model said this act would
                # move (or not) and the world did the opposite -- which is what a peer's
                # commit or a changed rule feels like from the inside. Pay for a look
                # and start believing again from what is actually there.
                LOOK_CAUSE["the world contradicted the belief"] += 1
                cfg = world.config()
                learn_decay(bel, cfg)
                bel = list(cfg)
                age = 0
                if carry:
                    store.bel = bel
                after = cfg[i]
                observed = True
                before = before if pred is None else before
            else:
                after = pred if bit else before
        if observed and _epi_a is not None and getattr(store, "shop", None) is not None \
                and goal[i] is not None and chosen in acts:
            # the act as a lived moment, labelled ONLY by what was observed: did the
            # slot really reach the goal state after it. Inference is not evidence
            # (order 11 VII), and a planner's prediction is not a label.
            from .machine_shop import token as _tok
            _epi_a.note(c0, before, "act", after == goal[i],
                        feats=(float(before), float(c0), float(goal[i]), float(_age_pre),
                               float(getattr(store, "world_id", 0.0)), _tok(chosen)))
        if exo is not None:
            exo["acted"] = i
            exo["last"][i] = after
        k = (c0, before, chosen)
        if k in prior and prior[k] != after:
            bad = src_of.get(k, "claims")       # the SOURCE lied once: drop all ITS claims
            if bad.startswith("self:"):
                # the Self's own past lied about THIS key (a state that had moved, a
                # rare edge seen once): that claim dies alone; the rest of what it
                # remembers keeps its per-context license and keeps being judged
                prior.pop(k, None)
                src_of.pop(k, None)
                if knowledge is not None:
                    knowledge.claims.pop(k, None)
                    knowledge.src.pop(k, None)
            else:
                for k2 in [q for q, sc in src_of.items() if sc == bad]:
                    prior.pop(k2, None)
                    src_of.pop(k2, None)
                if bad != "claims":
                    distrusted.add(bad)             # that PAGE lied; other sources stay usable
                    if knowledge is not None:
                        knowledge.drop_source(bad)  # ... and stops being known, for life
        # ONLY WHAT WAS OBSERVED MAY ENTER MEMORY (order 11 VII: evidence forgery).
        # When the prediction and the move-bit agree, `after` is the mind's own
        # inference returning -- writing it down would let any generalizing answerer
        # (a rule, the leader, a claim) file its guesses as experience and then earn
        # support from its own echo. Measured: ATANOR's rules reached route planning,
        # self-confirmed through this line, drifted from the changed world and cost a
        # young life 70% of its goals. Belief may carry inference; memory may not.
        if observed:
            # the pre-state of this transition was a FACT only if the belief it came
            # from was fresh (age 0: just observed); otherwise the key names a state the
            # mind assumed -- kept in this life's record as always, but not a fact the
            # next life may inherit (measured 2026-09-10: a few such edges, replayed,
            # cost redis 75% and mountain 99% of their goals)
            store.put(k, after, steps, fresh=(_age_pre == 0))
        if bel is not None:
            bel[i] = after
        steps += 1
    return budget


def study_agent(world, budget, rng, store):
    """AN EPISTEMIC LIFE: spends its acts buying the evidence its transition model lacks.

    The sealed exploration doctrine (act where knowledge is thin) applied to model
    building: at each step, list the (context, state, action) keys the store has never
    experienced; if the CURRENT state of some slot offers one, probe it; otherwise use
    KNOWN routes (BFS, as in plan_agent) to drive some slot toward the nearest state that
    unlocks an untried key, and probe there. Goal-free by design -- its product is the
    MODEL, priced in the same real acts as everything else."""
    acts = getattr(world, "actions", ACTIONS)
    par = getattr(world, "parents", PARENT)
    n = len(par)
    ctx = lambda cfg, i: DIR if par[i] < 0 else cfg[par[i]]

    def first_step(c0, cur, want):
        from collections import deque
        q = deque([cur])
        seen = {cur}
        parent = {}
        while q:
            s = q.popleft()
            for a in acts:
                k = (c0, s, a)
                nxt = store.get(k)
                if nxt is None or nxt in seen or nxt == s:
                    continue
                parent[nxt] = (s, a)
                if nxt == want:
                    while parent[nxt][0] != cur:
                        nxt = parent[nxt][0]
                    return parent[nxt][1]
                seen.add(nxt)
                q.append(nxt)
        return None

    steps = 0
    while steps < budget:
        cfg = world.config()
        if hasattr(store, "observe"):
            store.observe(cfg)
        i = chosen = None
        for j in range(n):                                  # probe an untried key HERE
            untried = [a for a in acts if not store.has((ctx(cfg, j), cfg[j], a))]
            if untried:
                i, chosen = j, untried[0]
                break
        if i is None:                                       # travel to the nearest untried key
            best = None
            for j in range(n):
                c0 = ctx(cfg, j)
                for want in range(4):
                    if want == cfg[j]:
                        continue
                    if any(not store.has((c0, want, a)) for a in acts):
                        a0 = first_step(c0, cfg[j], want)
                        if a0 is not None:
                            best = (j, a0)
                            break
                if best:
                    break
            if best is None:
                return steps                                # nothing reachable left to learn
            i, chosen = best
        before, c0 = world.state(i), ctx(cfg, i)
        world.do(chosen, i)
        store.put((c0, before, chosen), world.state(i), steps)
        steps += 1
    return steps


# --- REAL PROCESS world: the OS process lifecycle as a fifth family --------------------------

PROC_NSLOT = 5
PROC_ACTIONS = ("spawn", "kill", "reap")
P_ABSENT, P_RUNNING, P_DONE = 0, 1, 2


class ProcWorld:
    """REAL child processes: each slot is an OS process handle that is absent / running /
    finished-unreaped, moved by real spawn / kill / reap with the operating system's own
    verdicts (you cannot kill what does not run; you cannot reap what has not finished).
    The lifecycle is a CYCLE -- absent -> running -> done -> absent -- the first family
    where reaching a state can require going THROUGH the cycle (done -> running takes
    reap then spawn), which is exactly what planning over a learned graph is for."""

    parents = (-1,) * PROC_NSLOT
    actions = PROC_ACTIONS

    def __init__(self, seed):
        import subprocess
        self._sub = subprocess
        self.rng = np.random.default_rng(seed)
        self.procs = [None] * PROC_NSLOT

    def state(self, i):
        p = self.procs[i]
        if p is None:
            return P_ABSENT
        return P_RUNNING if p.poll() is None else P_DONE

    def config(self):
        return tuple(self.state(i) for i in range(PROC_NSLOT))

    def do(self, action, i):
        import sys as _sys
        s = self.state(i)
        try:
            if action == "spawn":
                if s != P_ABSENT:
                    return False
                self.procs[i] = self._sub.Popen(
                    [_sys.executable, "-c", "import time; time.sleep(3600)"],
                    stdout=self._sub.DEVNULL, stderr=self._sub.DEVNULL)
                return True
            if action == "kill":
                if s != P_RUNNING:
                    return False
                self.procs[i].kill()
                self.procs[i].wait(timeout=10)
                return True
            if action == "reap":
                if s != P_DONE:
                    return False
                self.procs[i] = None
                return True
        except Exception:
            return False
        return False

    def dispose(self):
        for p in self.procs:
            if p is not None and p.poll() is None:
                try:
                    p.kill()
                    p.wait(timeout=10)
                except Exception:
                    pass
        self.procs = [None] * PROC_NSLOT


def proc_goal(seed):
    g = tuple(int(x) for x in np.random.default_rng(seed).integers(0, 3, PROC_NSLOT))
    return g if any(g) else (P_RUNNING,) + g[1:]


class AsyncProcWorld(ProcWorld):
    """THE WORLD MOVES ON ITS OWN CLOCK: children exit by themselves after a real, finite
    lifetime, so RUNNING is a DECAYING state -- between any two of the mind's acts, slots
    it already fixed may quietly fall to DONE. A configuration here cannot merely be
    reached; it must be HELD. Nothing about the decay is told to the mind."""

    def __init__(self, seed, life_lo=1.5, life_hi=3.0):
        super().__init__(seed)
        self.life_lo, self.life_hi = life_lo, life_hi

    def do(self, action, i):
        import sys as _sys
        s = self.state(i)
        try:
            if action == "spawn":
                if s != P_ABSENT:
                    return False
                dur = float(self.rng.uniform(self.life_lo, self.life_hi))
                self.procs[i] = self._sub.Popen(
                    [_sys.executable, "-c", "import time; time.sleep(%f)" % dur],
                    stdout=self._sub.DEVNULL, stderr=self._sub.DEVNULL)
                return True
            return super().do(action, i)
        except Exception:
            return False


def held(world, goal, gap=0.3):
    """A configuration counts only if it is VERIFIED TWICE across a real time gap --
    a transient coincidence in a decaying world is not achievement."""
    import time as _t
    if world.config() != goal:
        return False
    _t.sleep(gap)
    return world.config() == goal


class TickProcWorld(ProcWorld):
    """ASYNCHRONY MADE REPRODUCIBLE: children are real OS processes, but their lifetimes
    are counted in WORLD TICKS -- every act of the mind advances the world's clock one
    tick, and the world enforces each child's seeded deadline (a real kill on the real
    process). From the mind's side nothing changed: slots it fixed quietly fall to DONE
    between its acts, uncaused by anything it did. From the gate's side everything
    changed: the dynamics are seeded, so a reading is exactly reproducible -- the
    wall-clock variant measured the MACHINE's spawn latency, not the mind (dev: 16/16 or
    5/16 flipping on load), which is disclosed in the prereg."""

    def __init__(self, seed, life_lo=4, life_hi=9):
        super().__init__(seed)
        self.life_lo, self.life_hi = life_lo, life_hi
        self.deadline = [None] * PROC_NSLOT
        self.tick = 0

    def _advance(self):
        self.tick += 1
        for j in range(PROC_NSLOT):
            if self.deadline[j] is not None and self.tick >= self.deadline[j] \
                    and self.procs[j] is not None and self.procs[j].poll() is None:
                try:
                    self.procs[j].kill()
                    self.procs[j].wait(timeout=10)
                except Exception:
                    pass
                self.deadline[j] = None

    def tick_noop(self):
        """The world's clock advances even when the mind only watches."""
        self._advance()

    def do(self, action, i):
        self._advance()
        ok = ProcWorld.do(self, action, i)
        if ok and action == "spawn":
            self.deadline[i] = self.tick + int(self.rng.integers(self.life_lo, self.life_hi))
        if ok and action in ("kill", "reap"):
            self.deadline[i] = None
        return ok


def held_ticks(world, goal, gap=2):
    """Verified across GAP world ticks in which the mind does nothing -- a transient
    coincidence in a decaying world is not achievement."""
    if world.config() != goal:
        return False
    for _ in range(gap):
        world.tick_noop()
    return world.config() == goal
