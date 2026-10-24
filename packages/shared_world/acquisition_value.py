"""Empirical sensor value by generic object/action role, not operation semantics.

Credit must be measured after an actual outcome. This table does not establish
provenance, causal utility, calibration, or autonomous learning agenda selection.
No operation names, path names, case IDs or preferred argument positions.
"""


def features(frame, action, handle):
    i = frame.handles.index(handle)
    return (frame.kinds[i], tuple(frame.kinds[frame.handles.index(h)] for h in action.args),
            tuple(int(handle == h) for h in action.args))


class AcquisitionValue:
    def __init__(self):
        self.samples = {}

    def learn(self, frame, action, handle, measured_gain):
        import math
        if type(measured_gain) not in (int,float) or not math.isfinite(measured_gain):
            raise ValueError('finite measured gain required')
        key = features(frame, action, handle)
        total, count = self.samples.get(key, (0.,0))
        self.samples[key] = total+measured_gain, count+1

    def value(self, frame, action, handle):
        total, count = self.samples.get(features(frame,action,handle), (0.,0))
        return total/count if count else 0.

    def choose(self, frame, action):
        return max(frame.handles, key=lambda h:self.value(frame,action,h))

    def explore(self, frame, action, rng):
        """Balance observed feature classes, not raw duplicate object count.

This assumes the feature abstraction is useful; it does not prove two objects
have equal hidden information. Exploration is generic, not a semantic target.
"""
        groups={}
        for h in frame.handles:
            groups.setdefault(features(frame,action,h),[]).append(h)
        minimum=min(self.samples.get(k,(0.,0))[1] for k in groups)
        key=rng.choice([k for k in groups if self.samples.get(k,(0.,0))[1]==minimum])
        return rng.choice(groups[key])
