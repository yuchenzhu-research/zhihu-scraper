#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"
FORCE_REINSTALL="${ZHIHU_FORCE_REINSTALL:-0}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 not found" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip wheel setuptools >/dev/null

if [ ! -x "$VENV_DIR/bin/zhihu" ] || [ "$FORCE_REINSTALL" = "1" ]; then
  echo "[info] installing zhihu-scraper in editable mode..."
  python -m pip install -U -e "${BASE_DIR}[cli]"
else
  echo "[ok] zhihu cli already available: $VENV_DIR/bin/zhihu"
fi

# Optional browser fallback dependencies
python -m pip install -U playwright >/dev/null || true

if command -v playwright >/dev/null 2>&1; then
  playwright install chromium || true
else
  python -m playwright install chromium || true
fi

echo "[ok] env ready"
