"""Seal one fresh-instance trial; DEV distribution exposure is explicit."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.representation_r1_eval import source_hashes, sha, save

if __name__ == '__main__':
    save(ROOT / 'docs/R3_PREREG_V1.json', {
        'attempt': 'r3-v1', 'blocks': 20, 'seed': 917330781,
        'bootstrap_seed': 330781, 'deadline_unix': time.time() + 7200,
        'source_hashes': source_hashes(),
        'training_hashes': {p.name: sha(p) for p in sorted((ROOT / 'evidence/r3-training').iterdir()) if p.is_file()},
        'design': '20 paired blocks; 4 or 5 aliases; selective and collective goals; 80 total episodes; counterbalanced arms and goals; two actions maximum.',
        'thresholds': {'on_success_rate_min': .9, 'paired_lift_min': .3, 'block_bootstrap_lcb95_min': .2,
                       'selective_success_regression_max': 0, 'total_action_increase_max': 0},
        'hard_gates': 'Every native replay green, frozen inner models, no halt or budget violation, source and training hashes unchanged.',
        'exposure': 'Training counts 2/3; DEV probes 3/4/5 and tests 3/4/5/7. Fresh instances only, NOT unseen mechanics or unseen cardinality to developers. No post-result tuning or retry.',
        'comparison': 'Same 276 transitions and observation channels; only argument-relative partition enabled/disabled. Production default OFF.',
        'inference_limit': 'Bootstrap is over this constructed mixture, not broad real-world generality; report CPU without an efficiency claim.'})
