#!/usr/bin/env bash
set -euo pipefail

mkdir -p v1/lyrics v1/translated

python3 scripts/sync-lyrics.py

git config user.name "saferill"
git config user.email "saferill@users.noreply.github.com"

if ! git diff --quiet v1/; then
  git add v1/
  git commit -m "chore(lyrics): auto-sync popular lyrics database"
  git push origin main
  echo "Lyrics updated and committed successfully."
else
  echo "No new lyrics to commit."
fi