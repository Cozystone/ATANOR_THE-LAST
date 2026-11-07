#!/usr/bin/env bash
# REBUILD_PLAN.md final evaluation: run once, from a frozen commit, on seeds never used in development.
#   stage 2/3: courses 931-933 (5 bodies), evaluator worlds 1031-1033 (later-solo worlds: the next of the three)
#   stage 4:   clime_run and desk_eval2_run, seeds 931-933 (worlds 1031-1033), learners current / next / next_nolab / next_noask
# Usage: bash atanor_os/rebuild/run_final.sh <out_dir> <sealed.json>
set -u
OUT=$1; SE=$2
mkdir -p "$OUT/courses" "$OUT/bench" "$OUT/inq" "$OUT/s4"
export PYTHONPATH=.
for b in board fs view desk clime; do for s in 931 932 933; do
  echo "$b $s"
done; done | xargs -P 15 -L 1 sh -c 'python -c "
import sys
from atanor_os.repr.run_act6 import _install, course
_install(); course(sys.argv[1], int(sys.argv[2]), sys.argv[3])
" $0 $1 '"$OUT"'/courses > '"$OUT"'/courses/gen-$0-$1.txt 2>&1'
for b in board fs view desk clime; do for s in 931 932 933; do
  n=$(( s == 933 ? 1031 : s + 101 ))
  echo "$b $s $((s + 100)) $n"
done; done | xargs -P 15 -L 1 sh -c '
  python -m atanor_os.rebuild.bench_predict $0 '"$OUT"'/courses/$0-s$1 $2 '"$OUT"'/bench/$0-s$1.json > /dev/null 2> '"$OUT"'/bench/$0-s$1.err
  python -m atanor_os.rebuild.bench_inquiry $0 '"$OUT"'/courses/$0-s$1 $2 $3 '"$OUT"'/inq/$0-s$1.json 10 > /dev/null 2> '"$OUT"'/inq/$0-s$1.err'
for s in 931 932 933; do for L in current next next_nolab next_noask; do
  echo "$s $L"
done; done | xargs -P 6 -L 1 sh -c '
  ATANOR_NEXT_COUNTS='"$OUT"'/s4/counts-clime-$1-$0.jsonl ATANOR_LEARNER=$1 timeout 14400 python -m atanor_os.eval.clime_run $0 '"$OUT"'/s4 sealed:'"$SE"' nogen1 > '"$OUT"'/s4/log-clime-$1-$0.txt 2>&1
  ATANOR_NEXT_COUNTS='"$OUT"'/s4/counts-old-$1-$0.jsonl ATANOR_LEARNER=$1 timeout 14400 python -m atanor_os.eval.desk_eval2_run $0 '"$OUT"'/s4 sealed:'"$SE"' en:'"$SE"' > '"$OUT"'/s4/log-old-$1-$0.txt 2>&1'
echo FINAL-DONE > "$OUT/done.txt"
