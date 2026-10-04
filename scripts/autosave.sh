#!/bin/bash
# Commit and push finished work every few minutes, so nothing is lost if the session stops mid-wave.
# Usage: bash scripts/autosave.sh [interval_seconds]
cd "$(dirname "$0")/.." || exit 1
INTERVAL=${1:-300}
while true; do
  if [ -n "$(git status --porcelain final keyA keyB diff reports 2>/dev/null)" ]; then
    python3 scripts/status.py --write > /dev/null 2>&1
    git add -A
    DONE=$(grep -o 'Batches done: \*\*[0-9]*' STATUS.md | grep -o '[0-9]*$')
    git commit -qm "Autosave: ${DONE}/82 batches done

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01X19DWC6sADXFbv8PbRTrYi" && \
    for d in 2 4 8 16; do git push -q 2>/dev/null && break; sleep $d; done
    echo "$(date -u +%H:%M) saved ${DONE}/82"
  fi
  sleep "$INTERVAL"
done
