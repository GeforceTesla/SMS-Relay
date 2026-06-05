#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./scripts/run-receiver.sh &
receiver_pid=$!
./scripts/run-web.sh &
web_pid=$!

cleanup() {
  kill "$receiver_pid" "$web_pid" 2>/dev/null || true
  wait "$receiver_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait -n "$receiver_pid" "$web_pid"
