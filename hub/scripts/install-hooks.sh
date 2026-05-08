#!/usr/bin/env bash
# Install F180 Hub git hooks — P1.5 Sprint F.
#
# Symlinks scripts/git-hooks/* into .git/hooks/ so the hooks travel with
# the repo (every contributor gets the same checks after running this once).
# Symlink instead of copy means hook edits in scripts/git-hooks/ apply
# immediately without re-running the installer.
#
# Usage: ./scripts/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_SRC="$REPO_ROOT/scripts/git-hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "ERROR: $REPO_ROOT is not a git repo"
  exit 1
fi

mkdir -p "$HOOKS_DST"

for hook in "$HOOKS_SRC"/*; do
  name="$(basename "$hook")"
  dst="$HOOKS_DST/$name"
  rm -f "$dst"
  ln -s "$hook" "$dst"
  chmod +x "$hook"
  echo "Installed $name -> .git/hooks/$name"
done

echo
echo "Hooks installed. Smoke test with:"
echo "  echo '/* test */' >> frontend/src/main.ts"
echo "  git add frontend/src/main.ts && git commit -m 'test'"
echo "  (then revert)"
