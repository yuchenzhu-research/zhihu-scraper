#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COOKIE_FILE="$BASE_DIR/cookies.json"
TEMPLATE_FILE="$BASE_DIR/templates/cookies.json.example"

mkdir -p "$BASE_DIR/templates"

if [ ! -f "$TEMPLATE_FILE" ]; then
  cat > "$TEMPLATE_FILE" <<'JSON'
[
  {
    "name": "z_c0",
    "value": "YOUR_Z_C0_HERE",
    "domain": ".zhihu.com",
    "path": "/"
  },
  {
    "name": "d_c0",
    "value": "YOUR_D_C0_HERE",
    "domain": ".zhihu.com",
    "path": "/"
  }
]
JSON
fi

if [ ! -f "$COOKIE_FILE" ]; then
  cp "$TEMPLATE_FILE" "$COOKIE_FILE"
  echo "[ok] created $COOKIE_FILE from template"
else
  echo "[info] $COOKIE_FILE already exists"
fi

echo "[next] edit $COOKIE_FILE and replace YOUR_Z_C0_HERE / YOUR_D_C0_HERE"
