"""Hand-declared diagnostic environment laws, NOT cognition or solutions.

All consequences executed by real SQLite constraints/triggers. The learner sees
the unchanged anonymous sensor codec and opaque action indices, never law IDs.
"""
import random
from scripts.plastic_law_world import LawWorld, native
from scripts.developmental_plastic_eval import frame

NEW_LAWS=('unique_link','broadcast_unlink','steal_link','attached_insert','cleanup_delete','parent_insert')
CONTROLS=('null','cascade')
LAWS=NEW_LAWS+CONTROLS
SQL={
 'unique_link':'CREATE UNIQUE INDEX capacity_one ON row_(ref)',
 'broadcast_unlink':'''CREATE TRIGGER broadcast AFTER UPDATE OF ref ON row_
 WHEN OLD.ref IS NOT NULL AND NEW.ref IS NULL BEGIN
 UPDATE row_ SET ref=NULL WHERE ref=OLD.ref; END''',
 'steal_link':'''CREATE TRIGGER steal BEFORE UPDATE OF ref ON row_
 WHEN OLD.ref IS NULL AND NEW.ref IS NOT NULL BEGIN
 UPDATE row_ SET ref=NULL WHERE k<>NEW.k AND ref=NEW.ref; END''',
 'attached_insert':'''CREATE TRIGGER attach AFTER INSERT ON row_
 WHEN EXISTS(SELECT 1 FROM anchor WHERE k=0) BEGIN
 UPDATE row_ SET ref=0 WHERE k=NEW.k; END''',
 'cleanup_delete':'''CREATE TRIGGER cleanup AFTER DELETE ON row_ BEGIN
 UPDATE row_ SET ref=NULL; DELETE FROM anchor WHERE k=0; END''',
 'parent_insert':'''CREATE TRIGGER populate AFTER INSERT ON anchor BEGIN
 UPDATE row_ SET ref=NEW.k; END''',
}


def make(law,seed,n,modified):
    if law not in LAWS:raise ValueError('undeclared law')
    body=LawWorld(seed,n,0,law if modified and law in CONTROLS else 'restrict')
    ids=list(range(1,n));random.Random(seed).shuffle(ids)
    missing=ids[-1] if law=='attached_insert' else None
    if law!='parent_insert':body.con.execute('INSERT INTO anchor VALUES (0)')
    body.con.executemany('INSERT INTO row_ VALUES (?, NULL)',[(i,) for i in ids if i!=missing])
    number=0 if law=='parent_insert' else 1 if law=='unique_link' else min(2+(seed%2),n-1) if law=='broadcast_unlink' else min(1+seed%2,n-2)
    linked=ids[:number]
    for i in linked:body.con.execute('UPDATE row_ SET ref=0 WHERE k=?',(i,))
    body.con.commit()
    if modified and law in SQL:body.con.execute(SQL[law]);body.con.commit()
    primary={'unique_link':[1,ids[1]],'broadcast_unlink':[2,ids[0]],
             'steal_link':[1,ids[number] if number<len(ids) else ids[-1]],
             'attached_insert':[0,missing], 'cleanup_delete':[3,ids[0]],
             'parent_insert':[0,0],'null':[3,0],'cascade':[3,0]}[law]
    return body,primary


def successors(body,actions):
    results=[]
    for action in actions:
        clone=LawWorld(0,body.n,0,'restrict')
        try:
            body.con.backup(clone.con)
            accepted=bool(clone.do(native.FK_ACTIONS[action[0]],action[1]))
            assert not clone.con.execute('PRAGMA foreign_key_check').fetchall()
            results.append(dict(accepted=accepted,after=frame(clone)))
        finally:clone.dispose()
    return results


def case(law,seed,n):
    a,action=make(law,seed,n,False);b,other=make(law,seed,n,True)
    try:
        before=frame(a);assert before==frame(b) and action==other
        actions=[[o,i] for o in range(4) for i in range(n)]
        old=successors(a,actions);new=successors(b,actions);idx=actions.index(action)
        changed=[i for i,(x,y) in enumerate(zip(old[idx]['after']['kinds'],new[idx]['after']['kinds'])) if x!=y]
        assert changed,'fixture must show a real new-law contradiction'
        common=[i for i,(x,y) in enumerate(zip(old,new)) if x==y and x['after']['kinds']!=before['kinds']]
        assert common
        return dict(law=law,seed=seed,n=n,before=before,actions=actions,primary=idx,
                    old=old,new=new,changed=changed,common=common)
    finally:a.dispose();b.dispose()
