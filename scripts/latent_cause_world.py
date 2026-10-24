"""Bounded research hypothesis bank inferred only from actual consequences.

No task/regime identifiers. Archived hypotheses are immutable; one provisional
hypothesis may learn. Recruitment and posterior rules are fixed before trial.
This is not a claim of Bayesian calibration or autonomous concept invention.
"""
import copy
import math
import torch
from scripts.developmental_plastic_world import PlasticWorld
from scripts.adaptation_pair_isolation import compose


class LatentCauseWorld:
    def __init__(self,state):
        self.archive=[PlasticWorld.restore(compose(state)['weights_adam'])]
        self.candidate=None;self.belief=[1.];self.recent=[];self.mismatches=0
        self.candidate_updates=0;self.recruits=0;self.saturated=False;self.n=None

    def models(self):return self.archive+([self.candidate] if self.candidate is not None else [])

    def enter_body(self,n):
        self.n=n
        for m in self.models():m.enter_body(n)

    def forecasts(self,frame,actions):
        ps=torch.stack([m.forecasts(frame,actions)[0] for m in self.models()])
        w=torch.tensor(self.belief,dtype=ps.dtype)
        return (ps*w[:,None,None,None]).sum(0),ps.var(0,unbiased=False).mean((1,2))

    @staticmethod
    def score(model,event):
        before,action,after=event
        model.enter_body(len(before['kinds']))
        p=model.forecasts(before,[action])[0][0]
        truth=torch.tensor(after['kinds'])
        logp=float(p.gather(1,truth[:,None]).clamp_min(1e-9).log().mean())
        return logp,p.argmax(-1).tolist()==after['kinds']

    def learn(self,before,action,after):
        event=copy.deepcopy((before,list(action),after))
        scores=[self.score(m,event) for m in self.models()]
        # Small fixed switching hazard prevents permanently impossible posteriors.
        k=len(scores);prior=[.95*p+.05/k for p in self.belief]
        logw=[math.log(p)+len(after['kinds'])*s[0] for p,s in zip(prior,scores)]
        top=max(logw);w=[math.exp(v-top) for v in logw];self.belief=[v/sum(w) for v in w]
        self.recent=(self.recent+[event])[-4:]
        archive_match=any(s[1] for s in scores[:len(self.archive)])
        self.mismatches=0 if archive_match else self.mismatches+1
        created=False
        if self.candidate is None and self.mismatches>=3:
            if len(self.archive)>=8:self.saturated=True
            else:
                best=max(range(len(self.archive)),key=lambda i:self.belief[i])
                cp=self.archive[best].checkpoint();cp['replay']=[]
                self.candidate=PlasticWorld.restore(cp);self.candidate_updates=0
                self.belief=[v*.9 for v in self.belief]+[.1]
                self.recruits+=1;created=True
        if self.candidate is not None:
            for e in (self.recent if created else [event]):
                self.candidate.enter_body(len(e[0]['kinds']));self.candidate.learn(*e)
                self.candidate_updates+=1
            if self.candidate_updates>=4 and len(self.recent)==4:
                fit=[self.score(self.candidate,e) for e in self.recent]
                old=max(sum(self.score(m,e)[0] for e in self.recent)/4 for m in self.archive)
                if sum(s[1] for s in fit)>=3 and sum(s[0] for s in fit)/4>old+.1:
                    self.archive.append(self.candidate);self.candidate=None;self.mismatches=0
        if self.n is not None:self.enter_body(self.n)

    def checkpoint(self):
        return dict(archive=[m.checkpoint() for m in self.archive],
                    candidate=None if self.candidate is None else self.candidate.checkpoint(),
                    belief=list(self.belief),recent=copy.deepcopy(self.recent),
                    mismatches=self.mismatches,candidate_updates=self.candidate_updates,
                    recruits=self.recruits,saturated=self.saturated,n=self.n)

    @classmethod
    def restore(cls,state):
        obj=cls.__new__(cls)
        obj.archive=[PlasticWorld.restore(s) for s in state['archive']]
        obj.candidate=None if state['candidate'] is None else PlasticWorld.restore(state['candidate'])
        for key in ('belief','recent','mismatches','candidate_updates','recruits','saturated','n'):
            setattr(obj,key,copy.deepcopy(state[key]))
        return obj
