"""Experimental interpolation guard; not truth or learned explanation generation.

Reject predictions beyond any previously observed feature range for their rooted
context. Interior combinations are not guaranteed supported. Never changes the
underlying learned effects. Generic numeric rule, no operation/domain exceptions.
"""
from scripts.developmental_conditional_eval import Model
from scripts.developmental_rooted_probe import rooted


def supported(features, history):
    rows = tuple(history)
    if not rows:
        return False
    if any(len(row) != len(features) for row in rows):
        raise ValueError('feature width mismatch')
    return all(min(row[i] for row in rows) <= x <= max(row[i] for row in rows)
               for i, x in enumerate(features))


class BoundedContext(Model):
    def predict(self, frame, action, conditional):
        output = []
        for field, address, values in super().predict(frame, action, conditional):
            key, nodes = rooted(frame, action, field, address)
            key = self.key_transform(key)
            history = (f for f,_ in self.examples.get(key, ()))
            allowed = supported(self.numeric_context(frame,nodes), history)
            output.append((field,address,values if allowed else []))
        return output
