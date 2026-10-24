import pathlib

p = pathlib.Path('atanor_os/eval/p8b.py')
s = p.read_text(encoding='utf-8')


def rep(old, new):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, 1)


SAMPLER = '''# ---------------- changed-tool sampler (amendment 1.1) ----------------
def drift_block(body, drift):
    """Workspaces shaped like the drift tasks (indices disjoint from the 20 evaluation drift tasks)."""
    def block(rng, root):
        ws, goal, _ = drift_task(body, rng.randrange(1000, 3000), root)
        _set_drift(ws, drift)
        return ws, (goal.universe if body == 'fs' else [])
    return block


def situation_agreement(model, body, drift, changed, k, seed, root, train_keys, max_blocks=300):
    """Checks of the changed tool only. changed=True: situations where the original and the changed rule disagree
    (k checks); changed=False: situations where they agree (k true successes and k true failures)."""
    from .explore import ALL_CAPS
    from ..agent.lift import effect_attrs
    from .p8 import _key
    tool, new_pre, old_pre = CHANGED_TOOL[body], pre_fn(body, drift), pre_fn(body, frozenset())
    rng, root = random.Random(seed), Path(root)
    cells = {'success': 0, 'failure': 0}

    def need():
        return cells['success'] + cells['failure'] < k if changed else min(cells.values()) < k
    r = {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'excluded_training_situations': 0}
    blocks = (drift_block(body, drift), test_block(body, drift))
    b = 0
    while b < max_blocks and need():
        ws, targets = blocks[b % 2](rng, root / f'b{b}')
        for _ in range(25):
            if not need():
                break
            pre = ws.observe(targets)
            cand = {'success': [], 'failure': []}
            for t, args in ws.actions(ws.universe(targets) if body == 'fs' else sorted(pre)):
                if t != tool or (new_pre(pre, t, args) != old_pre(pre, t, args)) != changed:
                    continue
                if _key(t, args, pre) in train_keys:
                    r['excluded_training_situations'] += 1
                    continue
                cand['success' if new_pre(pre, t, args) else 'failure'].append(args)
            open_cells = [c for c in cand if cand[c] and (changed or cells[c] < k)]
            if not open_cells:
                break
            c = rng.choice(open_cells)
            args = rng.choice(cand[c])
            predicted, _ = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            cells[c] += 1
            r['checks'] += 1
            if predicted is not None and not res['ok']:
                r['fp'] += 1
            elif predicted is None and res['ok']:
                r['fn'] += 1
            elif res['ok'] and not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a in args for k_ in effect_attrs(predicted[a])):
                r['eff'] += 1
        b += 1
    r['cells'] = cells
    r['accuracy'] = 1 - (r['fp'] + r['fn'] + r['eff']) / max(1, r['checks'])
    return r


# ---------------- ATANOR's re-verification'''

rep("# ---------------- ATANOR's re-verification", SAMPLER)
rep("""            r = {'bytes': size, 'prediction': acc['accuracy'], 'checks': acc['checks'], 'fp': acc['fp'], 'fn': acc['fn'], 'eff': acc['eff'],
                 'changed_tool_prediction': a_of([ch]), 'other_tools_prediction': a_of([t for t in pt if t != ch]),""",
    """            r = {'bytes': size, 'prediction': acc['accuracy'], 'checks': acc['checks'], 'fp': acc['fp'], 'fn': acc['fn'], 'eff': acc['eff'],
                 'changed_tool_prediction_mixed': a_of([ch]), 'other_tools_prediction': a_of([t for t in pt if t != ch]),""")
rep("""            if scen == 'drift':
                r['drift_tasks'] = _tasks(model, body, scen, out / scen, 'drift')""",
    """            if scen == 'drift':
                sa = 9300 + (body == 'view')
                r['changed_situations'] = situation_agreement(model, body, drift, True, k, sa, out / f'chg_{body}', keys)
                r['changed_tool_unchanged_situations'] = situation_agreement(model, body, drift, False, k, sa + 2, out / f'unchg_{body}', keys)
                r['drift_tasks'] = _tasks(model, body, scen, out / scen, 'drift')""")
rep("""             'drift_changed_pred': dr['changed_tool_prediction'], 'R1_drift_changed_pred': R1[f'drift_{body}']['changed_tool_prediction'],
             'drift_other_pred': dr['other_tools_prediction'],""",
    """             'drift_changed_pred': dr['changed_situations']['accuracy'], 'R1_drift_changed_pred': R1[f'drift_{body}']['changed_situations']['accuracy'],
             'drift_changed_checks': dr['changed_situations']['checks'],
             'drift_other_pred': dr['other_tools_prediction'], 'drift_changed_tool_unchanged_pred': dr['changed_tool_unchanged_situations']['accuracy'],""")
rep("""              and c['drift_other_pred'] >= 0.95 and""",
    """              and c['drift_changed_checks'] >= 20 and c['drift_other_pred'] >= 0.95 and c['drift_changed_tool_unchanged_pred'] >= 0.95 and""")
rep("""             'stable_completion': comp(P, f'stable_{body}') if False else sum(x['completed'] for x in st['test_tasks']) / len(st['test_tasks']),""",
    """             'stable_completion': sum(x['completed'] for x in st['test_tasks']) / len(st['test_tasks']),""")
rep("""        comp = lambda r, key: sum(x['completed'] for x in r[key]) / len(r[key])
""", "")
p.write_text(s, encoding='utf-8')
print('ok')
