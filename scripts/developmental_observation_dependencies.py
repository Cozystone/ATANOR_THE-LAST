"""Learn conditional observation reconstructions, NOT action-effect predictions.

Target binary channels are all searched equally. Generic primitives are constant
0/1, identity and equality of either unary sensor attribute. Actual unary values
at the evaluated time are inputs: this is not a forecast of that future time.
Source scope belongs to the owner; learned rules are hypotheses, never authority.
"""
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from packages.action_core.world import Frame
from packages.shared_world.relational import _matrices

CANDIDATES = (('constant',0), ('constant',1), ('identity',), ('eq','kind'), ('eq','size'))


def evaluate(expression, frame, i, j):
    if expression[0]=='constant': return expression[1]
    if expression[0]=='identity': return int(i==j)
    values = frame.kinds if expression[1]=='kind' else frame.sizes
    return int(values[i]==values[j])


class Dependencies:
    def __init__(self): self.rules = {}

    def learn(self, frame):
        for name,matrix in _matrices(frame).items():
            self.rules[name] = tuple(e for e in self.rules.get(name,CANDIDATES)
                if all(evaluate(e,frame,i,j)==v for i,row in enumerate(matrix) for j,v in enumerate(row)))

    def predict(self, frame):
        return {name:[[(sorted({evaluate(e,frame,i,j) for e in expressions}))
                       for j in range(len(frame.handles))] for i in range(len(frame.handles))]
                for name,expressions in self.rules.items() if name in _matrices(frame)}

    def forecast(self, prediction):
        """Compose only predicted unary sets; no actual future Frame argument.

Any unsupported alternative keeps output unknown. Empty learned support means
no dependency known: retain baseline rather than silently deleting its forecast.
Scope binding must be provided by the owning experiment/runtime.
"""
        table={(field,tuple(address)):values for field,address,values in prediction}
        output=[]
        for field,address,baseline in prediction:
            expressions=self.rules.get(field,())
            if not expressions:
                output.append((field,address,baseline)); continue
            i,j=address; values=set(); unsupported=False
            for e in expressions:
                if e[0]=='constant': values.add(e[1])
                elif e[0]=='identity': values.add(int(i==j))
                else:
                    left=table.get((e[1],(i,)),[]); right=table.get((e[1],(j,)),[])
                    if not left or not right: unsupported=True; break
                    values.update(int(a==b) for a in left for b in right)
            output.append((field,address,[] if unsupported else sorted(values)))
        return output


def score(model, frames):
    counts = Counter()
    for frame in frames:
        for name,matrix in model.predict(frame).items():
            actual = _matrices(frame)[name]
            for i,row in enumerate(matrix):
                for j,values in enumerate(row):
                    category=('unknown' if not values else 'wrong' if actual[i][j] not in values
                              else 'correct_singleton' if len(values)==1 else 'correct_set')
                    counts[name+':'+category]+=1
    return dict(counts)


def run(output):
    sql = ROOT/'evidence/developmental-fk-schema-tasks.json'
    native = ROOT/'evidence/developmental-exploring-life-v1/online.sqlite'
    raws = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (sql,native)}
    with closing(sqlite3.connect('file:'+native.as_posix()+'?mode=ro&immutable=1',uri=True)) as db:
        files=json.loads(db.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])['model']['records']
    corpora={'sql':json.loads(sql.read_text())['training'], 'filesystem':files}
    models, report = {}, {}
    for name,records in corpora.items():
        frames=[Frame.from_dict(r[k]) for r in records for k in ('before','after')]
        model=Dependencies()
        # Fixed first48 transitions; no shuffled/future examples, then freeze.
        for frame in frames[:96]: model.learn(frame)
        models[name]=model
        report[name]=dict(training_transitions=48,test_transitions=len(records)-48,
                          rules=model.rules,conditional_reconstruction=score(model,frames[96:]))
    # Deliberately invalid cross-codec reuse as negative control; no promotion.
    file_frames=[Frame.from_dict(r['after']) for r in files]
    report['blind_sql_to_filesystem']=score(models['sql'],file_frames)
    assert raws=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (sql,native)}
    result=dict(scope=__doc__,source_sha256=raws,results=report,
                limitation='Exposed records; actual contemporaneous unary inputs; NOT next-state/action utility')
    with output.open('x') as stream: json.dump(result,stream,sort_keys=True)
    print(json.dumps(report))


if __name__=='__main__': run(Path(sys.argv[1]))
