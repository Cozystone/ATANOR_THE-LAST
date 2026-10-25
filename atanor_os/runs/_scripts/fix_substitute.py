"""v8: curiosity about untried tools. Replaying a remembered procedure in the lab, a step whose tool fails is retried
with every tool that never succeeded and has the same arity, in both argument orders, before random experiments."""
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
old = """            for tool, rels in proc:
                if any(path[r] is None for r in rels):
                    break
                self._try(lab, tool, tuple(path[r] for r in rels), 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_analogy'] += 1
            if self._plannable(goal):
                self.log(event='experiment_resolved', how='analogy', lab_actions=len(proc))"""
new = """            substituted = False
            for tool, rels in proc:
                if any(path[r] is None for r in rels):
                    break
                args = tuple(path[r] for r in rels)
                ok, _ = self._try(lab, tool, args, 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_analogy'] += 1
                if not ok:                                     # the known step fails: a tool that never worked may do it now
                    worked = {e.tool for e in self.episodes if e.succeeded}
                    for alt in sorted(t for t, ar in lab.tools().items() if t not in worked and ar == len(args)):
                        for cand in ([args, args[::-1]] if len(args) > 1 else [args]):
                            ok, _ = self._try(lab, alt, cand, 'lab')
                            self.counts['lab_actions'] += 1
                            self.counts['lab_substitute'] += 1
                            if ok:
                                substituted = True
                                break
                        if ok:
                            break
            if self._plannable(goal):
                self.log(event='experiment_resolved', how='substitute' if substituted else 'analogy', lab_actions=self.counts['lab_actions'] - spent0)"""
assert old in s, 'anchor'; p.write_bytes(s.replace(old, new, 1).encode('utf-8')); print('substitute ok')
