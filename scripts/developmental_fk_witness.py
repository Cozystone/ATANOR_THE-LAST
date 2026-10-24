"""Native nonlocal-dependency witness using existing historical FKWorld.

Researcher-created counterexample, NOT an autonomous experiment or transfer score.
No altered FK engine, deployment adapter, or candidate cognition is introduced.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def run(source, output):
    raw=source.read_bytes()
    spec=importlib.util.spec_from_file_location('atanor_existing_fk',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows=[]
    for blocked in (False,True):
        body=module.FKWorld(81001,n=4,prefill=0)
        try:
            for i in range(4): assert body.do('insert',i)
            if blocked: assert body.do('link',2)
            before=body.config()
            references=body.con.execute('SELECT k, ref FROM row_ ORDER BY k').fetchall()
            # Analog of a self-output rooted query: action and output both slot0.
            # Other rows ARE observed globally, but absent from this local query.
            local={'action':'delete','argument_state':before[0],
                   'output_state':before[0],'argument_equals_output':True,
                   'self_reference':False}
            success=body.do('delete',0)
            after=body.config()
            anchor_count=body.con.execute('SELECT COUNT(*) FROM anchor').fetchone()[0]
            rows.append({'blocked':blocked,'before':before,'references':references,
                         'local_query':local,'success':success,'after':after,
                         'native_anchor_count':anchor_count})
        finally:
            body.dispose()
    assert rows[0]['local_query']==rows[1]['local_query']
    assert rows[0]['success'] and not rows[1]['success']
    assert rows[0]['native_anchor_count']==0 and rows[1]['native_anchor_count']==1
    assert source.read_bytes()==raw
    result={'source_path':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),
            'verdict':'ROOT_ONLY_CONTEXT_INSUFFICIENT',
            'scope':'native architectural witness, NOT a candidate transfer evaluation',
            'rows':rows}
    with output.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps(result))

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
