"""One place of the island (world/isle_world.py): the glen. Its own tools and its own state; the urns, the steles, the
attributes, their values and the laws are the island's. Built body-side by a separate agent. Which law a tool follows
is written here only and is never exported; the tool names say nothing about it."""
from .isle_world import IsleWorkspace, tool

TABLE = {'hadrel': tool('E7', 'R3'), 'ockney': tool('E10', 'R5'), 'pavrin': tool('E5'),
         'tulsk': tool('E6', 'E4'), 'fennit': tool('E11', cap='fennit_urns')}
RETIRE = {'tulsk': 'gribble', 'pavrin': 'drammock'}             # drift '<tool>_retired': the tool stops, the other name does its work
TOOLS = {t: s['arity'] for t, s in TABLE.items()}
CAPABILITY = {t: s['cap'] for t, s in TABLE.items() if s['cap']}


class GlenWorkspace(IsleWorkspace):
    BODY = 'glen'
    TABLE = TABLE
    RETIRE = RETIRE
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
