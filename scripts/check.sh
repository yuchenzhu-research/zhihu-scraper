#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"
COOKIE_FILE="$BASE_DIR/cookies.json"

if [ ! -d "$VENV_DIR" ]; then
  echo "[error] venv not found, run: bash $BASE_DIR/scripts/ensure_env.sh" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if ! command -v zhihu >/dev/null 2>&1; then
  echo "[error] zhihu CLI not found in venv" >&2
  exit 1
fi

echo "[ok] zhihu cli: $(command -v zhihu)"

echo "[info] running zhihu check..."
set +e
zhihu check
CHECK_CODE=$?
set -e

if [ -f "$COOKIE_FILE" ]; then
  echo "[ok] cookies.json exists: $COOKIE_FILE"
  if grep -q "YOUR_Z_C0_HERE\|YOUR_D_C0_HERE" "$COOKIE_FILE"; then
    echo "[warn] cookie file still uses placeholder values"
  else
    echo "[ok] cookie file appears customized"
  fi
else
  echo "[warn] cookies.json not found. create with: bash $BASE_DIR/scripts/setup_cookie.sh"
fi

if [ $CHECK_CODE -ne 0 ]; then
  echo "[warn] zhihu check returned non-zero ($CHECK_CODE)"
fi

echo "[info] output dir: $BASE_DIR/data"
echo "[done] check complete"
