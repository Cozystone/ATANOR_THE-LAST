"""Optimistic expressivity ceiling, not a transfer policy or capability score.

Strip source applicability ONLY for oracle coverage: every surviving source map
may propose for any target channel of the same action arity. No such stripping
is used in runtime. Compare even the entire existing remap grammar, fitting each
target observation independently with knowledge of its outcome. Failure under
this privileged oracle rules out mere retrieval/mapping fixes for this grammar.
Success is NOT a learnable/validated applicability mapping. Exposed SQL corpus.
"""
import itertools,json,sqlite3,sys,hashlib
from pathlib import Path
from contextlib import closing
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from packages.shared_world.contextual_rewrite import ContextualRewrite
from packages.shared_world.index_rewrite import fields,remap
from packages.action_core.world import Frame,Action


def run(output):
    source=ROOT/'evidence/developmental-exploring-life-v1/online.sqlite'
    target=ROOT/'evidence/developmental-fk-schema-tasks.json'
    with closing(sqlite3.connect('file:'+source.as_posix()+'?mode=ro&immutable=1',uri=True)) as db:
        records=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])['model']['records']
    model=ContextualRewrite(records);library={}
    for (key,names,name),rule in model.rules.items():
        pool=library.setdefault(len(key[1]),set());pool.update(rule.common)
        for _,_,_,yes,no in rule.alternatives:pool.update(yes);pool.update(no)
    rows=[];counts=Counter()
    for ordinal,r in enumerate(json.loads(target.read_text())['training']):
        before,after=(Frame.from_dict(r[k]) for k in ('before','after'))
        action=Action.from_dict(r['action']);args=tuple(before.handles.index(h) for h in action.args)
        grammar=list(itertools.product(range(-2,len(args)),repeat=len(args)))
        results=[]
        for name,values in fields(before).items():
            actual=fields(after)[name];changed=values!=actual
            source_ok=any(remap(values,args,m)==actual for m in library.get(len(args),()))
            grammar_ok=any(remap(values,args,m)==actual for m in grammar)
            results.append(dict(field=name,changed=changed,source_map_covers=source_ok,grammar_covers=grammar_ok))
            counts['fields']+=1;counts['changed_fields']+=changed
            counts['source_covered']+=source_ok;counts['grammar_covered']+=grammar_ok
            counts['changed_source_covered']+=changed and source_ok
            counts['changed_grammar_covered']+=changed and grammar_ok
        counts['transitions']+=1
        counts['complete_grammar_covered']+=all(f['grammar_covers'] for f in results)
        rows.append(dict(ordinal=ordinal,action=action.to_dict(),fields=results))
    report=dict(scope=__doc__,source_library={str(k):sorted(v) for k,v in library.items()},
        counts=counts,rows=rows,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        target_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    with output.open('x') as stream:json.dump(report,stream,sort_keys=True)
    print(json.dumps({k:v for k,v in report.items() if k in ('source_library','counts')}))


if __name__=='__main__':run(Path(sys.argv[1]))
