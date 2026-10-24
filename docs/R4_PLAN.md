# R4 — bounded experiment selection DEV screen

Checkpoint 1h / hard cap 3h / account 75%-used overrides. No production promotion.
Main history checked BEFORE implementation: `6ccf6fde` documented Aug30 FAIL,
seeking cost > benefit (3227 vs no-seeking 3365); no abandoned undocumented R4
attempt in this experiment repository. This is not that old candidate's repair.

Use the existing partitioned learner, same relation channel and planner. Candidate
selects among supervisor-provided actual frame/permitted-action experiments using
its own predictive uncertainty, not after-states. Acquisition uses real temporary
files. This tests experiment choice, NOT designing experiments, inventing goals,
unattended production agency, or uncertainty calibration.

First exposed DEV seed 44017: active vs random, budgets 4/8/16/32; no-acquisition
checkpoint at 0. Equal available contexts; acquired outcomes only after selection.
Held-out actual transitions measure expected field error; separate native tasks
measure success. Acquisition and execution costs remain separate and totaled.
DEV readiness requires active mean held-out error at 8/16/32 < random, plus no
final planning success regression. Otherwise stop this selection candidate and
record NO-GO; do not tune on the measured samples and rerun it as fresh.

If DEV passes, preregister new independent seeds and numerical capability/economy
gates before a single final trial. No initial GREEN claim from DEV. A higher success
rate bought with more actions is not automatically an efficiency improvement.
