from scripts.developmental_context_ablation import without_channel
from scripts.developmental_conditional_eval import Model


def test_drop_exactly_one_channel_preserves_other_context():
    key=('op','kind',(0,),(1,),(1,1),(('a',(0,1)),('b',(1,0))))
    assert without_channel('a')(key)==key[:-1]+((('b',(1,0)),),)
    assert without_channel('missing')(key)==key


def test_default_key_transform_is_identity():
    model=Model([])
    key=('opaque',42)
    assert model.key_transform(key)==key
