import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.representation_r1_eval import save,sha,source_hashes
if __name__=='__main__':
    save(ROOT/'docs/R9_PREREG_V1.json',{'attempt':'r9-v1','study_label':'R9','seed':917990281,'bootstrap_seed':997019,'blocks':8,
        'candidate':'focused','controls':['none','online','discriminate'],'arms':['focused','discriminate','online','none'],
        'acquisition_budget':32,'deadline_unix':time.time()+7200,'source_hashes':source_hashes(),
        'projection_sha256':sha(ROOT/'evidence/r2-discovery/receipt.json'),
        'thresholds':{'success_rate_min':.875,'none_lift_min':.25,'none_lcb95_min':.1,
                      'other_controls_lift_min':0,'other_controls_lcb95_min':-.05,'actions_per_success_no_worse_than_all_controls':True},
        'design':'8blocks x4arms x8given requests. Same horizons and budgets as R8; all except frozen-none learn ordinary task observations. Focused stop requires the unchanged planner actual choice, not merely existence of a better path. Batch request goals are given, never hidden outcomes.',
        'hard_gates':'Only actual acquired/task rows in snapshots, budgets, fixed source/projection, independent native audit.',
        'scope':'Finite grammar and known native mechanics; no verified truth/authority from agreement; trusted in-process experiment. CPU reported; operator resets/fixtures/measurement preparation excluded from agent action cost.',
        'retry_policy':'One fresh attempt; no old DEV retuning or threshold changes; old REDs preserved'})
