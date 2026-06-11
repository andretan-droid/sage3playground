#!/bin/bash
# Discord notification wrapper. Falls back to notifications.log when the
# webhook is unset so routines never fail on alerting.
set -euo pipefail

MESSAGE="${1:-}"
if [ -z "$MESSAGE" ]; then
    echo "usage: discord.sh \"message\"" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${DISCORD_WEBHOOK_URL:-}" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${MESSAGE}" >> "${REPO_ROOT}/notifications.log"
    echo "Webhook unset; appended to notifications.log"
    exit 0
fi

# Discord caps messages at 2000 chars; JSON-encode safely via python.
PAYLOAD=$(MESSAGE="$MESSAGE" python3 - <<'EOF'
import json, os
msg = os.environ["MESSAGE"][:1990]
print(json.dumps({"content": msg}))
EOF
)

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$DISCORD_WEBHOOK_URL")

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "Sent to Discord (HTTP ${HTTP_CODE})"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] (HTTP ${HTTP_CODE}) ${MESSAGE}" >> "${REPO_ROOT}/notifications.log"
    echo "Discord returned HTTP ${HTTP_CODE}; appended to notifications.log"
fi
