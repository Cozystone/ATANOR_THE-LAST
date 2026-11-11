"""One place of the island (world/isle_world.py): the tarn. Its own tools and its own state; the urns, the steles, the
attributes, their values and the laws are the island's. Built body-side by a separate agent. Which law a tool follows
is written here only and is never exported; the tool names say nothing about it."""
from .isle_world import IsleWorkspace, tool

TABLE = {'farrel': tool('E3', 'R6'), 'yonker': tool('E9'), 'clavin': tool('E10', 'R4'),
         'brosk': tool('E7', 'E8', 'R5'), 'webbin': tool('E11', cap='webbin_urns')}
RETIRE = {'yonker': 'lummet', 'clavin': 'sprote'}             # drift '<tool>_retired': the tool stops, the other name does its work
TOOLS = {t: s['arity'] for t, s in TABLE.items()}
CAPABILITY = {t: s['cap'] for t, s in TABLE.items() if s['cap']}


class TarnWorkspace(IsleWorkspace):
    BODY = 'tarn'
    TABLE = TABLE
    RETIRE = RETIRE
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
