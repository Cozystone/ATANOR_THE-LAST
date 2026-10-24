from scripts.developmental_observation_dependencies import Dependencies
from packages.action_core.world import Frame


def frame(kinds, sizes, relation):
    n=len(kinds)
    return Frame(kinds,sizes,relation,[[0]*n for _ in kinds],tuple('n'+str(i) for i in range(n)),
                 {'r_opaque_channel':relation})


def test_targets_not_selected_by_name_and_disagreement_preserved():
    model=Dependencies()
    model.learn(frame([1,2],[.3,.4],[[1,0],[0,1]]))
    assert model.rules['equal']==model.rules['r_opaque_channel']
    assert model.predict(frame([1,1],[.3,.4],[[1,1],[1,1]]))['r_opaque_channel'][0][1]==[0,1]


def test_counterexample_removes_false_dependency():
    model=Dependencies()
    model.learn(frame([1,1],[.3,.4],[[1,1],[1,1]]))
    assert ('eq','kind') in model.rules['equal']
    model.learn(frame([1,1],[.3,.4],[[1,0],[0,1]]))
    assert ('eq','kind') not in model.rules['equal']
    assert model.rules['equal']==()


def test_prediction_does_not_learn():
    model=Dependencies()
    assert model.predict(frame([1],[.2],[[1]]))=={}
    assert model.rules=={}


def test_forecast_uses_only_predicted_values_and_keeps_unknown():
    model=Dependencies()
    model.learn(frame([1,1],[.3,.4],[[1,1],[1,1]]))
    model.learn(frame([1,2],[.3,.4],[[1,0],[0,1]]))
    p=[('kind',(0,),[1]),('kind',(1,),[1,2]),('equal',(0,1),[0])]
    assert model.forecast(p)[-1][2]==[0,1]
    p[1]=('kind',(1,),[])
    assert model.forecast(p)[-1][2]==[]
