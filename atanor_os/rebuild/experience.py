"""REBUILD_PLAN.md A: the experience contract. One experience keeps, as separate fields, what was observed before, what
was asked of the body (tool, arguments, permissions granted), whether it actually ran and what it answered, what was
observed right after and later, known outside changes, the person's goal and answers with the scope each answer covers,
and the list of fields that were not observed. Tool success, goal success, the person's approval and safety are never
one value. A later change is never filed as this action's effect; a cause or failure reason that was not recorded is
never filled in.
"""
import json
from pathlib import Path

FIELDS = ('t', 'body', 'source', 'actor', 'action', 'executed', 'response', 'before', 'after', 'later', 'external',
          'goal', 'answers', 'unobserved')
SCOPES = ('selection', 'result', 'permission', 'unspecified')     # what a 'no' is about


def experience(**kw):
    e = {k: kw.get(k) for k in FIELDS}
    e['later'] = e['later'] or []
    e['external'] = e['external'] or []
    e['answers'] = e['answers'] or []
    e['unobserved'] = sorted(set(e['unobserved'] or []) | {k for k in ('before', 'after', 'response') if kw.get(k) is None})
    return e


def response_class(resp):
    """What the body answered, as observed: 'ok', 'failed' (the tool ran or refused on its own preconditions), or
    'blocked' (an outside guard or a missing permission stopped it before it ran). Nothing is inferred beyond that."""
    if resp is None:
        return None
    if resp.get('guard') or resp.get('blocked'):
        return 'blocked'
    return 'ok' if resp.get('ok') else 'failed'


class Store:
    """Append-only experiences on disk (one JSON line each); survives restarts. In a life (life/host.py) an experience is
    in the autobiography before it is here; a call's own experience is, as its intent, result and observation."""

    autobiography = None

    def __init__(self, path):
        self.path = Path(path)
        self.items = [json.loads(l) for l in self.path.read_text(encoding='utf-8').splitlines()] if self.path.exists() else []

    def add(self, e):
        if Store.autobiography is not None and 'intent' not in e and 'jseq' not in e:   # told or tried: on the record first
            e = {**e, 'jseq': Store.autobiography.append('TESTIMONY' if e.get('actor') == 'person' else 'SELF_TRIAL', experience=e)}
        e = {'id': f'x{len(self.items)}', **e}
        self.items.append(e)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + '\n')
        return e


def from_body_log(rows, body, source):
    """Experiences from a body's own log (the climate bays and the desk keep one; for the three older bodies a log of the
    arguments' observations before and after each call). Outside events become experiences with actor 'outside' and no
    action. What the log does not hold is listed in 'unobserved'."""
    out, t = [], 0
    pending_outside = []
    for r in rows:
        t += 1
        ev = r.get('event')
        if ev in ('tick', 'arrive'):
            ch = r.get('changes') or [[k, 'arrived', True] for k in (r.get('bays') or r.get('items') or {})]
            pending_outside.append({'t': t, 'event': ev, 'changes': ch})
            out.append(experience(t=t, body=body, source=source, actor='outside', action=None, executed=None, response=None,
                                  before=None, after=r.get('obs_after'), external=[{'event': ev, 'changes': ch}],
                                  unobserved=['before', 'response', 'action']))
            continue
        if ev != 'act':
            continue
        resp = {'ok': bool(r.get('ok')), 'error': r.get('error'), 'guard': r.get('guard')}
        blocked = response_class(resp) == 'blocked'
        unobs = ['granted', 'goal', 'answers', 'time']     # none of the body logs keep these
        if r.get('actor') is None:
            unobs.append('actor')
        before, after = r.get('obs_before'), r.get('obs_after')
        if blocked and before is None:
            unobs.append('before')                         # the guard logs only world hashes: same before and after
        out.append(experience(t=t, body=body, source=source, actor=r.get('actor', 'unknown'),
                              action={'tool': r['tool'], 'args': list(r.get('args') or []), 'granted': None},
                              executed=not blocked, response=resp, before=before, after=after if not blocked else before,
                              external=[], unobserved=unobs + (['elsewhere'] if 'elsewhere' not in r and body in ('board', 'fs', 'view') else [])))
        if r.get('elsewhere'):
            out[-1]['elsewhere'] = r['elsewhere']
        pending_outside = []
    return out


def body_log_path(course_dir, body):
    """Where a course run of repr.run_act6.course keeps the body log."""
    base = Path(course_dir)
    return base / 'obs_log.jsonl' if body in ('board', 'fs', 'view') else base / body / body / 'world_log.jsonl'


def load_course(course_dir, body, source='program'):
    p = body_log_path(course_dir, body)
    rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()]
    return from_body_log(rows, body, source)
