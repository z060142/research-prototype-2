#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
uv run python run.py --n 4000 --md results_lock.md --json results_lock.json
