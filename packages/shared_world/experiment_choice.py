"""Opt-in bounded uncertainty sampling; no claim of value-of-information optimality.

Only observed Frames and permitted Action candidates enter. No result, goal label,
native path or caller confidence is accepted. Supervisor owns experiment cost and
permission. Zero budget returns no choice. This is NOT autonomous experiment design.
"""
import math
from packages.action_core.world import Frame, Action


def select(model, candidates, *, remaining, rng):
    if type(remaining) is not int or remaining < 0:
        raise ValueError('invalid acquisition budget')
    if type(candidates) not in (list, tuple) or len(candidates) > 512:
        raise ValueError('bounded public candidate list required')
    if remaining == 0 or not candidates:
        return None
    best, choices = -1., []
    for index, row in enumerate(candidates):
        if type(row) is not tuple or len(row) != 2 or type(row[0]) is not Frame or type(row[1]) is not Action:
            raise ValueError('only observed frame/action pairs; no caller scores or outcomes')
        _, uncertainty = model.predict(row[0], [row[1]])[0]
        if not math.isfinite(uncertainty) or not 0 <= uncertainty <= 1:
            raise ValueError('invalid model uncertainty')
        if uncertainty > best:
            best, choices = uncertainty, [index]
        elif uncertainty == best:
            choices.append(index)
    return rng.choice(choices)
