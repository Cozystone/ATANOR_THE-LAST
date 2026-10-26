"""An outside reader of ATANOR's ontology memory (this is the part Claude runs). It reports conflicts, thin evidence,
over-generalization, claims waiting for re-verification, scope leaks and the contrast experiment that would settle an
open question. Its suggestions are written into the ledger only as status 'proposal': the learner never acts on them;
they become claims only through ATANOR's own observation, demonstration or contrast question.

Usage: python -m atanor_os.eval.memory_audit <mind_dir> [--write]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from ..agent.memory import ClaimLedger, Memory


def audit(mind_dir, write=False):
    mem = Memory(mind_dir, events_readable=False)
    claims = mem.claims.claims()
    report = {'claims': len(claims), 'versions': len(mem.claims.versions), 'conflicts': [], 'thin': [], 'overgeneral': [],
              'recheck': [], 'scope': [], 'experiments': []}
    by_sym = defaultdict(set)
    for c in claims:
        if c['kind'] == 'denotes':
            by_sym[c['content']['symbol']].add(c['content']['refers'])
    for s, nodes in by_sym.items():
        if len(nodes) > 1:
            report['conflicts'].append({'symbol': s, 'refers_to': sorted(nodes), 'note': 'one symbol bound to several internal nodes'})
    eff = defaultdict(list)
    for c in claims:
        if c['kind'] == 'effect':
            eff[(c['content']['tool'], json.dumps(c['content']['template']))].append(c)
    for k, cs in eff.items():
        if len({json.dumps(c['content']['gained']) for c in cs}) > 1:
            report['conflicts'].append({'tool': k[0], 'claims': [c['id'] for c in cs], 'note': 'same call, different observed effects'})
    scopes = {json.dumps(c['scope'], sort_keys=True) for c in claims}
    if len(scopes) > 1:
        report['scope'].append({'scopes': sorted(scopes), 'note': 'claims from several bodies or core versions in one memory'})
    for c in claims:
        conf = ClaimLedger.confidence(c)
        if len(c['support']) <= 1 and c['kind'] != 'denotes':
            report['thin'].append({'claim': c['id'], 'kind': c['kind'], 'support': len(c['support'])})
        if c['status'] == 'needs_recheck':
            report['recheck'].append({'claim': c['id'], 'counter': c['counter'], 'confidence': round(conf, 2)})
        if c['kind'] == 'selects' and c['content'].get('alternatives'):
            alts = c['content']['alternatives']
            report['overgeneral'].append({'claim': c['id'], 'chosen': c['content']['atoms'], 'equally_fitting': len(alts)})
            report['experiments'].append({'claim': c['id'], 'ask': 'contrast an object that carries '
                                          + ' and '.join(c['content']['atoms']) + ' but lacks ' + ' / '.join(sorted({a for alt in alts for a in alt} - set(c['content']['atoms'])))[:200]})
    if write:
        for x in report['experiments']:
            mem.propose('experiment', {'about': x['claim'], 'ask': x['ask']}, 'memory audit (outside reader)')
        for x in report['conflicts']:
            mem.propose('conflict', x, 'memory audit (outside reader)')
    return report


if __name__ == '__main__':
    r = audit(sys.argv[1], write='--write' in sys.argv)
    print(json.dumps({k: (v if not isinstance(v, list) else v[:6]) for k, v in r.items()}, indent=1, default=str))
