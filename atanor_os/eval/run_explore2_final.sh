#!/usr/bin/env bash
# EXPLORE2_PLAN.md final evaluation: run once, from a frozen commit.
#   stage 4: clime_run (nogen1) and desk_eval2_run, seeds 971-973 (worlds 1071-1073, practice 1271-1273),
#   learners next_noask / next_explore (the same fixed core)
# Usage: bash atanor_os/eval/run_explore2_final.sh <out_dir>
set -u
OUT=$1
mkdir -p "$OUT"
export PYTHONPATH=.
for s in 971 972 973; do for L in next_noask next_explore; do echo "$s $L"; done; done | xargs -P 6 -L 1 sh -c '
  ATANOR_NEXT_COUNTS='"$OUT"'/counts-clime-$1-$0.jsonl ATANOR_LEARNER=$1 timeout 14400 python -m atanor_os.eval.clime_run $0 '"$OUT"' nogen1 > '"$OUT"'/log-clime-$1-$0.txt 2>&1 || echo "CLIME FAILED $0 $1"
  ATANOR_NEXT_COUNTS='"$OUT"'/counts-old-$1-$0.jsonl ATANOR_LEARNER=$1 timeout 14400 python -m atanor_os.eval.desk_eval2_run $0 '"$OUT"' > '"$OUT"'/log-old-$1-$0.txt 2>&1 || echo "DESK FAILED $0 $1"'
python -m atanor_os.rebuild.summ_stage4 "$OUT" 971 972 973 > "$OUT/summary.txt" 2>&1
echo DONE > "$OUT/done.txt"
