import copy
import pytest
from scripts.adaptation_fresh_validation import choose, verdicts


def test_selection_fixed_priority_and_rejects_nonqualifying():
    entry=dict(acquisition=4,per_life=[4]*4)
    r=dict(outcomes={law:{a:copy.deepcopy(entry) for a in ('weights_adam','weights_replay')} for law in ('null','cascade')})
    assert choose(r)=='weights_adam'
    r['outcomes']['null']['weights_adam']['acquisition']=8
    assert choose(r)=='weights_replay'
    r['outcomes']['null']['weights_replay']['per_life'][0]=8
    with pytest.raises(ValueError):choose(r)


def test_all_validation_conditions_required():
    arm='weights_adam'
    o={law:{a:dict(acquisition=4,per_life=[4]*8) for a in ('fresh','full',arm)} for law in ('null','cascade')}
    o['null']['fresh']=dict(acquisition=8,per_life=[8]*8)
    summaries=[dict(law=law,arm=a,count=8,whole_correct=32) for law in o for a in o[law]]
    assert all(verdicts(o,summaries,arm).values())
    o['null'][arm]['per_life'][0]=None
    assert not verdicts(o,summaries,arm)['no_life_slower']
    o['null'][arm]['acquisition']=8
    assert not verdicts(o,summaries,arm)['null_fast']
