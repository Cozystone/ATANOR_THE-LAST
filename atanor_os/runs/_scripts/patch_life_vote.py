import pathlib

p = pathlib.Path('atanor_os/agent/life.py')
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert a in s, a[:70]
    s = s.replace(a, b, 1)


# naive-Bayes combination of each word's distribution over changes; ambiguous if the best change is below 0.8
rep("""        votes = Counter()
        for t in toks:
            pc = self.pattern_of.get(t)
            if t in values or t == dest:
                continue                                    # a word that names objects does not name the change
            if pc and t not in self.neutral:
                top, n = pc.most_common(1)[0]
                if n / sum(pc.values()) >= 0.75:
                    votes[top] += 1
        pid = votes.most_common(1)[0][0] if votes else None
        ambiguous = len(votes) > 1                          # words in one sentence point to different changes""",
"""        pids = sorted({q for c in self.pattern_of.values() for q in c})
        logp = {q: 0.0 for q in pids}
        informative = 0
        for t in toks:
            pc = self.pattern_of.get(t)
            if t in values or t == dest or not pc or t in self.neutral:
                continue                                    # a word that names objects does not name the change
            informative += 1
            n = sum(pc.values())
            for q in pids:
                logp[q] += math.log((pc[q] + 0.5) / (n + 0.5 * len(pids)))
        pid, ambiguous = None, False
        if informative and pids:
            m = max(logp.values())
            z = sum(math.exp(v - m) for v in logp.values())
            post = {q: math.exp(v - m) / z for q, v in logp.items()}
            pid = max(post, key=post.get)
            ambiguous = post[pid] < 0.8                     # the words do not agree enough on one change""")
rep("""import hashlib
import json
import random""", """import hashlib
import json
import math
import random""")
# after being shown how, look for counter-examples of the shown steps before trusting them
rep("""        steps = self.user.demonstrate_goal(goal)                  # last resort: be shown how, in the lab
        self.counts['demonstrate_how'] += 1
        lab = self._lab(objs, None)
        for tool, args in steps:
            self._try(lab, tool, tuple(args), 'demo')
        p, _ = self._plan(self.home, goal)
        return bool(p)""", """        steps = self.user.demonstrate_goal(goal)                  # last resort: be shown how, in the lab
        self.counts['demonstrate_how'] += 1
        lab = self._lab(objs, None)
        for tool, args in steps:
            self._try(lab, tool, tuple(args), 'demo')
        p, _ = self._plan(self.home, goal)
        if p:
            return True
        # what was shown worked, but a generalisation without counter-examples is not yet trusted: test it
        user, self.user = self.user, None
        try:
            ok = self._experiment(goal)
        finally:
            self.user = user
        self.log(event='after_demonstration_experiments', resolved=ok)
        return ok""")
p.write_bytes(s.encode('utf-8'))
print('ok')
