"""Trusted local evaluator of untrusted expressions, NOT access-control machinery.

Only supervisor-owned, prebound observed batches are used. Candidate scores,
statuses and provenance assertions are not accepted. A passing receipt is staging
research evidence; it never authorizes production code or arbitrary Python.
No module token/registry identity is treated as authentication.
"""
from collections import defaultdict, Counter
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def error_count(records, expression):
    # Independently implemented; do not call the proposer's scoring function.
    groups = defaultdict(list)
    for row in records:
        key = {'before': row['before'], 'action': row['action']}
        if expression is not None:
            col, op = expression['column'], expression['operator']
            values = [r[col] for r in row['raw_before']]
            bits = []
            for a in values:
                for b in values:
                    bits.append(a == b if op == 'eq' else a < b if op == 'lt' else a <= b)
            key['comparison'] = bits
        groups[digest(key)].append(digest(row['after']))
    return sum(len(values) - Counter(values).most_common(1)[0][1] for values in groups.values())


class RefinementGate:
    """Policy/data supplied by trusted experiment owner BEFORE proposal arrives.

    This is not an OS sandbox: malicious code with host access can alter process
    memory. The actual proposer subprocess receives only training data. Expected
    batch hashes come from the precommitted corpus manifest, not the proposal.
    """
    def __init__(self, training, validation, *, expected_training, expected_validation,
                 raw_fields, min_reduction=.9):
        if digest(training) != expected_training or digest(validation) != expected_validation:
            raise ValueError('observation batch differs from externally bound manifest')
        # Copy owner data so later mutation of caller containers cannot change it.
        self.training = json.loads(json.dumps(training))
        self.validation = json.loads(json.dumps(validation))
        self.hashes = (expected_training, expected_validation)
        self.raw_fields = tuple(raw_fields)
        self.min_reduction = min_reduction

    def evaluate(self, proposal):
        fields = {'format', 'width', 'column', 'operator'}
        if (type(proposal) is not dict or set(proposal) != fields or
                proposal['format'] != 'relation-proposal-v1' or
                type(proposal['width']) is not int or proposal['width'] != len(self.raw_fields) or
                type(proposal['column']) is not int or not 0 <= proposal['column'] < len(self.raw_fields) or
                proposal['operator'] not in ('eq', 'lt', 'le')):
            raise ValueError('invalid or self-attested proposal')
        baseline = error_count(self.validation, None)
        error = error_count(self.validation, proposal)
        train_before = error_count(self.training, None)
        train_after = error_count(self.training, proposal)
        accepted = (baseline > 0 and train_before > train_after and
                    (baseline - error) / baseline >= self.min_reduction)
        result = {'accepted': accepted, 'train_errors_before': train_before,
                  'train_errors_after': train_after, 'validation_errors_before': baseline,
                  'validation_errors_after': error, 'proposal': proposal,
                  'training_digest': self.hashes[0], 'validation_digest': self.hashes[1],
                  'production_authority': False}
        if accepted:
            name = 'r_' + digest(proposal)[:16]
            result['projection'] = {'version': 'stat-comparison-v1', 'fields': list(self.raw_fields),
                'channels': {name: {'column': proposal['column'], 'operator': proposal['operator'],
                                  'predictions': [False, True], 'width': proposal['width']}}}
        return result
