#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  batch.sh <url_file> [output_dir] [concurrency]
  batch.sh --file <url_file> [--output <dir>] [--concurrency N] [--retry N] [--sleep S]
EOF
}

URL_FILE=""
OUT_DIR=""
CONCURRENCY=4
RETRY=1
SLEEP_S=1.2

if [ $# -eq 0 ]; then
  usage >&2
  exit 1
fi

if [[ "$1" != "--"* ]]; then
  URL_FILE="$1"
  OUT_DIR="${2:-}"
  CONCURRENCY="${3:-4}"
else
  while [ $# -gt 0 ]; do
    case "$1" in
      --file) URL_FILE="${2:-}"; shift 2 ;;
      --output) OUT_DIR="${2:-}"; shift 2 ;;
      --concurrency) CONCURRENCY="${2:-4}"; shift 2 ;;
      --retry) RETRY="${2:-1}"; shift 2 ;;
      --sleep) SLEEP_S="${2:-1.2}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "[error] unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
fi

if [ -z "$URL_FILE" ]; then
  echo "[error] missing url file" >&2
  usage >&2
  exit 1
fi

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"

if [ ! -f "$URL_FILE" ]; then
  echo "[error] url file not found: $URL_FILE" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  bash "$BASE_DIR/scripts/ensure_env.sh"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$BASE_DIR/data"
fi
mkdir -p "$OUT_DIR"

attempt=1
while [ "$attempt" -le "$RETRY" ]; do
  echo "[info] batch attempt $attempt/$RETRY"
  if zhihu batch "$URL_FILE" -c "$CONCURRENCY" --output "$OUT_DIR"; then
    echo "[ok] batch success"
    exit 0
  fi

  if [ "$attempt" -lt "$RETRY" ]; then
    echo "[warn] batch failed, sleep ${SLEEP_S}s then retry..."
    sleep "$SLEEP_S"
  fi
  attempt=$((attempt + 1))
done

echo "[error] batch failed after $RETRY attempts" >&2
exit 1
