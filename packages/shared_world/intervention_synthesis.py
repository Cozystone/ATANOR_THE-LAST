"""Bounded reachability of a learned observable-disagreement predicate.

No native access, experiment menu, operation semantics or learning. Preparation
forecasts remain hypotheses; a returned sequence authorizes nothing. Execute one
step, reobserve and replan outside this module.
"""
import time
from packages.action_core.world import Frame, Action
from .effect_hypotheses import inspect_effects
from .epistemic_lookahead import _query_projection


def synthesize(model, observation, actions, *, remaining, max_length=3,
               width=32, max_queries=2048, cpu_deadline=None):
    if type(observation) is not Frame:
        raise ValueError("Actual current observation required")
    if type(actions) not in (list, tuple) or len(actions) > 512:
        raise ValueError("Bounded permitted actions required")
    if any(type(action) is not Action for action in actions):
        raise ValueError("Typed actions required")
    if type(remaining) is not int or remaining < 0:
        raise ValueError("Invalid action allowance")
    if any(type(x) is not int or x < 1 for x in (max_length, width, max_queries)):
        raise ValueError("Positive search bounds required")
    if max_length > 3 or width > 32 or max_queries > 2048:
        raise ValueError("Search exceeds registered bounds")
    queries, skipped, truncated = 0, 0, 0
    def result(status, sequence=(), report=None):
        return {"status": status, "sequence": sequence, "disagreement": report,
                "queries": queries, "unsupported_preparations": skipped,
                "width_pruned": truncated, "truth_claim": False}
    if not remaining or not actions:
        return result("NO_BUDGET_OR_ACTIONS")
    ordered = sorted(actions, key=lambda action: (action.op, action.args))
    frontier = [(observation, ())]
    visited = {repr(observation.to_dict())}
    for length in range(1, min(max_length, remaining) + 1):
        targets, successors = [], []
        for state, prefix in frontier:
            for action in ordered:
                if cpu_deadline is not None and time.process_time() >= cpu_deadline:
                    return result("CPU_BUDGET_EXHAUSTED")
                if queries >= max_queries:
                    return result("QUERY_BUDGET_EXHAUSTED")
                queries += 1
                report = inspect_effects(model, state, action)
                if report["status"] == "RESIDUAL_DISAGREEMENT":
                    targets.append((len(report["disagreement_cells"]), prefix + (action,), report))
                if length >= min(max_length, remaining):
                    continue
                # No learned effect is not a justified preparatory transition.
                if report["status"] != "FINITE_SET_AGREEMENT":
                    skipped += 1
                    continue
                joint, _ = model.predict(state, [action])[0]
                positive = [(weight, forecast) for weight, forecast in joint.outcomes if weight > 0]
                if len(positive) != 1 or positive[0][0] != 1:
                    skipped += 1
                    continue
                forecast = positive[0][1]
                if _query_projection(forecast) is None:
                    skipped += 1
                    continue
                key = repr(forecast.to_dict())
                if key in visited:
                    continue
                visited.add(key)
                successors.append((forecast, prefix + (action,)))
        if targets:
            # Stable sort preserves the fixed action enumeration on equal scores.
            targets.sort(key=lambda row: -row[0])
            _, sequence, report = targets[0]
            return result("PROPOSED", sequence, report)
        truncated += max(0, len(successors) - width)
        frontier = successors[:width]
        if not frontier:
            break
    return result("NO_WITNESS_WITHIN_BOUNDS")
