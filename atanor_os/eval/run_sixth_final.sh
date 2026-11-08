#!/usr/bin/env bash
# SIXTH_BODY_PLAN.md final evaluation on the sixth body (the dye works): run once, from a frozen commit.
#   guard: the core files must not differ from 8eeb9d50 (SIXTH_BODY_PLAN.md: otherwise nothing is run)
#   stage 4: dye_run (NONE), seeds 991-993 (evaluator worlds 1091-1093, practice worlds 1291-1293),
#            learners next_noask / next_explore (the same fixed core)
#   prediction: courses 991-993 (run_act6.course), make: ATANOR-course / ATANOR (X10 own trials) / ATANOR-RM, then the
#            four SLMs, prompt p2, one try per query; score
# Usage: bash atanor_os/eval/run_sixth_final.sh <out_dir>
set -u
OUT=$1
CORE="atanor_os/rebuild/effects.py atanor_os/rebuild/learner.py atanor_os/rebuild/explore.py atanor_os/rebuild/practice.py
      atanor_os/rebuild/goals.py atanor_os/rebuild/experience.py atanor_os/rebuild/bench_predict.py atanor_os/agent
      atanor_os/eval/slm_compare.py"
if ! git diff --quiet 8eeb9d50 -- $CORE; then
  echo "CORE CHANGED since 8eeb9d50: not run"; exit 1
fi
mkdir -p "$OUT/courses"
git rev-parse HEAD > "$OUT/commit.txt"
export PYTHONPATH=.
for s in 991 992 993; do for L in next_noask next_explore; do echo "$s $L"; done; done | xargs -P 6 -L 1 sh -c '
  ATANOR_NEXT_COUNTS='"$OUT"'/counts-dye-$1-$0.jsonl ATANOR_LEARNER=$1 timeout 14400 python -m atanor_os.eval.dye_run $0 '"$OUT"' > '"$OUT"'/log-dye-$1-$0.txt 2>&1 || echo "DYE FAILED $0 $1"'
python -m atanor_os.rebuild.summ_stage4 "$OUT" 991 992 993 > "$OUT/summary.txt" 2>&1
for s in 991 992 993; do echo "dye $s"; done | xargs -P 3 -L 1 sh -c 'python -c "
import sys
from atanor_os.repr.run_act6 import _install, course
_install(); course(sys.argv[1], int(sys.argv[2]), sys.argv[3])
" $0 $1 '"$OUT"'/courses > '"$OUT"'/courses/gen-$0-$1.txt 2>&1 || echo "COURSE FAILED $0 $1"'
for s in 991 992 993; do echo "dye $s"; done | xargs -P 3 -L 1 sh -c '
  python -m atanor_os.eval.slm_compare make $0 '"$OUT"'/courses/$0-s$1 $(( $1 + 100 )) '"$OUT"'/q-$0-s$1.json - $(( $1 + 300 )) > '"$OUT"'/make-$0-$1.txt 2>&1 || echo "MAKE FAILED $0 $1"'
for M in qwen2.5:7b-instruct llama3.1:latest exaone3.5:7.8b gpt-oss:20b; do
  T=$(echo $M | tr ':/' '__')
  for f in "$OUT"/q-*.json; do python -m atanor_os.eval.slm_compare ask $M $f "$OUT"/a-$T-$(basename $f .json).jsonl p2; done
done
python -m atanor_os.eval.slm_compare score "$OUT" > "$OUT/score.json"
echo DONE > "$OUT/done.txt"
