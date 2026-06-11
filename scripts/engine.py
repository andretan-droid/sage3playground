#!/usr/bin/env python3
"""Trading engine — the ONLY permitted path for order mutations.

Every buy, exit, stop placement, and stop adjustment goes through this file so
the hard risk gates are enforced deterministically, in code, regardless of what
the LLM decides. The agent may read this file but must never modify it.

Subcommands:
  status                          JSON snapshot: account, positions, gates, warnings
  buy SYM QTY|auto SECTOR PLAYBOOK "thesis"
                                  Gate-checked market buy + immediate protective stop
  exit SYM "reason"               Cancel stops, close position, log realized P&L
  tighten SYM TRAIL_PCT           Tighten a trailing stop (tighten-only, 3% spot gap)
  protect SYM                     Place a protective stop on an unprotected position
  reconcile                       Sync ledger with broker fills (stop-outs etc.)
  unblock SECTOR "reason"         Lift a sector block (weekly review only)

Hard gates (do not edit without a human-reviewed PR):
  long-only US equities, no OTC, whole shares, max 6 positions, max 20% equity
  per position, max 3 new buys per Mon-Fri week, 10% trailing stop on entry,
  stops tighten-only and never within 3% of spot, sector blocked after 2
  consecutive realized losses.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADE_LOG = os.path.join(REPO_ROOT, "memory", "TRADE-LOG.md")

BASE_URL = os.environ.get("APCA_BASE_URL", "https://paper-api.alpaca.markets").rstrip("/")
DATA_URL = "https://data.alpaca.markets"

# ---- Hard risk parameters -------------------------------------------------
MAX_POSITIONS = 6
MAX_POSITION_PCT = 0.20          # of total equity
MAX_WEEKLY_BUYS = 3              # new positions per Mon-Fri week
DEFAULT_TRAIL_PCT = 10.0         # trailing stop on every entry
FALLBACK_STOP_PCT = 7.0          # static stop fallback, % below entry
HARD_STOP_PCT = -7.0             # routine-time hard exit threshold (informational here)
MIN_SPOT_GAP_PCT = 3.0           # a stop may never sit within 3% of spot
ALLOWED_TRAILS = (10.0, 7.0, 5.0)
SECTOR_LOSS_LIMIT = 2            # consecutive realized losses -> sector block

LEDGER_BEGIN = "<!-- LEDGER:BEGIN -->"
LEDGER_END = "<!-- LEDGER:END -->"
LEDGER_COLS = ["ts_et", "action", "symbol", "qty", "price", "notional",
               "sector", "playbook", "pnl_pct", "order_id", "note"]


# ---- HTTP -----------------------------------------------------------------

def _headers():
    key = os.environ.get("APCA_API_KEY_ID")
    sec = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not sec:
        die("Missing APCA_API_KEY_ID / APCA_API_SECRET_KEY environment variables.")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec,
            "Content-Type": "application/json"}


def api(path, method="GET", body=None, base=None):
    url = (base or BASE_URL) + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise ApiError(f"{method} {path} -> HTTP {e.code}: {detail}") from None


class ApiError(Exception):
    pass


def die(msg, code=1):
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(code)


def ok(payload):
    payload["ok"] = True
    print(json.dumps(payload, indent=2))


def now_et():
    return datetime.now(tz=ET)


# ---- Ledger ----------------------------------------------------------------

def read_ledger():
    with open(TRADE_LOG, encoding="utf-8") as f:
        text = f.read()
    if LEDGER_BEGIN not in text or LEDGER_END not in text:
        die(f"Ledger markers missing in {TRADE_LOG}.")
    block = text.split(LEDGER_BEGIN)[1].split(LEDGER_END)[0]
    rows = []
    for line in block.strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0] == "ts_et":
            continue
        if len(cells) >= len(LEDGER_COLS):
            rows.append(dict(zip(LEDGER_COLS, cells)))
    return rows


def append_ledger(**fields):
    row = {c: str(fields.get(c, "")) for c in LEDGER_COLS}
    row["ts_et"] = fields.get("ts_et", now_et().strftime("%Y-%m-%d %H:%M"))
    # pipes would corrupt the markdown table
    row = {k: v.replace("|", "/") for k, v in row.items()}
    line = "| " + " | ".join(row[c] for c in LEDGER_COLS) + " |"
    with open(TRADE_LOG, encoding="utf-8") as f:
        text = f.read()
    text = text.replace(LEDGER_END, line + "\n" + LEDGER_END)
    with open(TRADE_LOG, "w", encoding="utf-8") as f:
        f.write(text)
    return row


def week_start_et():
    n = now_et()
    monday = (n - timedelta(days=n.weekday())).replace(hour=0, minute=0,
                                                       second=0, microsecond=0)
    return monday


def weekly_buy_count(rows):
    start = week_start_et()
    count = 0
    for r in rows:
        if r["action"] != "BUY":
            continue
        try:
            ts = datetime.strptime(r["ts_et"], "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        except ValueError:
            continue
        if ts >= start:
            count += 1
    return count


def sector_state(rows):
    """Returns (blocked: set, streaks: dict sector -> consecutive losses)."""
    streaks, blocked = {}, set()
    for r in rows:
        sector = r.get("sector", "")
        if r["action"] == "SELL" and sector:
            try:
                pnl = float(r["pnl_pct"])
            except ValueError:
                continue
            if pnl < 0:
                streaks[sector] = streaks.get(sector, 0) + 1
                if streaks[sector] >= SECTOR_LOSS_LIMIT:
                    blocked.add(sector)
            else:
                streaks[sector] = 0
        elif r["action"] == "UNBLOCK" and sector:
            blocked.discard(sector)
            streaks[sector] = 0
        elif r["action"] == "BLOCK" and sector:
            blocked.add(sector)
    return blocked, streaks


def sector_of(rows, symbol):
    for r in reversed(rows):
        if r["action"] == "BUY" and r["symbol"] == symbol and r.get("sector"):
            return r["sector"]
    return ""


def open_symbols_in_ledger(rows):
    """Symbols with a BUY not followed by a SELL."""
    state = {}
    for r in rows:
        if r["action"] == "BUY":
            state[r["symbol"]] = r
        elif r["action"] == "SELL":
            state.pop(r["symbol"], None)
    return state


# ---- Broker helpers ---------------------------------------------------------

def get_account():
    return api("/v2/account")


def get_positions():
    return api("/v2/positions")


def get_open_orders(symbol=None):
    path = "/v2/orders?status=open&limit=200"
    if symbol:
        path += f"&symbols={symbol}"
    return api(path)


def latest_price(symbol):
    try:
        q = api(f"/v2/stocks/{symbol}/quotes/latest?feed=iex", base=DATA_URL)
        ask = float(q.get("quote", {}).get("ap") or 0)
        if ask > 0:
            return ask
    except ApiError:
        pass
    t = api(f"/v2/stocks/{symbol}/trades/latest?feed=iex", base=DATA_URL)
    price = float(t.get("trade", {}).get("p") or 0)
    if price <= 0:
        raise ApiError(f"No live price available for {symbol}.")
    return price


def stop_orders_for(symbol):
    return [o for o in get_open_orders(symbol)
            if o.get("side") == "sell"
            and o.get("type") in ("trailing_stop", "stop", "stop_limit")]


def wait_for_fill(order_id, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        o = api(f"/v2/orders/{order_id}")
        if o.get("status") == "filled":
            return o
        if o.get("status") in ("canceled", "expired", "rejected"):
            raise ApiError(f"Order {order_id} ended as {o['status']}.")
        time.sleep(3)
    raise ApiError(f"Order {order_id} not filled within {timeout}s.")


# ---- Protective stop ladder --------------------------------------------------

def place_protective_stop(symbol, qty, entry_price):
    """Trailing stop -> static stop -> queued. Returns (kind, order_id_or_note)."""
    try:
        o = api("/v2/orders", "POST", {
            "symbol": symbol, "qty": str(qty), "side": "sell",
            "type": "trailing_stop", "trail_percent": str(DEFAULT_TRAIL_PCT),
            "time_in_force": "gtc",
        })
        return "trailing_10pct", o["id"]
    except ApiError as e1:
        try:
            stop_price = round(entry_price * (1 - FALLBACK_STOP_PCT / 100), 2)
            o = api("/v2/orders", "POST", {
                "symbol": symbol, "qty": str(qty), "side": "sell",
                "type": "stop", "stop_price": str(stop_price),
                "time_in_force": "gtc",
            })
            return f"static_stop@{stop_price}", o["id"]
        except ApiError as e2:
            append_ledger(action="QUEUE_STOP", symbol=symbol, qty=qty,
                          price=entry_price,
                          note=f"stop rejected twice; place at next open. "
                               f"err1={str(e1)[:80]} err2={str(e2)[:80]}")
            return "QUEUED", "run 'engine.py protect' at next market open"


# ---- Subcommands --------------------------------------------------------------

def cmd_buy(symbol, qty_arg, sector, playbook, thesis):
    symbol = symbol.upper()
    rows = read_ledger()
    acct = get_account()
    positions = get_positions()

    if acct.get("status") != "ACTIVE":
        die(f"GATE: account status is {acct.get('status')}, not ACTIVE.")
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        die("GATE: account is blocked from trading.")

    equity = float(acct["equity"])
    cash = float(acct["cash"])

    asset = api(f"/v2/assets/{symbol}")
    if asset.get("class") != "us_equity":
        die(f"GATE: {symbol} is not a US equity (class={asset.get('class')}). Long-only stocks.")
    if not asset.get("tradable"):
        die(f"GATE: {symbol} is not tradable on Alpaca.")
    if asset.get("exchange") == "OTC":
        die(f"GATE: {symbol} is OTC; OTC tickers are prohibited.")

    if any(p["symbol"] == symbol for p in positions):
        die(f"GATE: already holding {symbol}; adding to positions is prohibited "
            f"(keeps the 20% cap meaningful).")
    if len(positions) >= MAX_POSITIONS:
        die(f"GATE: already at max {MAX_POSITIONS} open positions.")

    used = weekly_buy_count(rows)
    if used >= MAX_WEEKLY_BUYS:
        die(f"GATE: weekly cap reached ({used}/{MAX_WEEKLY_BUYS} new trades this week).")

    blocked, streaks = sector_state(rows)
    if sector in blocked:
        die(f"GATE: sector '{sector}' is blocked after {SECTOR_LOSS_LIMIT} "
            f"consecutive losses. A weekly review must unblock it.")
    if not sector or not playbook or not thesis:
        die("GATE: sector, playbook, and thesis are all required for the journal.")

    price = latest_price(symbol)
    cap = MAX_POSITION_PCT * equity
    budget = min(cap, cash)

    if qty_arg == "auto":
        qty = int(budget // price)
    else:
        qty = int(qty_arg)
    if qty < 1:
        die(f"GATE: cannot buy a whole share of {symbol} at ~${price:.2f} "
            f"within budget ${budget:.2f} (whole shares only).")
    notional = qty * price
    if notional > cap * 1.001:
        die(f"GATE: {qty} x ${price:.2f} = ${notional:.2f} exceeds 20% of equity "
            f"(${cap:.2f}). Reduce qty or use 'auto'.")
    if notional > cash:
        die(f"GATE: ${notional:.2f} exceeds available cash ${cash:.2f}. No leverage.")

    order = api("/v2/orders", "POST", {
        "symbol": symbol, "qty": str(qty), "side": "buy",
        "type": "market", "time_in_force": "day",
    })
    filled = wait_for_fill(order["id"])
    fill_price = float(filled["filled_avg_price"])
    fill_qty = int(float(filled["filled_qty"]))

    stop_kind, stop_ref = place_protective_stop(symbol, fill_qty, fill_price)

    append_ledger(action="BUY", symbol=symbol, qty=fill_qty,
                  price=f"{fill_price:.2f}", notional=f"{fill_qty * fill_price:.2f}",
                  sector=sector, playbook=playbook, order_id=filled["id"],
                  note=f"stop={stop_kind} ({stop_ref}); thesis: {thesis[:160]}")
    ok({"action": "BUY", "symbol": symbol, "qty": fill_qty,
        "fill_price": fill_price, "stop": stop_kind, "stop_ref": stop_ref,
        "weekly_buys_used": used + 1, "weekly_buys_max": MAX_WEEKLY_BUYS})


def cmd_exit(symbol, reason):
    symbol = symbol.upper()
    rows = read_ledger()
    pos = next((p for p in get_positions() if p["symbol"] == symbol), None)
    if not pos:
        die(f"No open position in {symbol}.")
    entry = float(pos["avg_entry_price"])

    for o in get_open_orders(symbol):
        api(f"/v2/orders/{o['id']}", "DELETE")
    time.sleep(2)

    close = api(f"/v2/positions/{symbol}", "DELETE")
    filled = wait_for_fill(close["id"])
    fill_price = float(filled["filled_avg_price"])
    qty = int(float(filled["filled_qty"]))
    pnl_pct = (fill_price / entry - 1) * 100

    sector = sector_of(rows, symbol)
    append_ledger(action="SELL", symbol=symbol, qty=qty,
                  price=f"{fill_price:.2f}", notional=f"{qty * fill_price:.2f}",
                  sector=sector, playbook="", pnl_pct=f"{pnl_pct:.2f}",
                  order_id=filled["id"], note=f"reason: {reason[:160]}")

    result = {"action": "SELL", "symbol": symbol, "qty": qty,
              "fill_price": fill_price, "entry": entry,
              "pnl_pct": round(pnl_pct, 2), "reason": reason}
    _maybe_block_sector(sector, result)
    ok(result)


def _maybe_block_sector(sector, result):
    if not sector:
        return
    blocked, streaks = sector_state(read_ledger())
    if sector in blocked:
        # make the block explicit and visible in the ledger
        append_ledger(action="BLOCK", symbol="", sector=sector,
                      note=f"{SECTOR_LOSS_LIMIT} consecutive losses; "
                           f"no new entries until weekly review unblocks")
        result["sector_blocked"] = sector


def cmd_tighten(symbol, new_trail):
    symbol = symbol.upper()
    new_trail = float(new_trail)
    if new_trail not in ALLOWED_TRAILS:
        die(f"GATE: trail must be one of {ALLOWED_TRAILS}.")
    stops = stop_orders_for(symbol)
    trailing = [o for o in stops if o["type"] == "trailing_stop"]
    if not trailing:
        die(f"No open trailing stop found for {symbol}. Use 'protect' first.")
    order = trailing[0]
    current_trail = float(order["trail_percent"])
    if new_trail >= current_trail:
        die(f"GATE: stops only tighten. Current trail {current_trail}%, "
            f"requested {new_trail}% is not tighter.")

    price = latest_price(symbol)
    hwm = float(order.get("hwm") or price)
    prospective_stop = max(hwm, price) * (1 - new_trail / 100)
    min_gap = price * (MIN_SPOT_GAP_PCT / 100)
    if price - prospective_stop < min_gap:
        die(f"GATE: new stop ~${prospective_stop:.2f} would sit within "
            f"{MIN_SPOT_GAP_PCT}% of spot ${price:.2f}. Not tightening.")

    try:
        replaced = api(f"/v2/orders/{order['id']}", "PATCH",
                       {"trail": str(new_trail)})
        new_id = replaced["id"]
    except ApiError:
        api(f"/v2/orders/{order['id']}", "DELETE")
        time.sleep(2)
        qty = int(float(order["qty"]))
        o = api("/v2/orders", "POST", {
            "symbol": symbol, "qty": str(qty), "side": "sell",
            "type": "trailing_stop", "trail_percent": str(new_trail),
            "time_in_force": "gtc",
        })
        new_id = o["id"]

    append_ledger(action="TIGHTEN", symbol=symbol, order_id=new_id,
                  note=f"trail {current_trail}% -> {new_trail}%")
    ok({"action": "TIGHTEN", "symbol": symbol,
        "old_trail": current_trail, "new_trail": new_trail, "order_id": new_id})


def cmd_protect(symbol):
    symbol = symbol.upper()
    pos = next((p for p in get_positions() if p["symbol"] == symbol), None)
    if not pos:
        die(f"No open position in {symbol}.")
    if stop_orders_for(symbol):
        ok({"action": "PROTECT", "symbol": symbol, "note": "already protected"})
        return
    qty = int(float(pos["qty"]))
    entry = float(pos["avg_entry_price"])
    kind, ref = place_protective_stop(symbol, qty, entry)
    if kind != "QUEUED":
        append_ledger(action="STOP", symbol=symbol, qty=qty, order_id=ref,
                      note=f"protective stop placed: {kind}")
    ok({"action": "PROTECT", "symbol": symbol, "stop": kind, "ref": ref})


def cmd_reconcile():
    rows = read_ledger()
    positions = {p["symbol"]: p for p in get_positions()}
    ledger_open = open_symbols_in_ledger(rows)
    findings = {"recorded_external_exits": [], "unprotected": [],
                "untracked_positions": []}

    # positions the ledger thinks are open but the broker closed (stop fills)
    for symbol, buy_row in ledger_open.items():
        if symbol in positions:
            continue
        after = datetime.strptime(buy_row["ts_et"], "%Y-%m-%d %H:%M") \
            .replace(tzinfo=ET).isoformat()
        closed = api(f"/v2/orders?status=closed&symbols={symbol}"
                     f"&after={after}&limit=100&direction=desc")
        fill = next((o for o in closed if o.get("side") == "sell"
                     and o.get("status") == "filled"), None)
        if not fill:
            continue
        entry = float(buy_row["price"])
        fill_price = float(fill["filled_avg_price"])
        pnl_pct = (fill_price / entry - 1) * 100
        sector = buy_row.get("sector", "")
        append_ledger(
            ts_et=now_et().strftime("%Y-%m-%d %H:%M"),
            action="SELL", symbol=symbol, qty=int(float(fill["filled_qty"])),
            price=f"{fill_price:.2f}", sector=sector, pnl_pct=f"{pnl_pct:.2f}",
            order_id=fill["id"],
            note=f"reconciled: filled server-side ({fill['type']}) "
                 f"at {fill.get('filled_at', '?')}")
        entry_result = {"symbol": symbol, "pnl_pct": round(pnl_pct, 2)}
        _maybe_block_sector(sector, entry_result)
        findings["recorded_external_exits"].append(entry_result)

    for symbol in positions:
        if not stop_orders_for(symbol):
            findings["unprotected"].append(symbol)
        if symbol not in ledger_open:
            findings["untracked_positions"].append(symbol)

    ok(findings)


def cmd_unblock(sector, reason):
    append_ledger(action="UNBLOCK", symbol="", sector=sector,
                  note=f"weekly review: {reason[:160]}")
    ok({"action": "UNBLOCK", "sector": sector, "reason": reason})


def cmd_status():
    rows = read_ledger()
    acct = get_account()
    positions = get_positions()
    clock = api("/v2/clock")
    blocked, streaks = sector_state(rows)
    queued = [r for r in rows if r["action"] == "QUEUE_STOP"
              and r["symbol"] in {p["symbol"] for p in positions}]
    pos_view = []
    for p in positions:
        stops = stop_orders_for(p["symbol"])
        pos_view.append({
            "symbol": p["symbol"], "qty": p["qty"],
            "entry": p["avg_entry_price"], "current": p["current_price"],
            "pnl_pct": round(float(p["unrealized_plpc"]) * 100, 2),
            "stops": [{"type": o["type"],
                       "trail_percent": o.get("trail_percent"),
                       "stop_price": o.get("stop_price"),
                       "id": o["id"]} for o in stops],
        })
    ok({
        "as_of_et": now_et().strftime("%Y-%m-%d %H:%M"),
        "market_open": clock.get("is_open"),
        "next_open": clock.get("next_open"), "next_close": clock.get("next_close"),
        "equity": acct["equity"], "cash": acct["cash"],
        "base_url": BASE_URL,
        "positions": pos_view,
        "position_slots_used": f"{len(positions)}/{MAX_POSITIONS}",
        "weekly_buys_used": f"{weekly_buy_count(rows)}/{MAX_WEEKLY_BUYS}",
        "blocked_sectors": sorted(blocked),
        "sector_loss_streaks": {k: v for k, v in streaks.items() if v > 0},
        "unprotected_positions": [p["symbol"] for p in positions
                                  if not stop_orders_for(p["symbol"])],
        "queued_stops": [r["symbol"] for r in queued],
        "hard_exit_threshold_pct": HARD_STOP_PCT,
    })


def main(argv):
    if len(argv) < 1:
        die("Usage: engine.py status|buy|exit|tighten|protect|reconcile|unblock ...")
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "status":
            cmd_status()
        elif cmd == "buy":
            if len(args) != 5:
                die('Usage: engine.py buy SYM QTY|auto SECTOR PLAYBOOK "thesis"')
            cmd_buy(*args)
        elif cmd == "exit":
            if len(args) != 2:
                die('Usage: engine.py exit SYM "reason"')
            cmd_exit(*args)
        elif cmd == "tighten":
            if len(args) != 2:
                die("Usage: engine.py tighten SYM TRAIL_PCT")
            cmd_tighten(*args)
        elif cmd == "protect":
            if len(args) != 1:
                die("Usage: engine.py protect SYM")
            cmd_protect(args[0])
        elif cmd == "reconcile":
            cmd_reconcile()
        elif cmd == "unblock":
            if len(args) != 2:
                die('Usage: engine.py unblock SECTOR "reason"')
            cmd_unblock(*args)
        else:
            die(f"Unknown command '{cmd}'.")
    except ApiError as e:
        die(str(e))


if __name__ == "__main__":
    main(sys.argv[1:])
