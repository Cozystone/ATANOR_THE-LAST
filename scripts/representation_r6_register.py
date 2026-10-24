import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.representation_r1_eval import save,source_hashes,sha
if __name__=='__main__':
    save(ROOT/'docs/R6_PREREG_V1.json',{
        'attempt':'r6-v1','seed':917660281,'bootstrap_seed':667193,'blocks':8,
        'arms':['lookahead','active','random','none'],'acquisition_budget':32,
        'deadline_unix':time.time()+7200,'source_hashes':source_hashes(),
        'projection_sha256':sha(ROOT/'evidence/r2-discovery/receipt.json'),
        'thresholds':{'success_rate_min':.875,'none_lift_min':.25,'none_lcb95_min':.1,
                      'other_controls_lift_min':0,'other_controls_lcb95_min':-.05,
                      'native_actions_per_success_no_worse_than_every_control':True},
        'design':'8 paired seed blocks x 4 arms x 8 native tasks =256 tasks. Same observation menus and native experiment opportunities; lookahead may stop early; controls at32, none0. CPU separately reported, not ignored or called efficient.',
        'exposure':'R4,R5,R6 DEV44017 exposed. Fresh seeds only, not unseen mechanics. Source/model grammar fixed before results. Exactly one attempt.',
        'hard_gates':'Budgets32/2, only actual acquired transitions in learner snapshots, source unchanged, independent stdlib native reexecution before sealing.',
        'limitations':'Trusted in-process research runner, not external independent evaluation or hostile-process containment. Resettable context menus supplied by operator. Future hypotheses are query views only.'})
