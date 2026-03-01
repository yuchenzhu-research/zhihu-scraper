#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  query.sh <keyword>
  query.sh --keyword <keyword> [--limit N] [--data-dir <dir>] [--retry N] [--sleep S]
EOF
}

KEYWORD=""
LIMIT=10
DATA_DIR=""
RETRY=1
SLEEP_S=1.2

if [ $# -eq 0 ]; then
  usage >&2
  exit 1
fi

if [[ "$1" != "--"* ]]; then
  KEYWORD="$1"
else
  while [ $# -gt 0 ]; do
    case "$1" in
      --keyword) KEYWORD="${2:-}"; shift 2 ;;
      --limit) LIMIT="${2:-10}"; shift 2 ;;
      --data-dir) DATA_DIR="${2:-}"; shift 2 ;;
      --retry) RETRY="${2:-1}"; shift 2 ;;
      --sleep) SLEEP_S="${2:-1.2}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "[error] unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
fi

if [ -z "$KEYWORD" ]; then
  echo "[error] missing keyword" >&2
  usage >&2
  exit 1
fi

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  bash "$BASE_DIR/scripts/ensure_env.sh"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ -z "$DATA_DIR" ]; then
  DATA_DIR="$BASE_DIR/data"
fi

attempt=1
while [ "$attempt" -le "$RETRY" ]; do
  echo "[info] query attempt $attempt/$RETRY"
  if zhihu query "$KEYWORD" --limit "$LIMIT" --data-dir "$DATA_DIR"; then
    echo "[ok] query success"
    exit 0
  fi

  if [ "$attempt" -lt "$RETRY" ]; then
    echo "[warn] query failed, sleep ${SLEEP_S}s then retry..."
    sleep "$SLEEP_S"
  fi
  attempt=$((attempt + 1))
done

echo "[error] query failed after $RETRY attempts" >&2
exit 1
