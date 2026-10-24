import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.representation_r1_eval import save,sha,source_hashes
if __name__=='__main__':
    save(ROOT/'docs/R8_PREREG_V1.json',{'attempt':'r8-v1','seed':917880281,'bootstrap_seed':887019,'blocks':8,
        'arms':['discriminate','lookahead','online','none'],'acquisition_budget':32,'deadline_unix':time.time()+7200,
        'source_hashes':source_hashes(),'projection_sha256':sha(ROOT/'evidence/r2-discovery/receipt.json'),
        'thresholds':{'success_rate_min':.875,'none_lift_min':.25,'none_lcb95_min':.1,
                      'other_controls_lift_min':0,'other_controls_lcb95_min':-.05,'actions_per_success_no_worse_than_all_controls':True},
        'design':'8 blocks x4 arms x8 native tasks. Acquisition cap32; task cap2. Discriminate and R6lookahead learn actual task transitions, as does zero-acquisition online control. None remains frozen. No horizon extension or DEV44017 retuning.',
        'hard_gates':'Actual acquired/task observations only in pre/post snapshots; budgets; source/projection unchanged; independent native reexecution before sealing.',
        'claims':'Finite hypothesis disagreement, not verified causal truth. Native agent action economy only; report CPU, exclude operator fixture/reset and held-out measurement setup. In-process trusted research, not external judge or OS-isolated candidate.',
        'retry_policy':'one attempt, keep every result and original R6 RED unchanged'})
