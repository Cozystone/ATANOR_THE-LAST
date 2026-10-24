"""Opt-in learned shared recurrent dynamics; no native-operation semantics.

Existing sensor codec supplies categorical values/scalars/anonymous edge arrays.
Shared node/message computation supports variable entity count. Three small
random-initialized models, actual-only updates, bounded replay and persistent
detached recurrent activity. No pretrained model, hand-written effect, task ID,
goal-fed learning loss, or claim that uncertainty selection itself was learned.
Native permissions/provenance belong to the owning runner, NOT this learner.
"""
import copy
import random
import torch
from torch import nn
from torch.nn import functional as F


class Dynamics(nn.Module):
    def __init__(self, operations, channels, width=24):
        super().__init__()
        self.width = width
        self.operations = nn.Embedding(operations, 8)
        self.encode = nn.Linear(4, width)  # supplied categorical codec3 + scalar1
        self.message = nn.Linear(width * (2 + 2 * channels), width)
        self.cell = nn.GRUCell(width * 2 + 9, width)
        self.output = nn.Linear(width, 3)

    def forward(self, frame, actions, hidden):
        kinds = torch.tensor(frame['kinds'], dtype=torch.long)
        scalars = torch.tensor(frame['scalars'], dtype=torch.float32)[:, None]
        x = torch.cat((F.one_hot(kinds, 3).float(), scalars), -1)
        encoded = torch.tanh(self.encode(x))
        n = len(kinds)
        messages = [encoded, encoded.mean(0, keepdim=True).expand(n, -1)]
        for channel in frame['edges']:
            edge = torch.tensor(channel, dtype=torch.float32)
            # Generic message sums, no degree/kind-count/SQL-specific predicates.
            messages.extend((edge @ encoded, edge.T @ encoded))
        local = torch.tanh(self.message(torch.cat(messages, -1)))
        op = torch.tensor([a[0] for a in actions], dtype=torch.long)
        targets = torch.tensor([a[1] for a in actions], dtype=torch.long)
        batch = len(actions)
        target_state = local[targets][:, None, :].expand(-1, n, -1)
        mask = F.one_hot(targets, n).float()[:, :, None]
        operation = self.operations(op)[:, None, :].expand(-1, n, -1)
        inputs = torch.cat((local[None].expand(batch, -1, -1), target_state, operation, mask), -1)
        h = self.cell(inputs.reshape(batch*n, -1),
                      hidden[None].expand(batch, -1, -1).reshape(batch*n, -1))
        h = h.reshape(batch, n, self.width)
        return self.output(h), h


class PlasticWorld:
    def __init__(self, seed, operations=4, channels=2, width=24, capacity=256):
        torch.set_num_threads(1)
        self.config = dict(seed=seed, operations=operations, channels=channels,
                           width=width, capacity=capacity)
        self.models = []
        for i in range(3):
            with torch.random.fork_rng():
                torch.manual_seed(seed + i*1009)
                self.models.append(Dynamics(operations, channels, width))
        self.optimizers = [torch.optim.Adam(m.parameters(), lr=0.003) for m in self.models]
        self.rng = random.Random(seed)
        self.replay = []
        self.hidden = None
        self.revision = 0
        self.model_queries = 0
        self.updates = 0

    def enter_body(self, n):
        """Reset only body-bound working activation; retain learned world/history.

        New body handles cannot inherit unrelated per-entity working state.
        This boundary is owned by runner, not inferred from task/goal identity.
        """
        self.hidden = [torch.zeros(n, self.config['width']) for _ in self.models]

    def _validate(self, frame, actions):
        if type(frame) is not dict or set(frame) != {'kinds', 'scalars', 'edges'}:
            raise ValueError('sensor values only')
        n = len(frame['kinds'])
        if n < 1 or self.hidden is None or self.hidden[0].shape[0] != n:
            raise ValueError('explicit body binding required')
        if len(frame['scalars']) != n or len(frame['edges']) != self.config['channels']:
            raise ValueError('sensor shape mismatch')
        if any(type(v) is not int or v not in (0,1,2) for v in frame['kinds']):
            raise ValueError('categorical sensor outside supplied codec')
        if any(len(e)!=n or any(len(row)!=n for row in e) for e in frame['edges']):
            raise ValueError('edge shape mismatch')
        if not actions or any(len(a)!=2 or any(type(v) is not int for v in a)
                              or not 0<=a[0]<self.config['operations'] or not 0<=a[1]<n for a in actions):
            raise ValueError('action outside bound schema')

    def forecasts(self, frame, actions):
        self._validate(frame, actions)
        with torch.no_grad():
            probs = torch.stack([m(frame, actions, h)[0].softmax(-1)
                                 for m,h in zip(self.models,self.hidden)])
        self.model_queries += len(actions)*len(self.models)
        return probs.mean(0), probs.var(0, unbiased=False).mean((1,2))

    def choose_experience(self, frame, actions, rng, active):
        if not active:
            return rng.choice(actions)
        _, uncertainty = self.forecasts(frame, actions)
        best = float(uncertainty.max())
        candidates = [i for i,v in enumerate(uncertainty) if abs(float(v)-best)<=1e-12]
        return actions[rng.choice(candidates)]

    def choose_task(self, frame, actions, goal, rng):
        # All groups use the same bounded behavior, including Fresh. Predictions
        # need not be certain to explore inside the externally safe native body.
        probabilities, _ = self.forecasts(frame, actions)
        if rng.random() < 0.2:
            return rng.choice(actions)
        target = torch.tensor(goal, dtype=torch.long)[None,:,None].expand(len(actions),-1,-1)
        scores = probabilities.gather(2,target).squeeze(-1).mean(1)
        best = float(scores.max())
        return actions[rng.choice([i for i,v in enumerate(scores) if abs(float(v)-best)<=1e-12])]

    def learn(self, before, action, after):
        self._validate(before,[action])
        self._validate(after,[action])
        record = dict(before=copy.deepcopy(before), action=list(action), after=copy.deepcopy(after),
                      hidden=[h.detach().clone() for h in self.hidden])
        with torch.no_grad():
            next_hidden = [m(before,[action],h)[1][0].detach().clone()
                           for m,h in zip(self.models,self.hidden)]
        # Preserve the newest event and one sampled replay event. Chronological
        # replay is retained externally; bounded active memory is not forgetting
        # the canonical autobiography. Fast/slow consolidation not claimed here.
        old = self.rng.choice(self.replay) if self.replay else None
        for i,(model,optimizer) in enumerate(zip(self.models,self.optimizers)):
            for item in [record] + ([old] if old is not None else []):
                logits,_ = model(item['before'],[item['action']],item['hidden'][i])
                truth = torch.tensor(item['after']['kinds'],dtype=torch.long)
                changed = truth != torch.tensor(item['before']['kinds'])
                errors = F.cross_entropy(logits[0],truth,reduction='none')
                strata = [errors[mask].mean() for mask in (changed,~changed) if mask.any()]
                loss = torch.stack(strata).mean()
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(),5.)
                optimizer.step()
                self.updates += 1
        self.hidden = next_hidden
        self.replay.append(record)
        self.replay = self.replay[-self.config['capacity']:]
        self.revision += 1

    def checkpoint(self):
        return copy.deepcopy(dict(config=self.config, models=[m.state_dict() for m in self.models],
              optimizers=[o.state_dict() for o in self.optimizers], rng=self.rng.getstate(),
              replay=self.replay, hidden=self.hidden, revision=self.revision,
              model_queries=self.model_queries, updates=self.updates))

    @classmethod
    def restore(cls,state):
        model = cls(**state['config'])
        for m,s in zip(model.models,state['models']):
            m.load_state_dict(s)
        for o,s in zip(model.optimizers,state['optimizers']):
            o.load_state_dict(s)
        for key in ('replay','hidden','revision','model_queries','updates'):
            setattr(model,key,copy.deepcopy(state[key]))
        model.rng.setstate(state['rng'])
        return model
