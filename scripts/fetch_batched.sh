#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  fetch_batched.sh <question_url> [total] [batch] [sleep_seconds] [output_dir]
  fetch_batched.sh --url <question_url> [--total N] [--batch N] [--sleep S] [--output DIR] [--retry N] [--dedupe id|id+author]
EOF
}

URL=""
TOTAL=30
BATCH=10
SLEEP_S=1.2
OUT_DIR=""
RETRY=2
DEDUPE="id"

if [ $# -eq 0 ]; then
  usage >&2
  exit 1
fi

if [[ "$1" != "--"* ]]; then
  URL="$1"
  TOTAL="${2:-30}"
  BATCH="${3:-10}"
  SLEEP_S="${4:-1.2}"
  OUT_DIR="${5:-}"
else
  while [ $# -gt 0 ]; do
    case "$1" in
      --url) URL="${2:-}"; shift 2 ;;
      --total) TOTAL="${2:-30}"; shift 2 ;;
      --batch) BATCH="${2:-10}"; shift 2 ;;
      --sleep) SLEEP_S="${2:-1.2}"; shift 2 ;;
      --output) OUT_DIR="${2:-}"; shift 2 ;;
      --retry) RETRY="${2:-2}"; shift 2 ;;
      --dedupe) DEDUPE="${2:-id}"; shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) echo "[error] unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
  done
fi

if [ -z "$URL" ]; then
  echo "[error] missing question url" >&2
  usage >&2
  exit 1
fi

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BASE_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  bash "$BASE_DIR/scripts/ensure_env.sh"
fi

if [ -z "$OUT_DIR" ]; then
  OUT_DIR="$BASE_DIR/data"
fi

mkdir -p "$OUT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
cd "$BASE_DIR"

python "$BASE_DIR/scripts/fetch_question_batched.py" "$URL" \
  --total "$TOTAL" \
  --batch "$BATCH" \
  --sleep "$SLEEP_S" \
  --output "$OUT_DIR" \
  --retry "$RETRY" \
  --dedupe "$DEDUPE"
