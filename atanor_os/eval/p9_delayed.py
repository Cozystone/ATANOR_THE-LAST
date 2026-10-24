"""P9 delayed test: one attempt only, with frozen code, lexicon and representation checked before the sealed set opens.

    python -m atanor_os.eval.p9_delayed freeze   # once, before the run: records code / lexicon / R1 hashes (committed)
    python -m atanor_os.eval.p9_delayed run      # the single delayed evaluation
    python -m atanor_os.eval.p9_delayed status

No training happens here; the teacher, every model and the network stay off (guards inside p9.evaluate).
Any failure after the checks start is final and recorded: the run never repeats. Only a run started too early is
refused without consuming the attempt (the sealed file is not opened in that case).
"""
import datetime as dt
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
OUT = PKG / 'results' / 'p9'
FREEZE = OUT / 'delayed_freeze.json'
STATUS = OUT / 'delayed_status.json'
REFUSALS = OUT / 'delayed_refusals.json'
KST = dt.timezone(dt.timedelta(hours=9))
EARLIEST = dt.datetime(2026, 10, 27, 22, 33, tzinfo=KST)
IMMEDIATE_INTERPRETATION = 0.600            # P9 immediate result, unchanged
CODE_DIRS = ('agent', 'core', 'world', 'eval')


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def code_hashes():
    files = sorted(p for d in CODE_DIRS for p in (PKG / d).rglob('*.py') if '__pycache__' not in p.parts)
    per = {p.relative_to(PKG).as_posix(): _sha(p) for p in files}
    return per, hashlib.sha256(json.dumps(per, sort_keys=True).encode()).hexdigest()


def freeze():
    if FREEZE.exists():
        sys.exit('delayed freeze already exists; it is never rewritten')
    per, total = code_hashes()
    fz = json.loads((OUT / 'freeze.json').read_text(encoding='utf-8'))
    d = {'created': dt.datetime.now(KST).isoformat(timespec='seconds'), 'earliest_run_kst': EARLIEST.isoformat(),
         'min_hours_since_lexicon_freeze': 72, 'code_sha': total, 'code_files': per,
         'lexicon_sha': fz['lexicon_sha'], 'r1_sha': fz['r1_sha'], 'lexicon_frozen_at': fz['frozen_at']}
    FREEZE.write_text(json.dumps(d, indent=1), encoding='utf-8')
    print('frozen', total)


def _write_status(**kw):
    STATUS.write_text(json.dumps({**kw, 'at': dt.datetime.now(KST).isoformat(timespec='seconds')}, indent=1), encoding='utf-8')


def _refuse(reason):
    old = json.loads(REFUSALS.read_text(encoding='utf-8')) if REFUSALS.exists() else []
    REFUSALS.write_text(json.dumps(old + [{'at': dt.datetime.now(KST).isoformat(timespec='seconds'), 'reason': reason}], indent=1), encoding='utf-8')
    sys.exit(f'refused (attempt not consumed): {reason}')


def run():
    if STATUS.exists():
        sys.exit('the delayed test was already attempted; it is never repeated: ' + STATUS.read_text(encoding='utf-8'))
    fd = json.loads(FREEZE.read_text(encoding='utf-8'))
    now = dt.datetime.now(KST)
    hours = (time.time() - fd['lexicon_frozen_at']) / 3600
    if now < EARLIEST or hours < fd['min_hours_since_lexicon_freeze']:
        _refuse(f'too early: now {now.isoformat(timespec="seconds")}, {hours:.2f} h since the lexicon freeze')
    _write_status(state='started', hours_since_lexicon_freeze=round(hours, 2))      # the single attempt begins here
    checks = {}
    try:
        per, total = code_hashes()
        checks['code'] = total == fd['code_sha']
        checks['code_changed_files'] = sorted(f for f in set(per) | set(fd['code_files']) if per.get(f) != fd['code_files'].get(f))
        checks['lexicon'] = {c: _sha(OUT / f'lexicon_{c}.json') == s for c, s in fd['lexicon_sha'].items()}
        checks['r1'] = _sha(PKG / 'results' / 'p8b' / 'reps' / 'R1_KEEP' / 'stable_fs.json') == fd['r1_sha']
        if not (checks['code'] and all(checks['lexicon'].values()) and checks['r1']):
            _write_status(state='failed', stage='hash_check', checks=checks, hours_since_lexicon_freeze=round(hours, 2))
            sys.exit('hash mismatch; nothing evaluated; recorded')
        from .p9 import evaluate
        res = evaluate('delayed', OUT)                        # opens the sealed delayed set (sha checked inside)
    except SystemExit:
        raise
    except Exception:
        _write_status(state='failed', stage='evaluation', checks=checks, error=traceback.format_exc()[-3000:])
        sys.exit('evaluation failed; recorded; not repeated')
    s = res['summary']
    invalid = bool(res['teacher_import_attempts'] or res['network_event_count'])
    reused = (not invalid) and s['CONCEPT']['interpretation'] >= 0.8 * IMMEDIATE_INTERPRETATION and all(checks['lexicon'].values())
    v = {'verdict_delayed': 'INVALID' if invalid else ('REUSED' if reused else 'NOT_REUSED'),
         'threshold': round(0.8 * IMMEDIATE_INTERPRETATION, 3), 'immediate_interpretation_unchanged': IMMEDIATE_INTERPRETATION,
         'hours_since_lexicon_freeze': res['hours_since_freeze'], 'checks': checks,
         'teacher_import_attempts': res['teacher_import_attempts'], 'network_event_count': res['network_event_count'],
         'exact_overlap_with_training': res['exact_overlap_with_training'],
         **{c: {k: s[c][k] for k in ('interpretation', 'tool', 'set', 'dest', 'action_success', 'interpretation_seen_ext', 'interpretation_unseen_ext')}
            for c in ('CONCEPT', 'FLAT', 'NONE', 'ORACLE')},
         'concept_minus_flat': round(s['CONCEPT']['interpretation'] - s['FLAT']['interpretation'], 3)}
    (OUT / 'verdict_delayed.json').write_text(json.dumps(v, indent=1), encoding='utf-8')
    sealed = Path('D:/ATANOR-experiments/2026-09-19/sealed/p9_delayed.json')
    (OUT / 'sealed_p9_delayed.json').write_bytes(sealed.read_bytes())       # published after the run
    _write_status(state='completed', verdict=v['verdict_delayed'])
    print(json.dumps(v, indent=1))


def status():
    for p in (FREEZE, STATUS, REFUSALS, OUT / 'verdict_delayed.json'):
        print(p.name, '->', p.read_text(encoding='utf-8') if p.exists() else 'absent')


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'status': status}[sys.argv[1] if len(sys.argv) > 1 else 'status']()
