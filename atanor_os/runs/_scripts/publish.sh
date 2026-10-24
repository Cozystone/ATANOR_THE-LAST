#!/usr/bin/env bash
# Mirror the private development repository into the public repository
# github.com/Cozystone/ATANOR_THE-LAST, one public commit per development commit.
# Before the cutover commit (message contains "[publish-all]") only commits that touched atanor_os/ were mirrored,
# and only atanor_os/ (plus a root README). From the cutover on, every development commit is mirrored with the
# whole tracked tree (atanor_os/, packages/, scripts/, tests/, docs/, evidence/ ...).
# Never published: archived third-party page texts (web/, web_*/, pages/ folders), model weights (runs/ollama),
# and anything git-ignored in the development repository.
#   publish.sh init            -> create the mirror and replay every existing commit
#   publish.sh sync            -> replay development commits not yet mirrored, then push
set -euo pipefail
DEV=/d/ATANOR-experiments/2026-09-19/developmental-research
PUB=/d/ATANOR-experiments/2026-09-19/ATANOR_THE-LAST
URL=https://github.com/Cozystone/ATANOR_THE-LAST.git
G=(git -c user.name=Codex -c user.email=codex@local -C "$PUB")

if [ "${1:-sync}" = init ]; then
  mkdir -p "$PUB"
  git -C "$PUB" init -q -b main
  git -C "$PUB" remote add origin "$URL"
fi

CUT=$(git -C "$DEV" log --grep='\[publish-all\]' --format=%h | tail -1)
if [ -n "$CUT" ]; then
  before=$(git -C "$DEV" log --reverse --format=%h "$CUT^" -- atanor_os)
  after=$(git -C "$DEV" log --reverse --format=%h "$CUT^..HEAD")
else
  before=$(git -C "$DEV" log --reverse --format=%h -- atanor_os)
  after=""
fi

mirrored=$( "${G[@]}" log --format=%B 2>/dev/null | sed -n 's/^Source: developmental-research@\([0-9a-f]*\)$/\1/p' || true)
for c in $before $after; do
  if grep -qx "$c" <<<"$mirrored"; then continue; fi
  find "$PUB" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  if grep -qx "$c" <<<"$after"; then
    git -C "$DEV" archive "$c" | tar -x -C "$PUB"
  else
    git -C "$DEV" archive "$c" atanor_os | tar -x -C "$PUB"
  fi
  # never publish archived third-party page texts or model weights
  find "$PUB" -path "$PUB/.git" -prune -o -type d \( -name web -o -name 'web_*' -o -name pages \) -prune -exec rm -rf {} + 2>/dev/null || true
  rm -rf "$PUB/atanor_os/runs/ollama"
  cp "$DEV/atanor_os/runs/_scripts/PUBLIC_README.md" "$PUB/README.md"
  "${G[@]}" add -A
  msg=$(git -C "$DEV" log -1 --format=%B "$c")
  date=$(git -C "$DEV" log -1 --format=%aD "$c")
  GIT_AUTHOR_DATE="$date" GIT_COMMITTER_DATE="$date" "${G[@]}" commit -q -m "$msg" -m "Source: developmental-research@$c"
  echo "mirrored $c"
done
"${G[@]}" push -q -u origin main ${PUSH_ARGS:-}
"${G[@]}" log --oneline -5
