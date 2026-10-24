"""Opt-in research actuator, not a learned rule or experiment recipe.

Expose native hard-link creation between owned, unprotected file handles.
Destination must already be absent; no implicit unlink, reset, or overwrite.
Default Sandbox and schemas remain unchanged. Single-process research safety,
not a sandbox against hostile concurrent filesystem mutation.
"""
import os
from .schema import bind_schema, TRANSFER_SCHEMA
from .world import Sandbox


class RelinkBody(Sandbox):
    @staticmethod
    def _native_schema(operations):
        schema = bind_schema(operations)
        allowed = TRANSFER_SCHEMA.entries + (('link', 2),)
        if any(row not in allowed for row in schema.entries):
            raise ValueError('body has no such native operation')
        return schema

    def _permitted(self, action):
        if action.op == 'link' and any(h in self.protected for h in action.args):
            return False
        return super()._permitted(action)

    def step(self, action):
        if action.op != 'link':
            return super().step(action)
        paths = self._validate(action)
        for protected in self.protected:
            target = self._checked(protected)
            if paths[0].exists() and target.exists() and os.path.samefile(paths[0], target):
                raise ValueError('cannot alias protected file')
        try:
            os.link(*paths)
        except OSError:
            return False
        return True
