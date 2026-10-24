"""Versioned bounded relation channels and declarative native sensor projection.

Names specify a vocabulary, never authority. The supervisor obtains observations
from native stat; a model may only predict their future values. Projection rules
are externally bound configuration, not accepted from action/proposal metadata.
"""
import copy
import math
import re

RAW_FIELDS = ('st_dev', 'st_ino', 'st_nlink', 'st_size', 'st_mode')


def validate_relations(relations, n, *, predicted=False):
    if type(relations) is not dict or len(relations) > 4:
        raise ValueError('bounded relation map required')
    for name, matrix in relations.items():
        if type(name) is not str or not re.fullmatch(r'r_[a-z0-9_]{1,48}', name):
            raise ValueError('invalid relation channel name')
        if (type(matrix) is not list or len(matrix) != n or
                any(type(row) is not list or len(row) != n for row in matrix)):
            raise ValueError('invalid relation dimensions')
        for row in matrix:
            for value in row:
                if (type(value) not in (int, float) or not math.isfinite(value) or
                        not 0 <= value <= 1 or (not predicted and value not in (0, 1))):
                    raise ValueError('invalid relation value')


def validate_spec(spec):
    if spec is None:
        return None
    if (type(spec) is not dict or set(spec) != {'version', 'fields', 'channels'} or
            spec['version'] != 'stat-comparison-v1' or type(spec['fields']) is not list or
            not spec['fields'] or len(set(spec['fields'])) != len(spec['fields']) or
            any(f not in RAW_FIELDS for f in spec['fields']) or
            type(spec['channels']) is not dict or not 1 <= len(spec['channels']) <= 4):
        raise ValueError('invalid bound sensor specification')
    validate_relations({name: [[0]] for name in spec['channels']}, 1)
    for rule in spec['channels'].values():
        if (type(rule) is not dict or set(rule) != {'column', 'operator', 'predictions', 'width'} or
                type(rule['column']) is not int or not 0 <= rule['column'] < len(spec['fields']) or
                rule['width'] != len(spec['fields']) or rule['operator'] not in ('eq', 'lt', 'le') or
                type(rule['predictions']) is not list or len(rule['predictions']) != 2 or
                any(type(v) is not bool for v in rule['predictions'])):
            raise ValueError('invalid sensor comparison')
    return copy.deepcopy(spec)


def observe_relations(paths, spec):
    spec = validate_spec(spec)
    if spec is None:
        return {}
    raw = []
    for path in paths:
        try:
            info = path.stat()
            raw.append([int(getattr(info, f)) for f in spec['fields']])
        except FileNotFoundError:
            raw.append(None)
    result = {}
    for name, rule in sorted(spec['channels'].items()):
        matrix = []
        for left in raw:
            row = []
            for right in raw:
                if left is None or right is None:
                    row.append(0.)  # explicitly supplied defined-endpoint mask
                    continue
                a, b = left[rule['column']], right[rule['column']]
                bit = {'eq': a == b, 'lt': a < b, 'le': a <= b}[rule['operator']]
                row.append(float(rule['predictions'][int(bit)]))
            matrix.append(row)
        result[name] = matrix
    return result
