"""P7 evaluation (evaluator side): ATANOR's decision layer with and without a language model as its
reading tool. Same tasks, judge and decision procedure as P6; new formats, new sealed sentences.

Formats: Wikidata file formats with one English label, never used in P6 training, the H6 transfer set,
or the P6 pools (results/p7-truth/pool.json, built before the freeze). 32 are drawn with a seed from the
public hash of the freeze commit. Sentences: written by an agent without the teacher's context, kept
outside the repository; only their sha256 is published before the run.
Conditions: F_LM (model on), S_LM (model on, single source), F (model off), N (no web), ORACLE.
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

from ..agent.autonomy import FORMS
from ..agent.perception import OllamaBackend, Perception
from .h6 import transfer_set
from .p6 import PKG, _NoTeacher, paired, run_condition, secondary, summarize, teacher_off
from .web_truth import norm, split

P7 = PKG / 'results' / 'p7-truth'
MODEL = 'qwen2.5:7b-instruct'
MODEL_HOST = 'http://127.0.0.1:11435'


def build_pool():
    snap = json.loads((PKG / 'results' / 'p6-truth' / 'truth.json').read_text(encoding='utf-8'))
    extra = json.loads((PKG / 'results' / 'p6-truth' / 'train_extra.json').read_text(encoding='utf-8'))['formats']
    tl = json.loads((PKG / 'results' / 'p6-train' / 'train_log.json').read_text(encoding='utf-8'))
    held, dev, _ = transfer_set()
    used = set(tl['teach_exts']) | set(tl['dev_exts']) | set(held) | set(dev) | set(snap['formats'])
    pool = {}
    for e, labels in sorted(extra.items()):
        if e in used or len(labels) != 1:
            continue
        lab = labels[0]
        if len(lab) > 60 or norm(lab) == norm(e) or any(c in lab for c in '/\\:*?"<>|'):
            continue
        pool[e] = {'label': lab, 'aliases': []}
    P7.mkdir(parents=True, exist_ok=True)
    (P7 / 'pool.json').write_text(json.dumps({'built_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'formats': pool}, indent=1, ensure_ascii=False),
                                  encoding='utf-8')
    return pool


def evaluate_p7(state_path, sealed_path, commit_hash, out, protocol, n_eval=32, n_possible=30, n_impossible=6,
                conditions=('ORACLE', 'N', 'F', 'S_LM', 'F_LM')):
    teacher_off()
    if Path(sealed_path).resolve().is_relative_to(PKG.resolve()):
        raise RuntimeError('sealed_inside_repo')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    pool = json.loads((P7 / 'pool.json').read_text(encoding='utf-8'))['formats']
    seed = int(hashlib.sha256(commit_hash.encode()).hexdigest(), 16) % (2 ** 31)
    exts = sorted(random.Random(seed).sample(sorted(pool), n_eval))
    snapshot = {'formats': {e: pool[e] for e in exts}}
    sealed_bytes = Path(sealed_path).read_bytes()
    sealed = json.loads(sealed_bytes)['sentences']
    sentences = {f: [x['sentence'] for x in sealed if x['form'] == f] for f in FORMS}
    tdir = Path(state_path).parent                                 # teacher material exported before the run (no teacher import here)
    trained = [x[0] for x in json.loads((tdir / 'train_sentences.json').read_text(encoding='utf-8'))]
    trained += [x[0] for x in json.loads((tdir / 'h6_sentences.json').read_text(encoding='utf-8'))]
    trained += [x[0] for x in json.loads((tdir / 'dev_sentences.json').read_text(encoding='utf-8'))]
    nw = lambda t: ' '.join(t.lower().split())
    overlap = sorted({nw(t) for t in trained} & {nw(x['sentence']) for x in sealed})
    specs = [{'index': i, 'exts': exts, 'impossible': i >= n_possible} for i in range(n_possible + n_impossible)]

    def factory(d):
        return Perception(OllamaBackend(MODEL, host=MODEL_HOST), Path(d) / 'model_calls.jsonl')

    rows, extra = {}, {}
    for c in conditions:
        rows[c], extra[c] = run_condition(c, specs, state_path, out / c, snapshot, sentences, 'eval', seed, perception_factory=factory)
    summ = summarize(rows)
    calls = {}
    for c in conditions:
        f = out / c / 'model_calls.jsonl'
        rs = [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines()] if f.exists() else []
        calls[c] = {'calls': len(rs), 'prompt_tokens': sum((r.get('usage') or {}).get('prompt_tokens') or 0 for r in rs),
                    'output_tokens': sum((r.get('usage') or {}).get('output_tokens') or 0 for r in rs),
                    'seconds': round(sum(r.get('seconds', 0) for r in rs), 1), 'accepted': sum(len(r.get('accepted', [])) for r in rs),
                    'rejected_by_verification': sum(len(r.get('rejected', [])) for r in rs), 'errors': sum('error' in r for r in rs),
                    'digests': sorted({r.get('digest') for r in rs if r.get('digest')}), 'prompt_versions': sorted({r.get('prompt_version') for r in rs})}
    checks = {'teacher_import_attempts': list(_NoTeacher.attempts), 'teacher_module_loaded': any(m.startswith('atanor_os.teach') for m in sys.modules),
              'model_calls_in_model_off_conditions': sum(calls[c]['calls'] for c in conditions if not c.endswith('_LM')),
              'llm_or_local_host_attempts_by_web_body': {c: e['llm_or_local_host_attempts'] for c, e in extra.items()},
              'sentence_overlap_with_training': overlap, 'sealed_sha256': hashlib.sha256(sealed_bytes).hexdigest(),
              'commit_hash': commit_hash, 'seed': seed, 'eval_exts': exts, 'oracle_completion': summ['ORACLE']['completion']}
    res = {'summary': summ, 'F_LM_vs_N': paired(rows['F_LM'], rows['N']), 'F_vs_N': paired(rows['F'], rows['N']),
           'F_LM_vs_S_LM': paired(rows['F_LM'], rows['S_LM']), 'F_LM_vs_F': paired(rows['F_LM'], rows['F']),
           'model_cost': calls, 'checks': checks, 'secondary': secondary(rows, out)}
    res['verdict_with_tool'] = verdict_p7(res, 'F_LM', protocol)
    res['verdict_model_off'] = verdict_p7(res, 'F', protocol)
    (out / 'p7_result.json').write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    (out / 'p7_rows.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    return res


def verdict_p7(res, cond, protocol):
    ck, sm = res['checks'], res['summary']
    if (ck['teacher_import_attempts'] or ck['teacher_module_loaded'] or ck['model_calls_in_model_off_conditions']
            or any(ck['llm_or_local_host_attempts_by_web_body'].values()) or ck['sentence_overlap_with_training']
            or (ck['oracle_completion'] or 0) < 1.0):
        return 'INVALID'
    F = sm[cond]
    d = paired_pp(res, cond)
    if (d >= protocol['min_gain_pp'] and F['completion'] >= protocol['min_completion'] and F['correct_stops'] >= protocol['min_correct_stops_frac'] * F['impossible_tasks']
            and F['wrong_placements_per_task'] <= protocol['max_wrong_per_task']):
        return 'GAIN'
    if d <= 0 or F['completion'] < protocol['no_gain_completion']:
        return 'NO_GAIN'
    return 'INCONCLUSIVE'


def paired_pp(res, cond):
    return res['F_LM_vs_N']['mean_pp'] if cond == 'F_LM' else res['F_vs_N']['mean_pp']
