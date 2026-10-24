"""Register a distinct fresh R2 planning attempt after staged expression acceptance."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.representation_r1_eval import source_hashes, sha, save


if __name__ == '__main__':
    receipt = json.loads((ROOT / 'evidence/r2-discovery/receipt.json').read_text())
    if receipt.get('accepted') is not True or receipt.get('production_authority') is not False:
        raise RuntimeError('no validated staging projection')
    p = json.loads((ROOT / 'docs/R1_PREREG_V1.json').read_text())
    p.update(attempt='r2-v1', study_label='R2', seed=91790281, bootstrap_seed=317533,
             deadline_unix=1789635200, projection=receipt['projection'],
             training_directory='evidence/r2-training', source_hashes=source_hashes(),
             training_hashes={path.name: sha(path) for path in sorted((ROOT / 'evidence/r2-training').iterdir()) if path.is_file()},
             refinement_receipt_sha256=sha(ROOT / 'evidence/r2-discovery/receipt.json'),
             refinement_boundary='Proposal inferred from 32 owner-observed transitions; independently recomputed acceptance on separate 32 transitions, criterion fixed before proposal. Frozen relation projection promoted only to isolated successor training, not production. R1 thresholds retained; entirely distinct fresh seed. No live vocabulary migration or autonomous experiment choice claim.')
    save(ROOT / 'docs/R2_PREREG_V1.json', p)
