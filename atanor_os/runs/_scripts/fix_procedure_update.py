"""v8: a procedure step whose tool was replaced by a working substitute is remembered with the substitute."""
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
old = """            substituted = False
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
                            break"""
new = """            substituted, new_proc = False, []
            for tool, rels in proc:
                if any(path[r] is None for r in rels):
                    new_proc = None
                    break
                args = tuple(path[r] for r in rels)
                ok, _ = self._try(lab, tool, args, 'lab')
                self.counts['lab_actions'] += 1
                self.counts['lab_analogy'] += 1
                step = [tool, list(rels)]
                if not ok:                                     # the known step fails: a tool that never worked may do it now
                    worked = {e.tool for e in self.episodes if e.succeeded}
                    for alt in sorted(t for t, ar in lab.tools().items() if t not in worked and ar == len(args)):
                        for order in ([list(rels), list(rels)[::-1]] if len(args) > 1 else [list(rels)]):
                            ok, _ = self._try(lab, alt, tuple(path[r] for r in order), 'lab')
                            self.counts['lab_actions'] += 1
                            self.counts['lab_substitute'] += 1
                            if ok:
                                substituted, step = True, [alt, order]
                                break
                        if ok:
                            break
                new_proc.append(step)
            if substituted and new_proc:
                self.procedures[goal.id.split(':', 1)[-1]] = new_proc      # the procedure that works now
                self.save()"""
assert old in s, 'anchor'; p.write_bytes(s.replace(old, new, 1).encode('utf-8')); print('procedure update ok')
