"""REBUILD_PLAN.md: the new learning structure, kept apart from the baseline core (atanor_os/agent/grounding.py) until a
part of it is shown better and swapped in.
  experience  what happened, as separate observed fields (never merged into one success value)
  effects     conditional prediction of what an action changes, from a start state, with its own uncertainty
  goals       whether a predicted change is what the person meant (separate from what the action does)
  inquiry     open questions, the checks that could settle them, and a simple policy that picks one
"""
