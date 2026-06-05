#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  echo "Missing server/.venv. Run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -f "config.toml" ]]; then
  echo "Missing server/config.toml. Run: cp config.example.toml config.toml and edit it." >&2
  exit 1
fi

HOST="${SMS_RELAY_RECEIVER_HOST:-0.0.0.0}"
PORT="${SMS_RELAY_RECEIVER_PORT:-8000}"

exec .venv/bin/uvicorn app.main:public_app --host "$HOST" --port "$PORT"
