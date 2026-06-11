# Routine: Midday scan (12:00 ET)

Read CLAUDE.md first and follow the standard run procedure. This routine
manages existing positions only — no new entries.

1. `python3 scripts/engine.py status` and `python3 scripts/engine.py reconcile`.
   Protect any unprotected positions.
2. For every open position, decide in this order:
   - **Hard stop**: pnl ≤ −7% → `engine.py exit SYM "hard stop -7% breached"`.
   - **Broken thesis**: quick WebSearch on each held name for material adverse
     news (guidance cut, downgrade-driving event, thesis falsifier from the
     journal). If the journaled falsifier has occurred → exit, even if pnl is
     fine. Cite the evidence in the journal.
   - **Stop ladder**: peak gain ≥ +20% → `engine.py tighten SYM 5`;
     peak gain ≥ +15% → `engine.py tighten SYM 7`. Use the position's current
     pnl from `status` as the proxy for peak gain; the engine enforces
     tighten-only and the 3% spot gap, so a rejected tighten is fine — journal it.
   - **news-sentiment positions**: if the catalyst is absorbed (price stalled
     2+ sessions post-news), exit proactively per the playbook.
3. Journal the scan in `memory/TRADE-LOG.md`: per-position one-liners
   (pnl, action taken or "hold, thesis intact"). No action is still an entry.
4. Commit and push. Discord update only if you took an action (exit/tighten) or
   a position is within 2% of its hard stop — otherwise stay silent.
