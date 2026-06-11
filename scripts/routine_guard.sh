#!/bin/bash
# Decides whether a scheduled run should proceed.
#   usage: routine_guard.sh ROUTINE VARIANT
#   VARIANT: edt | est | manual
# Skips when (a) this cron is the wrong-DST duplicate, or (b) the market is
# closed today (holiday/weekend). Writes proceed=true|false to $GITHUB_OUTPUT
# (or stdout when run locally).
set -euo pipefail

ROUTINE="${1:?routine required}"
VARIANT="${2:?variant required}"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"

skip() {
    echo "SKIP: $1"
    echo "proceed=false" >> "$OUT"
    exit 0
}

# 1. DST check: each routine has two UTC crons; only the one matching the
#    current America/New_York offset may run.
OFFSET=$(TZ=America/New_York date +%z)   # -0400 (EDT) or -0500 (EST)
if [ "$VARIANT" = "edt" ] && [ "$OFFSET" != "-0400" ]; then
    skip "EDT cron fired but New York is on EST (${OFFSET})."
fi
if [ "$VARIANT" = "est" ] && [ "$OFFSET" != "-0500" ]; then
    skip "EST cron fired but New York is on EDT (${OFFSET})."
fi

# 2. Market calendar: skip holidays. (Scheduled crons already exclude weekends.)
if [ -n "${APCA_API_KEY_ID:-}" ]; then
    TODAY=$(TZ=America/New_York date +%Y-%m-%d)
    CAL=$(curl -sf "${APCA_BASE_URL:-https://paper-api.alpaca.markets}/v2/calendar?start=${TODAY}&end=${TODAY}" \
        -H "APCA-API-KEY-ID: ${APCA_API_KEY_ID}" \
        -H "APCA-API-SECRET-KEY: ${APCA_API_SECRET_KEY}" || echo '[]')
    if [ "$CAL" = "[]" ] || [ -z "$CAL" ]; then
        skip "Market is closed today (${TODAY})."
    fi
else
    echo "WARN: no broker credentials; skipping calendar check."
fi

echo "PROCEED: routine=${ROUTINE} variant=${VARIANT} offset=${OFFSET}"
echo "proceed=true" >> "$OUT"
