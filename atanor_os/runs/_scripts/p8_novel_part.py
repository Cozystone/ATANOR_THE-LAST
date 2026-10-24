

def training_keys(exp):
    """Exact (tool, args, full pre-state) of every training experience: an unseen situation must differ."""
    keys = set()
    for es in exp.values():
        for e in es:
            keys.add(_key(e.tool, e.args, e.pre))
    return keys


def _key(tool, args, pre):
    return hashlib.sha256(json.dumps([tool, list(args), sorted((p, sorted(o.items())) for p, o in pre.items())], default=str).encode()).hexdigest()


def novel_agreement(model, k, seed, root, block, pre_fn, train_keys, max_blocks=400):
    """rule_agreement's stratified sampler (>= k per (tool, true outcome) cell, near-miss failures first),
    restricted to situations that do NOT occur in the training log; excluded samples are counted."""
    from .explore import ALL_CAPS
    from ..agent.lift import effect_attrs
    rng = random.Random(seed)
    root = Path(root)
    cells, near_cells, per_tool, excluded, block_i = None, {}, {}, 0, 0
    while block_i < max_blocks and (cells is None or min(cells.values()) < k):
        ws, targets = block(rng, root / f'b{block_i}')
        if cells is None:
            cells = {f'{t}:{o}': 0 for t in ws.TOOLS for o in ('success', 'failure')}
            near_cells = {t: 0 for t in ws.TOOLS}
            per_tool = {t: {'checks': 0, 'fp': 0, 'fn': 0, 'eff': 0, 'near_checks': 0} for t in ws.TOOLS}
        for _ in range(25):
            if min(cells.values()) >= k:
                break
            pre = ws.observe(targets)
            buckets, succ_args = {}, {}
            for tool, args in ws.actions(sorted(pre)):
                if _key(tool, args, pre) in train_keys:
                    excluded += 1
                    continue
                ok = pre_fn(pre, tool, args)
                buckets.setdefault(f"{tool}:{'success' if ok else 'failure'}", []).append((tool, args))
                if ok:
                    succ_args.setdefault(tool, []).append(args)
            for tool, sa in succ_args.items():
                near = [(t, a) for t, a in buckets.get(f'{tool}:failure', []) if any(sum(x != y for x, y in zip(a, s_)) == 1 for s_ in sa)]
                if near:
                    buckets[f'{tool}:near'] = near
            needy = [c for c in buckets if (near_cells[c.split(':')[0]] if c.endswith(':near') else cells[c]) < k]
            if not needy:
                break
            nn = [c for c in needy if c.endswith(':near')]
            cell = rng.choice(nn or needy)
            tool, args = rng.choice(buckets[cell])
            predicted, _ = model.predict(pre, tool, args)
            res = ws.execute(tool, args, ALL_CAPS)
            post = ws.observe(list(pre))
            is_near = cell.endswith(':near')
            if is_near:
                near_cells[tool] += 1
                cells[f'{tool}:failure'] += 1
            else:
                cells[cell] += 1
            pt = per_tool[tool]
            pt['checks'] += 1
            pt['near_checks'] += int(is_near)
            if predicted is not None and not res['ok']:
                pt['fp'] += 1
            elif predicted is None and res['ok']:
                pt['fn'] += 1
            elif res['ok'] and not all(predicted[a][k_] in ('unknown', post[a].get(k_)) for a in args for k_ in effect_attrs(predicted[a])):
                pt['eff'] += 1
        block_i += 1
    filled = bool(cells) and min(cells.values()) >= k
    return {'per_tool': per_tool, 'cells': cells, 'near_cells': near_cells, 'filled': filled, 'excluded_training_situations': excluded}
