# Minimal loop v2 execution authorization record

V1 stopped on worker completion summary: an unfinished goal has result=None,
not missing result. Calling .get on None raised after committed native action.
This is lifecycle harness failure, not learner/capability outcome. Preserve v1.

Only change: completed_count treats missing/None as unfinished. Synthetic fixture
tests None,missing,false,true. All client learning/planning/schema/goal/budgets/
seeds/gates unchanged. New output minimal-persistent-loop-v2; one full execution.
No original sealed v1 result overwritten (v1 produced no final receipt).
