# Routine: Daily summary (16:15 ET)

Read CLAUDE.md first and follow the standard run procedure. The market just
closed; this routine records the day and reports. No trading (the engine will
reject orders after hours anyway — if a hard-stop breach is found now, journal
it prominently for the market-open routine).

1. `python3 scripts/engine.py status` and `python3 scripts/engine.py reconcile`
   (afternoon stop-outs get recorded here).
2. Compute the day:
   - Day P&L % = today's equity vs the previous row in Equity History
     (`memory/TRADE-LOG.md`). If the table is empty, this is day one — use
     equity as the baseline and say so.
   - Cumulative return % = today's equity vs the first row's equity.
3. Append today's row to **Equity History** in `memory/TRADE-LOG.md`.
4. Write the day's closing journal entry: what happened, stop-outs reconciled,
   each open position's pnl and stop level, anything the next pre-market run
   must look at first.
5. Commit and push.
6. Discord daily summary, **under 15 lines**:
   equity + day P&L + cumulative return, open positions one-liner each
   (symbol, pnl%, stop), trades/exits today, weekly budget used, one-sentence
   outlook for tomorrow.
