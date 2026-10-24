"""Materialize the frozen R1 preregistration and file bindings; never run trial."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.representation_r1_eval import source_hashes, sha, save


if __name__ == '__main__':
    training = ROOT / 'evidence/r1-training'
    save(ROOT / 'docs/R1_PREREG_V1.json', {
        'attempt': 'r1-v1', 'seed': 91779419, 'blocks': 32,
        'bootstrap_seed': 417221, 'bootstrap_replicates': 10000,
        'deadline_unix': 1789662900,
        'min_on_success': .90, 'min_lift': .30, 'min_lcb': .20,
        'max_on_collateral': .05, 'min_collateral_reduction': .30,
        'source_hashes': source_hashes(),
        'training_hashes': {path.name: sha(path) for path in sorted(training.iterdir()) if path.is_file()},
        'design': '32 randomized blocks each containing linked and independent cases, each ON/OFF once (128 episodes total, 64 per arm). Same seeds/payload/goal/2-action budget per pair. Conditions and arm order counterbalanced. Fresh names and payload lengths 53..511, versus training 7/41 bytes. Both target roles randomized. Frozen inner models trained from the SAME 176 native transitions; ON gets R0-induced channel, OFF has it removed during training and execution. No adaptation to final cases.',
        'success': 'Native target bytes empty AND sibling/reference bytes identical to original. Independently replay ALL episodes from external config. Success denominator=64 per arm, harmful collateral denominator=64 per arm; any intermediate sibling change counts even if repaired. Pair-block bootstrap success-lift one-sided 95% LCB from 10000 resamples; this is only within the deliberately narrow generator, NOT mechanics/general intelligence uncertainty.',
        'decision': 'All runtime/measurement gates plus success>=.90, lift>=.30, paired LCB>=.20, harm<=.05, harm reduction>=.30, no independent-control regression, exact predicted dynamic relation in every ON executed step. No retry. Source/training mismatch before marker means readiness blocked; after marker an interrupted or malformed attempt is INVALID and not rerun. Valid metric failure is RED. No threshold tuning.',
        'cost': 'Report native action counts, OS worker CPU including startup, measured parent episode CPU and separate verification CPU. Training corpus=176 native transitions; development/training time disclosed but no comprehensive energy/efficiency claim or cost-lift gate in this first narrow capability test.',
        'mechanism': '7 new relation contract/adversarial tests pass; broader suite 342 passed/1 known expired transfer deadline failure/2 skips. Native observed values are acquired by Sandbox, never caller supplied. R0 grammar and human-selected stat sensor remain acknowledged. Fixed vocab per model; no autonomous online predicate birth. Generic exact file-size goals supplied by operator. No hardlink-specific cognition branch.',
        'limitations': ['Single known native mechanism, not unseen mechanics or generality', 'Privileged human-supplied raw stat sensor, relation selected by simple search', 'Frozen vocabulary and operator-chosen experiments/goals', 'Size goal is supplied; exact-byte evaluation is stricter', 'Local trusted host, not external E5', 'Production OFF, main repository untouched, no push'],
    })
