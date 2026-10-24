

# ---------------- sealed evaluation (teacher off) ----------------
def _nwords(s):
    return ' '.join(re.findall(r'[a-z]+', s.lower()))


def evaluate(state_path, sealed_path, commit_hash, out, conditions=('ORACLE', 'N', 'M', 'S', 'F'), n_possible=30, n_impossible=6,
             protocol=None):
    teacher_off()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    snap = load_snapshot()
    pools = split(snap)
    sealed_bytes = Path(sealed_path).read_bytes()
    sealed = json.loads(sealed_bytes)['sentences']
    sentences = {f: [x['sentence'] for x in sealed if x['form'] == f] for f in FORMS}
    trained = json.loads((Path(state_path).parent / 'train_sentences.json').read_text(encoding='utf-8'))
    trained += json.loads((Path(state_path).parent / 'dev_sentences.json').read_text(encoding='utf-8'))
    overlap = sorted({_nwords(s) for s, _ in trained} & {_nwords(x['sentence']) for x in sealed})
    tl = json.loads((Path(state_path).parent / 'train_log.json').read_text(encoding='utf-8'))
    ext_overlap = sorted(set(pools['eval']) & (set(tl['teach_exts']) | set(tl['dev_exts'])))
    seed = int(hashlib.sha256(commit_hash.encode()).hexdigest(), 16) % (2 ** 31)
    specs = [{'index': i, 'exts': pools['eval'], 'impossible': i >= n_possible} for i in range(n_possible + n_impossible)]
    rows, extra = {}, {}
    for c in conditions:
        rows[c], extra[c] = run_condition(c, specs, state_path, out / c, snap, sentences, 'eval', seed)
    summ = summarize(rows)
    checks = {'teacher_import_attempts': list(_NoTeacher.attempts),
              'teacher_module_loaded': any(m.startswith('atanor_os.teach') for m in sys.modules),
              'llm_or_local_host_attempts': {c: e['llm_or_local_host_attempts'] for c, e in extra.items()},
              'sentence_overlap_with_training': overlap, 'extension_overlap_with_training': ext_overlap,
              'sealed_sha256': hashlib.sha256(sealed_bytes).hexdigest(), 'commit_hash': commit_hash, 'seed': seed,
              'oracle_completion': summ.get('ORACLE', {}).get('completion')}
    res = {'summary': summ, 'F_vs_N': paired(rows['F'], rows['N']), 'F_vs_S': paired(rows['F'], rows['S']),
           'F_vs_M': paired(rows['F'], rows['M']), 'checks': checks, 'secondary': secondary(rows, out), 'extra': extra}
    res['verdict'] = verdict(res, protocol or {})
    (out / 'p6_result.json').write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    (out / 'p6_rows.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    return res


def secondary(rows, out):
    """Trigger validity, evidence validity, conflict handling, from the traces and the local web archive."""
    import gzip
    s = {}
    for c, rs in rows.items():
        if c == 'ORACLE':
            continue
        invalid_triggers, info, evid_ok, evid_n = 0, 0, 0, 0
        conflicts = {'adopted_despite_disagreement': 0, 'stopped_contradiction': 0, 'stopped_single_source': 0}
        known, adopted = set(), {}
        for r in rs:
            for t in r['trace']:
                if t['action'] in ('search', 'open', 'follow') and t.get('ext'):
                    info += 1
                    invalid_triggers += int(t['ext'] in known and t['action'] == 'search')
                if t['action'] in ('recall', 'compare'):
                    known.add(t.get('ext'))
                if t['action'] == 'compare':
                    adopted[t['ext']] = (t['name'], t['sources'])
                    conflicts['adopted_despite_disagreement'] += int(bool(t.get('disagreeing')))
                if t['action'] == 'stop_fact':
                    conflicts['stopped_contradiction'] += int(t.get('reason') == 'contradiction')
                    conflicts['stopped_single_source'] += int(t.get('reason') == 'single_source')
        arch = out / c / 'web' / 'pages'
        sha_of = {}
        for r in rs:
            for t in r['trace']:
                if t['action'] == 'open' and t.get('ok') and t.get('sha256'):
                    sha_of[t['url']] = t['sha256']
        for ext, (name, sources) in adopted.items():
            for u in sources:
                p = arch / f"{sha_of.get(u, '')}.json.gz"
                if u in sha_of and p.exists():
                    text = json.loads(gzip.decompress(p.read_bytes()))['text'].lower()
                    evid_n += 1
                    evid_ok += int(name.lower() in text and ext.lower() in text)
        s[c] = {'information_actions': info, 'searches_for_already_known_fact': invalid_triggers, 'conflicts': conflicts,
                'evidence_pages_checked': evid_n, 'evidence_pages_with_name_and_extension': evid_ok}
    return s


def verdict(res, protocol):
    ck, sm = res['checks'], res['summary']
    invalid = (ck['teacher_import_attempts'] or ck['teacher_module_loaded'] or any(ck['llm_or_local_host_attempts'].values())
               or ck['sentence_overlap_with_training'] or ck['extension_overlap_with_training'] or (ck['oracle_completion'] or 0) < 1.0)
    if invalid:
        return 'INVALID'
    F, d = sm['F'], res['F_vs_N']['mean_pp']
    gain = (d >= protocol.get('min_gain_pp', 30) and F['completion'] >= protocol.get('min_completion', 0.5)
            and F['correct_stops'] >= protocol.get('min_correct_stops_frac', 2 / 3) * F['impossible_tasks']
            and F['wrong_placements_per_task'] <= protocol.get('max_wrong_per_task', 0.5))
    if gain:
        return 'GAIN'
    if d <= 0 or F['completion'] < protocol.get('no_gain_completion', 0.2):
        return 'NO_GAIN'
    return 'INCONCLUSIVE'
