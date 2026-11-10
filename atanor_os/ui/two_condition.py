"""Teach 'defect cards that are in a tray -> lift to high' on a fresh board (seed 1), then next session command a never-taught
combination with that selection. My meaning: mark == defect and tray != '-'. Direct Session, no HTTP."""
import sys, time, json, shutil, datetime
from pathlib import Path
from atanor_os.ui.teach_server import Session
root = Path(sys.argv[1]); shutil.rmtree(root, ignore_errors=True)
seed = int(sys.argv[2])
sess = Session(root, seed=seed, source='claude')
cards = lambda: sess.home._read()['cards']
from collections import defaultdict
by = defaultdict(lambda: [set(), 0])
for k, v in cards().items():
    if v['tray'] != '-': by[v['mark']][0].add(v['tray'])
    else: by[v['mark']][1] += 1
MARK = next((m for m in sorted(by) if len(by[m][0]) >= 2 and by[m][1] >= 1), None)   # in two different trays, and one without a tray
if MARK is None:
    print('RESULT skip'); sys.exit(0)
meant = lambda c: c['mark'] == MARK and c['tray'] != '-'
log = []
def drive(script):
    t0 = time.time()
    while sess.job.is_alive():
        p = sess.person.pending
        if p is None:
            time.sleep(0.01)
            assert time.time() - t0 < 60
            continue
        k = p['kind']
        if k == 'contrast':
            a = {'yes': meant(cards()[p['object']])}; log.append(('contrast', p['object'], cards()[p['object']]['mark'], cards()[p['object']]['tray'], a['yes']))
        elif k in ('confirm', 'judge'):
            c = cards(); acted = set(p.get('acted') or [])
            a = {'ok': script['ok'](c, acted)}; a['reason'] = None if a['ok'] else 'cards'; log.append((k, sorted(acted), a['ok']))
        else:
            a = script[k]
        sess.person.answers.put(a)
        while sess.person.pending is p:
            time.sleep(0.01)
    sess.job.join()
c0 = cards()
tray = sorted((k for k, v in c0.items() if meant(v)), key=lambda k: c0[k]['tray'])
tray = [tray[0], tray[-1]] + tray[1:-1]          # the two pointed cards are in different trays
sess.start('teach')
before = {k for k, v in c0.items() if meant(v)}
drive({'point': {'objects': tray[:2]}, 'demo': {'tool': 'lift', 'args': [tray[0], 'l.high'], 'object': tray[0]},
       'ok': lambda c, acted: all(c[k]['level'] == 'high' for k in before) and all(c[k]['level'] == 'low' for k in c if k not in before),
       'name': {'selection': 'vik', 'action': 'hup'}})
sess.start('teach')                                   # a second action on other cards, to combine later: idea -> stamp urgent
OTHER = next(m for m in sorted(by) if m != MARK)
idea = sorted(k for k, v in cards().items() if v['mark'] == OTHER)
meant2 = lambda c: c['mark'] == OTHER
m_old = meant; meant = meant2
drive({'point': {'objects': idea[:2] if len(idea) > 1 else idea}, 'demo': {'tool': 'lodge', 'args': [idea[0], 't3'], 'object': idea[0]},
       'ok': lambda c, acted: True, 'name': {'selection': 'pel', 'action': 'zim'}})
meant = m_old
sess.new_session()
c1 = cards(); want = {k for k, v in c1.items() if meant(v)}
sess.start('command', text='zim vik', alone=False)     # never taught together: defect cards in a tray -> tray t3
drive({'ok': lambda c, acted: acted <= want and all(c[k]['tray'] == 't3' for k in want)})
lesson = [x for x in log if x[0] == 'confirm'][0][2]
judged = [x for x in log if x[0] == 'judge']
print('RESULT', 'lesson', lesson, 'command', judged[-1][2] if judged else 'not run')
print('wanted', sorted(want), 'trayless defect', sorted(k for k, v in c1.items() if v['mark'] == 'defect' and v['tray'] == '-'))
