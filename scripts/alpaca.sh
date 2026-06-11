#!/bin/bash
# Read-only Alpaca broker wrapper. Order mutations are NOT available here —
# all buys/sells/stops must go through scripts/engine.py (the risk gate).
set -euo pipefail

ACTION="${1:-}"
SYMBOL="${2:-}"

BASE_URL="${APCA_BASE_URL:-https://paper-api.alpaca.markets}"
DATA_URL="https://data.alpaca.markets"

if [ -z "${APCA_API_KEY_ID:-}" ] || [ -z "${APCA_API_SECRET_KEY:-}" ]; then
    echo '{"error": "Missing APCA_API_KEY_ID / APCA_API_SECRET_KEY."}' >&2
    exit 1
fi

HEADERS=(
    -H "APCA-API-KEY-ID: ${APCA_API_KEY_ID}"
    -H "APCA-API-SECRET-KEY: ${APCA_API_SECRET_KEY}"
)

case "$ACTION" in
    account)
        curl -sf "${BASE_URL}/v2/account" "${HEADERS[@]}"
        ;;
    positions)
        curl -sf "${BASE_URL}/v2/positions" "${HEADERS[@]}"
        ;;
    orders)
        curl -sf "${BASE_URL}/v2/orders?status=open&limit=200" "${HEADERS[@]}"
        ;;
    quote)
        [ -n "$SYMBOL" ] || { echo "usage: alpaca.sh quote SYM" >&2; exit 1; }
        curl -sf "${DATA_URL}/v2/stocks/${SYMBOL}/quotes/latest?feed=iex" "${HEADERS[@]}"
        ;;
    bars)
        # alpaca.sh bars SYM [timeframe] [limit]   e.g. bars AAPL 1Day 60
        [ -n "$SYMBOL" ] || { echo "usage: alpaca.sh bars SYM [tf] [limit]" >&2; exit 1; }
        TF="${3:-1Day}"
        LIMIT="${4:-60}"
        curl -sf "${DATA_URL}/v2/stocks/${SYMBOL}/bars?timeframe=${TF}&limit=${LIMIT}&feed=iex&adjustment=split" "${HEADERS[@]}"
        ;;
    clock)
        curl -sf "${BASE_URL}/v2/clock" "${HEADERS[@]}"
        ;;
    calendar)
        TODAY=$(TZ=America/New_York date +%Y-%m-%d)
        curl -sf "${BASE_URL}/v2/calendar?start=${TODAY}&end=${TODAY}" "${HEADERS[@]}"
        ;;
    *)
        echo '{"error": "Supported: account, positions, orders, quote SYM, bars SYM [tf] [limit], clock, calendar"}' >&2
        exit 1
        ;;
esac
