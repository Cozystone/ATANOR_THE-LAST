"""One place of the island (world/isle_world.py): the moor. Its own tools and its own state; the urns, the steles, the
attributes, their values and the laws are the island's. Built body-side by a separate agent. Which law a tool follows
is written here only and is never exported; the tool names say nothing about it."""
from .isle_world import IsleWorkspace, tool

TABLE = {'mebrin': tool('E2', 'R3'), 'sollux': tool('E5', 'R4'), 'gavot': tool('E6'),
         'ruskin': tool('E1', 'E9', 'R6'), 'ombel': tool('E11', cap='ombel_urns')}
RETIRE = {'mebrin': 'tascal', 'gavot': 'pindle'}             # drift '<tool>_retired': the tool stops, the other name does its work
TOOLS = {t: s['arity'] for t, s in TABLE.items()}
CAPABILITY = {t: s['cap'] for t, s in TABLE.items() if s['cap']}


class MoorWorkspace(IsleWorkspace):
    BODY = 'moor'
    TABLE = TABLE
    RETIRE = RETIRE
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
