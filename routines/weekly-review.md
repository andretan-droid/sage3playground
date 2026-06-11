# Routine: Weekly review (Friday 16:45 ET)

Read CLAUDE.md first and follow the standard run procedure. This is the
system's learning loop — be honest and specific; vague reviews produce no
improvement.

1. `python3 scripts/engine.py status` and `python3 scripts/engine.py reconcile`.
2. Compute the week from the Execution Ledger and Equity History:
   - Weekly return %, cumulative return %; WebSearch SPY's week for comparison.
   - Closed trades this week: win rate, profit factor
     (gross profits / |gross losses|), average win %, average loss %, average
     holding period.
   - Per-playbook breakdown: W-L and average pnl for momentum, news-sentiment,
     mean-reversion.
3. **Behavioral review** — reread this week's Journal entries and look for
   patterns the numbers hide: exits at the hard stop that a broken-thesis exit
   should have caught earlier; winners cut early; rejected ideas that worked
   (check what they did); gates that fired repeatedly; research quality issues.
4. **Sector blocks**: for each blocked sector, decide with evidence whether to
   `python3 scripts/engine.py unblock SECTOR "reason"` or keep it blocked
   another week. Justify either way.
5. Write the review at the top of `memory/WEEKLY-REVIEW.md` (format in file),
   including a letter grade A–F for the week's process (not just the P&L —
   a disciplined losing week can grade higher than a sloppy winning one).
6. Apply improvements to the **qualitative sections** of
   `memory/TRADING-STRATEGY.md` (playbook bars, regime guidance) with a Change
   log row citing the evidence. Hard gates are code — if you believe a hard
   parameter should change, write the proposal and evidence in the review for
   the human operator instead.
7. Housekeeping: prune RESEARCH-LOG entries older than 3 weeks; tidy the
   watchlist.
8. Commit and push. Discord weekly recap (≤ 15 lines): grade, numbers vs SPY,
   best/worst trade, one key lesson, posture for next week.
