import copy

import pytest

from packages.shared_world.refinement import propose
from packages.shared_world.refinement_gate import RefinementGate, digest


def records(offset=0, permutation=False, contradictory=True):
    result = []
    for i in range(4):
        for same in (False, True):
            raw = [[100 + offset + 2*i, 3], [100 + offset + 2*i + int(not same), 3]]
            if permutation:
                raw = [list(reversed(r)) for r in raw]
            result.append({'before': {'handles': ['n0', 'n1'], 'value': i},
                           'action': {'op': 'opaque', 'args': ['n0']},
                           'after': {'changed': same if contradictory else False}, 'raw_before': raw})
    return result


def gate(train, validation):
    return RefinementGate(train, validation, expected_training=digest(train),
                          expected_validation=digest(validation), raw_fields=['x', 'y'])


def test_contradiction_drives_proposal_without_supplied_label():
    data = records()
    expression = propose(data)
    assert expression == {'format': 'relation-proposal-v1', 'width': 2, 'column': 0, 'operator': 'eq'}
    result = gate(data, records(1000)).evaluate(expression)
    assert result['accepted'] and result['validation_errors_after'] == 0
    assert result['production_authority'] is False


def test_no_contradiction_no_new_representation():
    assert propose(records(contradictory=False)) is None


def test_column_permutation_not_hardcoded():
    assert propose(records(permutation=True))['column'] == 1


def test_forged_acceptance_or_score_cannot_be_promoted():
    data = records()
    proposal = propose(data)
    authority = gate(data, records(1000))
    for key in ('verified', 'accepted', 'validation_errors_after', 'source_digest'):
        forged = dict(proposal, **{key: True})
        with pytest.raises(ValueError):
            authority.evaluate(forged)
    wrong = dict(proposal, column=1)
    assert not authority.evaluate(wrong)['accepted']


def test_changed_corpus_rejected_against_owner_manifest():
    data, validation = records(), records(1000)
    original = digest(validation)
    validation[0]['after'] = {'forged': True}
    with pytest.raises(ValueError):
        RefinementGate(data, validation, expected_training=digest(data),
                       expected_validation=original, raw_fields=['x', 'y'])


def test_owner_data_copy_and_heldout_failure_preserve_old_epoch():
    data, val = records(), records(1000)
    for row in val:
        row['raw_before'][1][0] = row['raw_before'][0][0]
    authority = gate(data, val)
    val[0]['raw_before'][1][0] += 3
    result = authority.evaluate(propose(data))
    assert not result['accepted'] and 'projection' not in result


def test_no_caller_extra_fields_in_proposer_data():
    data = records()
    data[0]['verified'] = True
    with pytest.raises(ValueError):
        propose(data)
