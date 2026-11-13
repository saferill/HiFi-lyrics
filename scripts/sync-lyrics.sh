#!/usr/bin/env bash
set -euo pipefail

mkdir -p v1/lyrics v1/translated

python3 -u scripts/sync-lyrics.py
python3 -u scripts/validate-lyrics.py --strict

CURRENT_BRANCH="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
  echo "Detached HEAD; skipping git push."
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

git add -A v1/
if ! git diff --staged --quiet v1/; then
  git commit -m "chore(lyrics): auto-sync popular lyrics database from LRCLIB [skip ci]"
  git fetch origin "$CURRENT_BRANCH"
  if ! git rebase "origin/$CURRENT_BRANCH"; then
    echo "::error::Rebase onto origin/$CURRENT_BRANCH failed. Aborting without force-push."
    git rebase --abort || true
    exit 1
  fi
  python3 -u scripts/validate-lyrics.py --strict
  git push origin "$CURRENT_BRANCH"
  echo "Lyrics updated and committed to $CURRENT_BRANCH."
else
  echo "No new lyrics or index changes to commit."
fi
