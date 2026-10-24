"""DEV candidate: move rooted values into learnable conditions, never erase them.

Preserve operation, field, argument/address roles, channel names and node count
as the structural type. Kinds and complete rooted matrix values become numeric
features alongside existing rich context. Uses unchanged conditional learner.
No semantic mapping across bodies or learned feature generation is claimed.
"""
from scripts.developmental_conditional_eval import Model
from scripts.developmental_fk_tasks import context
from packages.shared_world.relational import _matrices


def structural_key(key):
    return key[:4] + (len(key[4]), tuple(name for name,_ in key[5]))


def features(frame, nodes):
    values = tuple(frame.kinds[i] for i in nodes)
    values += tuple(matrix[i][j] for _,matrix in
                    sorted({'parent':frame.parent, **_matrices(frame)}.items())
                    for i in nodes for j in nodes)
    return values + context(frame,nodes)


def learner():
    return Model([], numeric_context=features, key_transform=structural_key)
