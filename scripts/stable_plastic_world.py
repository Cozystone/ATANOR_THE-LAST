"""Research-only frozen teacher on actual autobiographical anchors.

No law IDs, evaluation labels, oracle routing, consolidation or autonomous
memory selection. One fixed regularizer; old predictions may themselves be wrong.
"""
import copy
import torch
from torch import nn
from torch.nn import functional as F
from scripts.developmental_plastic_world import PlasticWorld
from scripts.adaptation_pair_isolation import compose


class StablePlasticWorld(PlasticWorld):
    @classmethod
    def from_life(cls, state):
        model = cls.restore(compose(state)['weights_adam'])
        model.teachers = copy.deepcopy(model.models)
        for teacher in model.teachers:
            teacher.requires_grad_(False)
        history = state['replay']
        model.anchors = copy.deepcopy([history[i * (len(history)-1)//7]
                                      for i in range(8)]) if history else []
        return model

    def learn(self, before, action, after):
        self._validate(before, [action]); self._validate(after, [action])
        record = dict(before=copy.deepcopy(before), action=list(action),
                      after=copy.deepcopy(after), hidden=[h.clone() for h in self.hidden])
        with torch.no_grad():
            next_hidden = [m(before, [action], h)[1][0].detach().clone()
                           for m,h in zip(self.models,self.hidden)]
        old = self.rng.choice(self.replay) if self.replay else None
        for i,(model,optimizer,teacher) in enumerate(zip(self.models,self.optimizers,self.teachers)):
            for item in [record] + ([old] if old is not None else []):
                logits,_ = model(item['before'],[item['action']],item['hidden'][i])
                truth = torch.tensor(item['after']['kinds'],dtype=torch.long)
                changed = truth != torch.tensor(item['before']['kinds'])
                errors = F.cross_entropy(logits[0],truth,reduction='none')
                loss = torch.stack([errors[mask].mean() for mask in (changed,~changed) if mask.any()]).mean()
                penalties=[]
                for anchor in self.anchors:
                    # Only exact observed contradiction removes an anchor; no
                    # law-specific or held-out knowledge about what changed.
                    if (anchor['before']==before and anchor['action']==list(action)
                            and anchor['after']!=after):
                        continue
                    with torch.no_grad():
                        target=teacher(anchor['before'],[anchor['action']],anchor['hidden'][i])[0].softmax(-1)
                    current=model(anchor['before'],[anchor['action']],anchor['hidden'][i])[0]
                    penalties.append(F.kl_div(current.log_softmax(-1),target,reduction='none').sum(-1).mean())
                if penalties: loss=loss+torch.stack(penalties).mean()
                optimizer.zero_grad(set_to_none=True);loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step();self.updates+=1
        self.hidden=next_hidden
        self.replay=(self.replay+[record])[-self.config['capacity']:]
        self.revision+=1
