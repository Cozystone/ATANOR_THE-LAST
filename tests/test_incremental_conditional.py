from packages.action_core.world import Frame,Action
from scripts.developmental_conditional_eval import Model


def row(op,before,after):
    def frame(size):return Frame([1],[size],[[1]],[[0]],('n0',)).to_dict()
    return dict(before=frame(before),after=frame(after),action=Action(op,('n0',)).to_dict())


def test_incremental_hypotheses_equal_full_rebuild_after_every_event():
    records=[row('a',1.,0.),row('b',1.,1.),row('a',0.,1.),row('a',.5,0.)]
    model=Model([])
    for i,r in enumerate(records):
        untouched=model.rules.copy();model.learn([r]);batch=Model(records[:i+1])
        assert model.rules==batch.rules
        for key in untouched:
            if key[0]!=r['action']['op']:assert model.rules[key] is untouched[key]
        for x in records:
            f=Frame.from_dict(x['before']);a=Action.from_dict(x['action'])
            assert model.predict(f,a,True)==batch.predict(f,a,True)
