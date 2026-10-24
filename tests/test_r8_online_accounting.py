from scripts.representation_r5_dev import run_arm
from scripts.representation_r8_eval import actual_training

def test_online_control_only_learns_its_actual_charged_task_steps(tmp_path):
    r=run_arm(tmp_path/'online',8211,'online',learn_tasks=True)
    assert r['acquisition_actions']==0
    assert r['pre_task_snapshot']['revision']==0
    assert r['learner_snapshot']['revision']==r['task_actions']
    assert actual_training(r)
