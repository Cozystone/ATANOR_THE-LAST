"""G_SURVIVAL_PLAN.md: a life born with a genome eats and dies; one made without stays as before."""
import json
import os
from pathlib import Path

import pytest

from atanor_os.life import host
from atanor_os.life.lineage import birth, clamp, cross, mutate, random_genome
from atanor_os.life.metabolism import E0, GENOME, PRICES, Death

os.environ.setdefault('ATANOR_LEARNER', 'next_explore')


def _life(d, genome):
    host.schedule = lambda bodies, sessions: [{'kind': 'session', 'body': 'board', 'i': 0}]
    if genome is not None:
        birth(d, 1, ['board'], 1, genome)
    return host.Life(d, 1, ['board'], 1)


def test_a_life_without_a_genome_has_no_metabolism(tmp_path):
    life = _life(tmp_path / 'old', None)
    for _ in range(50):
        life.journal.append('ACTION_INTENT', body='board', source='x', actor='learner', tool='t', args=[], caps=None, before={})
    assert not life.metab.enabled and not (tmp_path / 'old' / '.dead').exists()
    assert not [r for r in life.journal.rows() if r['kind'] == 'INTEROCEPTION']
    life.close()


def test_a_life_with_a_genome_pays_dies_once_and_never_reopens(tmp_path):
    d = tmp_path / 'g'
    life = _life(d, clamp(dict(zip(GENOME, (0.99, 6, 10, 30.0, 90.0, 1.0, 0)))))
    assert life.metab.enabled and life.metab.E == E0
    life.journal.append('PREDICTION', body='board', tool='t', args=[], reader='BAYES0.99', before={}, outcome=None, why='x')
    assert life.metab.E == pytest.approx(E0 - PRICES['PREDICTION'])
    inter = [r for r in life.journal.rows() if r['kind'] == 'INTEROCEPTION']
    assert inter and inter[-1]['data']['why'] == 'PREDICTION'
    n = 0
    with pytest.raises(Death):
        while True:
            n += 1
            life.journal.append('ACTION_INTENT', body='board', source='x', actor='learner', tool='t', args=[], caps=None, before={})
    rows = life.journal.rows()
    assert rows[-1]['kind'] == 'HOST' and rows[-1]['data']['event'] == 'death'
    import math
    assert (d / '.dead').exists() and n == math.ceil((E0 - PRICES['PREDICTION']) / PRICES['ACTION_INTENT'])
    life.close()
    with pytest.raises(Death):
        host.Life(d, 1, ['board'], 1)                      # over for good


def test_energy_is_the_record_so_a_restart_keeps_it(tmp_path):
    d = tmp_path / 'r'
    life = _life(d, clamp(dict(zip(GENOME, (0.99, 6, 10, 30.0, 90.0, 1.0, 0)))))
    for _ in range(7):
        life.journal.append('ACTION_INTENT', body='board', source='x', actor='learner', tool='t', args=[], caps=None, before={})
    e = life.metab.E
    life.close()
    again = host.Life(d, 1, ['board'], 1)
    assert again.metab.E == pytest.approx(e) and again.metab.enabled
    again.close()


def test_genomes_stay_in_bounds_and_inheritance_is_read_not_lived(tmp_path):
    import random
    rng = random.Random(3)
    for _ in range(50):
        g = mutate(cross(random_genome(rng), random_genome(rng), rng), rng)
        assert set(g) == set(GENOME) and g['E_high'] > g['E_low'] and 0.9 <= g['tau'] <= 0.999 and g['guide'] in (0, 1)
    p = tmp_path / 'parent'
    (p / 'mind').mkdir(parents=True)
    (p / 'mind' / 'experiences.jsonl').write_text(json.dumps({'id': 'x0', 't': 0, 'body': 'board', 'source': 'program', 'actor': 'learner',
                                                             'action': {'tool': 't', 'args': ['a']}, 'before': {'a': {}}, 'after': {'a': {}}, 'intent': 5}) + '\n'
                                                  + json.dumps({'id': 'x1', 't': 1, 'body': 'board', 'source': 'program', 'kind': 'answer'}) + '\n', encoding='utf-8')
    c = tmp_path / 'child'
    birth(c, 1, ['board'], 1, random_genome(rng), parents=[p])
    items = [json.loads(l) for l in (c / 'mind' / 'experiences.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(items) == 1 and items[0]['source'] == 'read' and 'intent' not in items[0] and items[0]['inherited_from'] == 'parent'
