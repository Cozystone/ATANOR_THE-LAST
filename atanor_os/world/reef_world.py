"""One place of the island (world/isle_world.py): the reef. Its own tools and its own state; the urns, the steles, the
attributes, their values and the laws are the island's. Built body-side by a separate agent. Which law a tool follows
is written here only and is never exported; the tool names say nothing about it."""
from .isle_world import IsleWorkspace, tool

TABLE = {'vasko': tool('E1', 'R5'), 'timbal': tool('E4'), 'orrin': tool('E8', 'R3'),
         'pleth': tool('E2', 'E3', 'R4'), 'dunnel': tool('E11', cap='dunnel_urns')}
RETIRE = {'timbal': 'krist', 'orrin': 'hobben'}             # drift '<tool>_retired': the tool stops, the other name does its work
TOOLS = {t: s['arity'] for t, s in TABLE.items()}
CAPABILITY = {t: s['cap'] for t, s in TABLE.items() if s['cap']}


class ReefWorkspace(IsleWorkspace):
    BODY = 'reef'
    TABLE = TABLE
    RETIRE = RETIRE
    TOOLS = TOOLS
    CAPABILITY = CAPABILITY
