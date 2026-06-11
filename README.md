# trading-agent

An autonomous, LLM-guided portfolio management system. Claude Code wakes up on a
schedule inside an ephemeral GitHub Actions container, reads its memory from this
repository, checks the broker, makes decisions within hard-coded risk gates,
trades, journals everything, commits, and terminates.

```
cron (GitHub Actions, ET-pinned)
  └─> ephemeral container
        ├─ clone repo (Git-as-memory)
        ├─ guard: DST check + market calendar
        ├─ Claude Code headless runs routines/<routine>.md
        │    ├─ reads memory/*.md + live broker state
        │    ├─ research via built-in web search
        │    ├─ ALL order mutations via scripts/engine.py (deterministic risk gates)
        │    └─ journals decisions (including no-trades)
        ├─ commit + push memory updates
        └─ Discord notification
```

## Layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Operating manual the agent reads every run |
| `memory/TRADING-STRATEGY.md` | Hard gates (mirror of code) + the three strategy playbooks |
| `memory/TRADE-LOG.md` | Journal, equity history, and the machine-written execution ledger |
| `memory/RESEARCH-LOG.md` | Daily pre-market research and trade ideas |
| `memory/WATCHLIST.md` | Tickers under active observation |
| `memory/WEEKLY-REVIEW.md` | Friday performance reviews, grades, behavioral findings |
| `scripts/engine.py` | **The only path to orders.** Validates every gate, places stops, keeps the ledger |
| `scripts/alpaca.sh` | Read-only broker access (account, positions, quotes, bars, orders, clock) |
| `scripts/discord.sh` | Notifications (falls back to `notifications.log` if unconfigured) |
| `scripts/routine_guard.sh` | Skips runs on holidays and wrong-DST cron duplicates |
| `routines/*.md` | The five scheduled prompts (pre-market, open, midday, summary, weekly) |
| `.github/workflows/trading.yml` | Schedules and orchestrates everything |

## Hard risk gates (enforced in code, not prompts)

- Long-only US equities; no options, shorting, leverage, or OTC. Whole shares only.
- Max **6** open positions; max **20% of equity** per position; max **3** new trades per Mon–Fri week.
- Every buy is immediately protected: GTC **10% trailing stop**, with fallback ladder
  (static stop → queued for next open) for PDT-sensitive rejections.
- Stops can only tighten (7% at +15% gain, 5% at +20%), never within 3% of spot, never widen.
- Hard exit at **−7%** from entry, checked at every routine.
- Sector with 2 consecutive realized losses → new entries blocked until weekly review clears it.

## Getting started

See [SETUP.md](SETUP.md). Start with **paper trading** — the system points at
`paper-api.alpaca.markets` until you deliberately change one secret.

## Disclaimer

Educational/experimental software. Trading involves substantial risk of loss.
Nothing here is financial advice; past (paper) performance does not predict
future results. Run it on paper, read the journal, and only ever risk money
you can afford to lose.
