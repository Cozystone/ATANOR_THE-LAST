"""One place of the island (world/isle_world.py): the crag. Its own tools and its own state; the urns, the steles, the
attributes, their values and the laws are the island's. Built body-side by a separate agent. Which law a tool follows
is written here only and is never exported; the tool names say nothing about it."""
from .isle_world import IsleWorkspace, tool

TABLE = {'jorvel': tool('E7', 'R6'), 'kessin': tool('E3', 'R3'), 'ulmar': tool('E6'),
         'drosk': tool('E5', 'E10'), 'nobbet': tool('E11', cap='nobbet_urns')}
RETIRE = {'ulmar': 'wexley', 'kessin': 'quoddy'}             # drift '<tool>_retired': the tool stops, the other name does its work
TOOLS = {t: s['arity'] for t, s in TABLE.items()}
CAPABILITY = {t: s['cap'] for t, s in TABLE.items() if s['cap']}


class CragWorkspace(IsleWorkspace):
    BODY = 'crag'
    TABLE = TABLE
    RETIRE = RETIRE
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
