# Trade Log

Three sections: **Equity History** (one row per daily summary), **Journal**
(narrative, newest first — every decision including no-trades), and the
**Execution Ledger** (machine-written by `scripts/engine.py`; never hand-edit).

## Equity History

| date_et | equity | cash | day_pnl_pct | cum_return_pct | open_positions | notes |
|---|---|---|---|---|---|---|

## Journal

<!-- Newest entries at the top. Format:
### YYYY-MM-DD HH:MM ET — <routine>
- Decisions made and why (cite the playbook for entries)
- What would falsify each open thesis
- Explicit note when NO action was taken and why
-->

## Queued / Pending

(Stops queued by the PDT fallback ladder appear in the ledger as QUEUE_STOP and
in `engine.py status` output until placed. Anything else pending goes here.)

## Execution Ledger

Machine-written. Actions: BUY, SELL, STOP, TIGHTEN, QUEUE_STOP, BLOCK, UNBLOCK.

<!-- LEDGER:BEGIN -->
| ts_et | action | symbol | qty | price | notional | sector | playbook | pnl_pct | order_id | note |
|---|---|---|---|---|---|---|---|---|---|---|
<!-- LEDGER:END -->
