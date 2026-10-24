import torch
from scripts.predictive_interference_audit import projection


def test_harmful_projection_and_nonharmful_control():
    delta=torch.tensor([3.,4.]);g=torch.tensor([2.,0.])
    p=projection(delta,g)
    assert torch.equal(p,torch.tensor([3.,0.]))
    assert float((delta-p)@g)==0
    assert torch.equal(projection(delta,-g),torch.zeros(2))
    assert torch.equal(projection(delta,torch.zeros(2)),torch.zeros(2))
