#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SMS_RELAY_DDNS_ENV:-$ROOT_DIR/ddns.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing $name. Copy ddns.env.example to ddns.env and fill it in." >&2
    exit 1
  fi
}

require_var CF_API_TOKEN
require_var CF_RECORD_NAME

CF_RECORD_TYPE="${CF_RECORD_TYPE:-A}"
CF_RECORD_PROXIED="${CF_RECORD_PROXIED:-true}"
CF_RECORD_TTL="${CF_RECORD_TTL:-1}"
CF_IP_SOURCE="${CF_IP_SOURCE:-https://api.ipify.org}"

api() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  if [[ -n "$body" ]]; then
    curl -fsS -X "$method" \
      -H "Authorization: Bearer $CF_API_TOKEN" \
      -H "Content-Type: application/json" \
      --data "$body" \
      "https://api.cloudflare.com/client/v4/$path"
  else
    curl -fsS -X "$method" \
      -H "Authorization: Bearer $CF_API_TOKEN" \
      -H "Content-Type: application/json" \
      "https://api.cloudflare.com/client/v4/$path"
  fi
}

json_get() {
  local expr="$1"
  python3 -c "import json,sys; data=json.load(sys.stdin); print($expr)"
}

if [[ -z "${CF_ZONE_ID:-}" ]]; then
  require_var CF_ZONE_NAME
  zone_response="$(api GET "zones?name=$CF_ZONE_NAME")"
  CF_ZONE_ID="$(printf '%s' "$zone_response" | json_get "data['result'][0]['id'] if data.get('result') else ''")"
fi

if [[ -z "${CF_ZONE_ID:-}" ]]; then
  echo "Could not find Cloudflare zone ID for CF_ZONE_NAME=$CF_ZONE_NAME" >&2
  exit 1
fi

public_ip="$(curl -fsS "$CF_IP_SOURCE" | tr -d '[:space:]')"

if [[ -z "$public_ip" ]]; then
  echo "Could not detect public IP from $CF_IP_SOURCE" >&2
  exit 1
fi

record_response="$(api GET "zones/$CF_ZONE_ID/dns_records?type=$CF_RECORD_TYPE&name=$CF_RECORD_NAME")"
record_count="$(printf '%s' "$record_response" | json_get "len(data.get('result', []))")"

if [[ "$record_count" == "0" ]]; then
  create_body="$(CF_RECORD_TYPE="$CF_RECORD_TYPE" \
    CF_RECORD_NAME="$CF_RECORD_NAME" \
    public_ip="$public_ip" \
    CF_RECORD_TTL="$CF_RECORD_TTL" \
    CF_RECORD_PROXIED="$CF_RECORD_PROXIED" \
    python3 - <<'INNER_PY'
import json
import os

proxied = os.environ['CF_RECORD_PROXIED'].lower() in {'1', 'true', 'yes', 'on'}
print(json.dumps({
    'type': os.environ['CF_RECORD_TYPE'],
    'name': os.environ['CF_RECORD_NAME'],
    'content': os.environ['public_ip'],
    'ttl': int(os.environ['CF_RECORD_TTL']),
    'proxied': proxied,
}))
INNER_PY
)"
  create_response="$(api POST "zones/$CF_ZONE_ID/dns_records" "$create_body")"
  success="$(printf '%s' "$create_response" | json_get "str(data.get('success', False)).lower()")"
  if [[ "$success" != "true" ]]; then
    echo "Cloudflare DDNS create failed:" >&2
    printf '%s\n' "$create_response" >&2
    exit 1
  fi
  echo "Cloudflare DDNS created: $CF_RECORD_NAME -> $public_ip proxied=$CF_RECORD_PROXIED"
  exit 0
fi

CF_RECORD_ID="${CF_RECORD_ID:-$(printf '%s' "$record_response" | json_get "data['result'][0]['id']")}" 
current_ip="$(printf '%s' "$record_response" | json_get "data['result'][0]['content']")"
current_proxied="$(printf '%s' "$record_response" | json_get "str(data['result'][0].get('proxied', False)).lower()")"

if [[ "$current_ip" == "$public_ip" && "$current_proxied" == "$CF_RECORD_PROXIED" ]]; then
  echo "Cloudflare DDNS unchanged: $CF_RECORD_NAME -> $public_ip proxied=$CF_RECORD_PROXIED"
  exit 0
fi

update_body="$(CF_RECORD_TYPE="$CF_RECORD_TYPE" \
  CF_RECORD_NAME="$CF_RECORD_NAME" \
  public_ip="$public_ip" \
  CF_RECORD_TTL="$CF_RECORD_TTL" \
  CF_RECORD_PROXIED="$CF_RECORD_PROXIED" \
  python3 - <<'INNER_PY'
import json
import os

proxied = os.environ['CF_RECORD_PROXIED'].lower() in {'1', 'true', 'yes', 'on'}
print(json.dumps({
    'type': os.environ['CF_RECORD_TYPE'],
    'name': os.environ['CF_RECORD_NAME'],
    'content': os.environ['public_ip'],
    'ttl': int(os.environ['CF_RECORD_TTL']),
    'proxied': proxied,
}))
INNER_PY
)"

update_response="$(api PUT "zones/$CF_ZONE_ID/dns_records/$CF_RECORD_ID" "$update_body")"
success="$(printf '%s' "$update_response" | json_get "str(data.get('success', False)).lower()")"

if [[ "$success" != "true" ]]; then
  echo "Cloudflare DDNS update failed:" >&2
  printf '%s\n' "$update_response" >&2
  exit 1
fi

echo "Cloudflare DDNS updated: $CF_RECORD_NAME $current_ip -> $public_ip proxied=$CF_RECORD_PROXIED"
