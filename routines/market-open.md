# Routine: Market open execution (09:45 ET)

Read CLAUDE.md first and follow the standard run procedure. This is the only
routine that opens new positions.

1. `python3 scripts/engine.py status` and `python3 scripts/engine.py reconcile`.
   Place queued/missing stops with `engine.py protect SYM` before anything else.
2. Read today's entry in `memory/RESEARCH-LOG.md`. If there is no entry for
   today, do not invent trades — journal that the pre-market run is missing and
   stop after handling exits/stops.
3. **Exits first**: if research flagged a broken thesis on a held position, or
   `status` shows any position at or below −7%, exit now:
   `python3 scripts/engine.py exit SYM "reason"`.
4. For each planned trade idea, in priority order:
   - `bash scripts/alpaca.sh quote SYM` — check the live quote. Skip if the
     bid/ask spread exceeds 0.5% of price, or price gapped >5% beyond the
     level the idea was based on (journal the skip).
   - Confirm against `status`: weekly budget remaining, position slots, sector
     not blocked, cash available.
   - `python3 scripts/engine.py buy SYM auto SECTOR PLAYBOOK "one-line thesis"`
     (use an explicit qty instead of `auto` only if research specified sizing).
   - If the engine rejects with `GATE:`, journal the rejection and move on —
     never retry to circumvent a gate.
5. The engine places the protective stop automatically and reports it. If the
   result says `QUEUED`, note it in the Journal's Queued section.
6. Journal everything in `memory/TRADE-LOG.md` (Journal section, newest first):
   entries taken with playbook + falsifier, ideas skipped and why, exits with
   reasons. A no-trade day gets an entry saying so.
7. Commit and push. Discord update (≤ 10 lines): fills with prices and stops,
   skips, exits, weekly budget used.
