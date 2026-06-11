# Routine: Pre-market research (08:30 ET)

Read CLAUDE.md first and follow the standard run procedure. You are preparing
the trading plan for today's market-open routine — you do NOT place trades in
this routine.

1. `python3 scripts/engine.py status` and `python3 scripts/engine.py reconcile`.
   Protect any unprotected positions (`engine.py protect SYM`) — queued stops
   from the PDT fallback ladder are placed now.
2. Read `memory/TRADING-STRATEGY.md`, `memory/WATCHLIST.md`, the last 3 days of
   `memory/RESEARCH-LOG.md`, and the Journal in `memory/TRADE-LOG.md`.
3. Research with WebSearch (multiple searches):
   - Overnight market action, index futures, VIX, today's economic calendar
     (Fed speakers, CPI/PPI/jobs prints), notable earnings today/tomorrow.
   - News on every currently held position — has any thesis broken overnight?
   - Sector strength/weakness; fresh catalysts on watchlist names; at most a
     couple of new candidate tickers with concrete, dated catalysts.
4. Make a regime call (trending / choppy / event-driven) and formulate **0-3
   trade ideas** following the playbook bars in TRADING-STRATEGY.md. Respect
   the remaining weekly trade budget and blocked sectors from `status`. Zero
   ideas is a perfectly good output on a bad tape — say so explicitly and why.
   Also list ideas you considered and rejected, with reasons.
5. Write today's dated entry at the top of `memory/RESEARCH-LOG.md` (use the
   format in that file). Update `memory/WATCHLIST.md` adds/removes.
6. If any held position's thesis broke overnight, flag it prominently in the
   research entry so the market-open routine exits it — do not exit pre-market.
7. Commit and push. Send a Discord update (≤ 8 lines): regime call, trade ideas
   (or "no trades planned"), and any thesis warnings on held positions.
