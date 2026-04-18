#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <username> <password> <option>"
  echo "Example: $0 pranav pranav123 A"
  exit 1
fi

USERNAME="$1"
PASSWORD="$2"
OPTION="$(echo "$3" | tr '[:lower:]' '[:upper:]')"
BASE_URL="${BASE_URL:-http://127.0.0.1:8443}"

if [[ "$OPTION" != "A" && "$OPTION" != "B" && "$OPTION" != "C" ]]; then
  echo "Error: option must be A, B, or C"
  exit 1
fi

# Login first and extract token, then submit vote with that token.
LOGIN_PAYLOAD=$(printf '{"username":"%s","password":"%s"}' "$USERNAME" "$PASSWORD")
LOGIN_RESPONSE=$(curl -sS -X POST "$BASE_URL/api/login" -H "Content-Type: application/json" -d "$LOGIN_PAYLOAD")

TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | python3 -c 'import json, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
print(payload.get("token", ""))')

if [[ -z "$TOKEN" ]]; then
  echo "Login failed. Response:"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

VOTE_PAYLOAD=$(printf '{"token":"%s","option":"%s"}' "$TOKEN" "$OPTION")
VOTE_RESPONSE=$(curl -sS -X POST "$BASE_URL/api/vote" -H "Content-Type: application/json" -d "$VOTE_PAYLOAD")

echo "Vote response:"
echo "$VOTE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VOTE_RESPONSE"