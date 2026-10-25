"""General fixes after the seed-2 evaluation (applied after that evaluation was committed)."""
import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# 1. trust: a rule is trusted when a counter-example backs it, OR it explains every known failure of the tool and
#    has enough support (a tool that never failed in many tries is trusted for the argument kinds that succeeded)
rep("""        backed = sum(g.get('ev', {}).values()) > 0
        if k in self.kinds_ok[tool] and backed:
            return 'learned', g
        return 'unknown', None""", """        backed = sum(g.get('ev', {}).values()) > 0 or (g.get('unexplained', 0) == 0 and g['support'] >= 3)
        if k in self.kinds_ok[tool] and backed:
            return 'learned', g
        return 'unknown', None""")
# 2. a word's selection meaning counts only after two uses (one use over-fits to its first objects)
rep("""            if t != dest and t not in self.neutral and self.word_n[t] and self.meaning.get(t):
                cons |= self.meaning[t]""", """            if t != dest and t not in self.neutral and self.word_n[t] >= 2 and self.meaning.get(t):
                cons |= self.meaning[t]""")
# 3. ambiguity = disagreement among informative words (or none), not a posterior threshold
rep("""        pid, ambiguous = None, False
        if informative and pids:
            m = max(logp.values())
            z = sum(math.exp(v - m) for v in logp.values())
            post = {q: math.exp(v - m) / z for q, v in logp.items()}
            pid = max(post, key=post.get)
            ambiguous = post[pid] < 0.8                     # the words do not agree enough on one change""",
    """        pid, ambiguous = None, False
        if informative and pids:
            pid = max(logp, key=logp.get)
            tops = set()
            for t in toks:
                pc = self.pattern_of.get(t)
                if t in values or t == dest or not pc or t in self.neutral:
                    continue
                n = sum(pc.values())
                probs = [(pc[q] + 0.1) / (n + 0.1 * len(pids)) for q in pids]
                ent = -sum(x * math.log(x) for x in probs) / math.log(len(pids)) if len(pids) > 1 else 0.0
                if 1.0 - ent >= 0.3:                        # an informative word: it mostly goes with one change
                    tops.add(pc.most_common(1)[0][0])
            ambiguous = len(tops) != 1 or pid not in tops   # informative words disagree, or none exists""")
# 4. acting: the action budget follows the goal's size; after a budget-stopped full plan, plan sub-goals directly
rep("""    def _achieve(self, goal, task_id):
        ws = self.home
        avoid = set()
        for step in range(BUDGET['actions']):""", """    def _achieve(self, goal, task_id):
        ws = self.home
        avoid = set()
        self._subgoals_only = False
        limit = BUDGET['actions'] + 3 * len(getattr(goal, 'selected', []) or [])
        for step in range(limit):""")
rep("""        state = ws.observe(goal.universe)
        cap = getattr(ws, 'CAPABILITY', {})
        p, pst = plan(state, goal, self.model, ws.actions(self._focus(goal)), avoid, cap)
        if p or pst['stop'] == 'exhausted':
            return p, pst
        self.counts['subgoals'] += 1""", """        state = ws.observe(goal.universe)
        cap = getattr(ws, 'CAPABILITY', {})
        if not getattr(self, '_subgoals_only', False):
            p, pst = plan(state, goal, self.model, ws.actions(self._focus(goal)), avoid, cap)
            if p or pst['stop'] == 'exhausted':
                return p, pst
            self._subgoals_only = True                       # the whole goal is too big to search: object by object from here
        self.counts['subgoals'] += 1""")
p.write_bytes(s.encode('utf-8'))
print('ok')
