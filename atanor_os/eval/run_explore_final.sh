#!/usr/bin/env bash
# EXPLORE_PLAN.md final evaluation: run once, from a frozen commit.
#   courses 961-963 (5 bodies), evaluator worlds 1061-1063, practice worlds 1261-1263 (course + 300)
#   make: ATANOR-course / ATANOR (X10 own trials) / ATANOR-RM (as many random trials per action); the SLMs get the
#   course's experiences and ATANOR's trials; then the four SLMs, prompt p2, one try per query.
# Usage: bash atanor_os/eval/run_explore_final.sh <out_dir>
set -u
OUT=$1
mkdir -p "$OUT/courses"
export PYTHONPATH=.
for b in board fs view desk clime; do for s in 961 962 963; do echo "$b $s"; done; done | xargs -P 8 -L 1 sh -c 'python -c "
import sys
from atanor_os.repr.run_act6 import _install, course
_install(); course(sys.argv[1], int(sys.argv[2]), sys.argv[3])
" $0 $1 '"$OUT"'/courses > '"$OUT"'/courses/gen-$0-$1.txt 2>&1 || echo "COURSE FAILED $0 $1"'
for b in board fs view desk clime; do for s in 961 962 963; do echo "$b $s"; done; done | xargs -P 8 -L 1 sh -c '
  python -m atanor_os.eval.slm_compare make $0 '"$OUT"'/courses/$0-s$1 $(( $1 + 100 )) '"$OUT"'/q-$0-s$1.json - $(( $1 + 300 )) > '"$OUT"'/make-$0-$1.txt 2>&1 || echo "MAKE FAILED $0 $1"'
for M in qwen2.5:7b-instruct llama3.1:latest exaone3.5:7.8b gpt-oss:20b; do
  T=$(echo $M | tr ':/' '__')
  for f in "$OUT"/q-*.json; do python -m atanor_os.eval.slm_compare ask $M $f "$OUT"/a-$T-$(basename $f .json).jsonl p2; done
done
python -m atanor_os.eval.slm_compare score "$OUT" > "$OUT/score.json"
echo DONE > "$OUT/done.txt"
