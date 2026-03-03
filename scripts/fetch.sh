#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  fetch.sh <zhihu_url> [output_dir]
  fetch.sh --url <zhihu_url> [--output <dir>] [--retry N] [--sleep S]
EOF
}

URL=""
OUT_DIR=""
RETRY=1
SLEEP_S=1.2

if [ $# -eq 0 ]; then
  usage >&2
  exit 1
fi

if [[ "$1" != "--"* ]]; then
  URL="$1"
  OUT_DIR="${2:-}"
else
  while [ $# -gt 0 ]; do
    case "$1" in
      --url) URL="${2:-}"; shift 2 ;;
      --output) OUT_DIR="${2:-}"; shift 2 ;;
      --retry) RETRY="${2:-1}"; shift 2 ;;
      --sleep) SLEEP_S="${2:-1.2}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "[error] unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
fi

if [ -z "$URL" ]; then
  echo "[error] missing url" >&2
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

cd "$BASE_DIR"

if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$BASE_DIR/data"
fi
mkdir -p "$OUT_DIR"

attempt=1
while [ "$attempt" -le "$RETRY" ]; do
  echo "[info] fetch attempt $attempt/$RETRY"
  if zhihu fetch "$URL" --output "$OUT_DIR"; then
    echo "[ok] fetch success"
    exit 0
  fi

  if [ "$attempt" -lt "$RETRY" ]; then
    echo "[warn] fetch failed, sleep ${SLEEP_S}s then retry..."
    sleep "$SLEEP_S"
  fi
  attempt=$((attempt + 1))
done

echo "[error] fetch failed after $RETRY attempts" >&2
exit 1
