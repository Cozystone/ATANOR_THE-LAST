"""Skill (macro) extraction from the agent's own successful traces, and reuse in planning (hypothesis H2).

A macro is a pair of tools whose argument slots are structurally related ('eq' = same object,
'child' = the later argument lies directly under the earlier one). Macros are extracted from
goal-directed episodes the agent itself completed (training tasks, never test tasks) and must
recur in at least `min_support` episodes. In planning a macro instance is one candidate action
that expands to its two primitive steps; execution always performs primitives one at a time.
No new actuator is invented: a macro only orders existing tools.
"""
from ..world.fs_world import parent_of
from .models import RuleModel


def relations(args_a, args_b):
    """For each slot of step b: ('eq', i) if equal to slot i of step a, ('child', i) if its parent is
    slot i of step a, else None. Argument-level structure only; no attribute values."""
    rel = []
    for x in args_b:
        r = None
        for i, y in enumerate(args_a):
            if x == y:
                r = ('eq', i)
                break
            if parent_of(x) == y:
                r = ('child', i)
                break
        rel.append(r)
    return tuple(rel)


class Macro:
    def __init__(self, tool_a, tool_b, rel, support=0):
        self.tool_a, self.tool_b, self.rel, self.support = tool_a, tool_b, rel, support

    def key(self):
        return (self.tool_a, self.tool_b, self.rel)

    def instances(self, actions):
        """All (step_a, step_b) pairs of candidate primitive actions that satisfy the relations."""
        a_list = [a for a in actions if a[0] == self.tool_a]
        b_list = [b for b in actions if b[0] == self.tool_b]
        return [('macro', (a, b)) for a in a_list for b in b_list if relations(a[1], b[1]) == self.rel]

    def to_json(self):
        return {'tool_a': self.tool_a, 'tool_b': self.tool_b, 'rel': [list(r) if r else None for r in self.rel],
                'support': self.support}


def extract_macros(traces, min_support=2):
    """traces: successful action sequences [(tool, args), ...] from completed episodes.
    Only consecutive pairs with at least one structural relation count as a procedure."""
    counts = {}
    for acts in traces:
        seen = set()
        for (ta, aa), (tb, ab) in zip(acts, acts[1:]):
            rel = relations(aa, ab)
            if all(r is None for r in rel):
                continue
            seen.add((ta, tb, rel))
        for k in seen:
            counts[k] = counts.get(k, 0) + 1
    return sorted((Macro(*k, support=n) for k, n in counts.items() if n >= min_support),
                  key=lambda m: (-m.support, m.key()))


class SkillModel(RuleModel):
    """E: C plus macros extracted from the agent's own completed training episodes."""
    name = 'E'

    def __init__(self, experiences=(), spec=None):
        super().__init__(experiences, spec)
        self.macros = []
        self.traces = []

    def learn_traces(self, traces, min_support=2):
        self.traces = list(traces)
        self.macros = extract_macros(self.traces, min_support)
        return self.macros

    def expand_actions(self, actions):
        out = list(actions)
        for m in self.macros:
            out += m.instances(actions)
        return out

    def describe(self):
        d = super().describe()
        d.update(condition=self.name, macros=[m.to_json() for m in self.macros], traces=len(self.traces))
        return d
