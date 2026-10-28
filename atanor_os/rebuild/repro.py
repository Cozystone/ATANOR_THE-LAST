"""REBUILD_PLAN.md stage 1: confusions found in existing course logs, each with a minimal case, and what the logs lack.
  state_dependent   the same action (tool + constant arguments) changed different things from different starts
  outside_change    an object the learner acted on changed later without any action on it (a tick, a delayed result)
  tool_ok_goal_no   every call succeeded but the person said the command was wrong
  vague_no          a 'no' whose scope (which objects, which result, permission) was not said
  missing           fields the learner's own records (mind/events.jsonl) do not keep, counted against the body log
Usage: python -m atanor_os.rebuild.repro <out.json> <body>=<course_dir> ...
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .effects import Effects
from .experience import load_course


def change(before, after):
    return tuple(sorted((k, (after or {}).get(k)) for k in set(before or {}) | set(after or {}) if (before or {}).get(k) != (after or {}).get(k)))


def scan(body, course_dir):
    course_dir = Path(course_dir)
    exps = load_course(course_dir, body)
    out = {'body': body, 'course': str(course_dir)}
    # state-dependent effects: one action key, several different changes on its first argument
    eff = Effects()
    by_key = defaultdict(lambda: defaultdict(list))
    for e in exps:
        if e.get('action') and e.get('before') is not None and e['executed']:
            eff.observe(e)
            a = e['action']['args']
            key = eff.models and next(k for k, m in eff.models.items() if m.cases and m.cases[-1].t == e['t'])
            ch = change(e['before'].get(a[0]), (e.get('after') or {}).get(a[0]))
            by_key[str(key)][ch].append({'t': e['t'], 'before': e['before'].get(a[0]), 'ok': e['response']['ok']})
    sd = {k: v for k, v in by_key.items() if len([c for c in v if c]) >= 2}
    k0 = next(iter(sorted(sd, key=lambda k: -len(sd[k]))), None)
    out['state_dependent'] = {'actions': len(by_key), 'with_several_changes': len(sd),
                              'example': {'action': k0, 'cases': {str(c): v[:1] for c, v in list(sd[k0].items())[:4]}} if k0 else None}
    # outside changes on objects the learner touched
    last_act, later = {}, Counter()
    example = None
    for e in exps:
        if e['actor'] == 'outside':
            for ch in e['external'][0]['changes']:
                o = ch[0]
                if o in last_act and len(ch) >= 2 and ch[1] != 'arrived':
                    later[e['external'][0]['event']] += 1
                    if example is None:
                        example = {'acted': last_act[o], 'outside': {'event': e['external'][0]['event'], 'change': ch}}
        elif e.get('action'):
            for o in e['action']['args'][:1]:
                last_act[o] = {'t': e['t'], 'tool': e['action']['tool'], 'after': (e.get('after') or {}).get(o)}
    out['outside_change'] = {'outside_events': sum(e['actor'] == 'outside' for e in exps), 'on_acted_objects': dict(later), 'example': example}
    # the course's own record: commands judged wrong although nothing failed; 'no' answers without scope
    log = [json.loads(l) for l in (course_dir / body / 'log.jsonl').read_text(encoding='utf-8').splitlines()]
    cmds = [r for r in log if r.get('event') == 'command']
    okwrong = [r for r in cmds if r.get('outcome') == 'wrong' and r.get('acted') and not r.get('failed')]
    out['tool_ok_goal_no'] = {'commands': len(cmds), 'wrong_with_calls_all_ok': len(okwrong),
                              'example': {k: okwrong[0].get(k) for k in ('words', 'acted', 'reason', 'alone')} if okwrong else None}
    ev = [json.loads(l) for l in (course_dir / 'mind' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    conf = [e for e in ev if e['kind'] == 'confirm']
    out['vague_no'] = {'confirms': len(conf), 'no': sum(not e['answer'] for e in conf),
                       'no_without_scope': sum(not e['answer'] and e.get('reason') is None for e in conf),
                       'yes_with_scope_in_reason_field': sum(bool(e['answer']) and e.get('reason') is not None for e in conf),
                       'note': "the 'reason' field holds both the scope of a yes (a 'show' answer is about the cards) and the reason of a no"}
    acts_body = sum(1 for e in exps if e.get('action') and e['actor'] in ('learner', 'unknown'))
    lev = Counter(e['kind'] for e in ev)
    post_kept = sum(len(e.get('post') or {}) for e in ev if e['kind'] == 'act_after')
    out['missing'] = {
        'learner_events_with_time': sum('at' in e or 't' in e for e in ev), 'learner_events': len(ev),
        'learner_acts': lev['act'], 'learner_acts_with_post': post_kept, 'body_log_acts_by_learner_or_unknown': acts_body,
        'learner_events_with_granted_permissions': sum('granted' in e or 'caps' in e for e in ev),
        'learner_events_of_outside_changes': sum(e['kind'] in ('tick', 'arrive', 'outside') for e in ev),
        'blocked_acts_in_learner_record': sum(e['kind'] == 'act' and 'permission' in str(e.get('error') or '') for e in ev),
        'unobserved_fields_in_body_log': dict(Counter(f for e in exps for f in e['unobserved']))}
    return out


if __name__ == '__main__':
    res = [scan(*a.split('=', 1)) for a in sys.argv[2:]]
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False), encoding='utf-8')
    for r in res:
        print(r['body'], r['course'][-8:], 'state_dep', r['state_dependent']['with_several_changes'], '/', r['state_dependent']['actions'],
              '| outside on acted', r['outside_change']['on_acted_objects'], '| ok-but-wrong', r['tool_ok_goal_no']['wrong_with_calls_all_ok'],
              '/', r['tool_ok_goal_no']['commands'], '| no', r['vague_no']['no'], 'unscoped', r['vague_no']['no_without_scope'],
              '| acts', r['missing']['learner_acts'], 'with post', r['missing']['learner_acts_with_post'],
              'time', r['missing']['learner_events_with_time'], 'outside', r['missing']['learner_events_of_outside_changes'])
