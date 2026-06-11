# Setup Guide

## 1. Move this code into your private `trading-agent` repo

Create a **private** repository named `trading-agent` on GitHub (no README —
keep it empty), then from a machine with this code checked out:

```bash
git clone -b claude/sweet-hopper-yhhczn https://github.com/andretan-droid/sage3playground.git trading-agent
cd trading-agent
git remote set-url origin https://github.com/andretan-droid/trading-agent.git
git branch -m main
git push -u origin main
```

> Private matters: this repo will contain your full trade history and research.
> Secrets are never committed, but the journal itself is sensitive.

## 2. Create the three accounts/keys

1. **Alpaca** — sign up at alpaca.markets, open the dashboard, switch to
   **Paper Trading**, and generate an API key pair. Paper accounts start with
   $100k; you can reset the paper account to **$10,000** in the dashboard to
   match the strategy baseline (recommended so position sizing behaves as
   designed).
2. **Anthropic** — console.anthropic.com → API key. **Set a monthly spend
   limit** (e.g. $50) under Billing as a backstop. Expected usage is roughly
   $1–3/day across the 5 routines.
3. **Discord** — in your server: Server Settings → Integrations → Webhooks →
   New Webhook, pick the channel, copy the URL. If you ever paste the URL
   anywhere public, regenerate it.

## 3. Configure the GitHub repository

Settings → Secrets and variables → Actions:

**Secrets**
| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from step 2.2 |
| `APCA_API_KEY_ID` | paper key id |
| `APCA_API_SECRET_KEY` | paper secret |
| `DISCORD_WEBHOOK_URL` | from step 2.3 |

**Variables (optional)**
| Name | Value | Default |
|---|---|---|
| `APCA_BASE_URL` | `https://paper-api.alpaca.markets` | paper (safe) |
| `CLAUDE_MODEL` | e.g. `claude-sonnet-4-6` | Claude Code's default |

Then: Settings → Actions → General → Workflow permissions → **Read and write
permissions** (the agent commits its memory back to `main`).

## 4. First dry run

Actions tab → **Trading Agent** → Run workflow → routine: `premarket`.

Watch the run. Expected outcome: a new dated entry in
`memory/RESEARCH-LOG.md`, a commit on `main`, and a Discord message. Then try
`market-open` during market hours and verify in the Alpaca paper dashboard
that any buy got its trailing stop placed immediately.

### Local testing (optional)

```bash
cp .env.example .env   # fill it in
set -a; source .env; set +a
bash scripts/alpaca.sh account
bash scripts/alpaca.sh quote AAPL
python3 scripts/engine.py status
bash scripts/discord.sh "test message"
claude -p "$(cat routines/premarket.md)"   # full local routine run
```

## 5. Paper validation — minimum 2 weeks

Let the schedule run. Check daily Discord summaries and skim the journal.
Validation checklist before even thinking about live:

- [ ] Every buy got a protective stop within the same run (check ledger notes)
- [ ] A stop-out was correctly reconciled into the ledger afterwards
- [ ] Hard −7% exits fired at routine time when applicable
- [ ] Weekly cap and position cap rejections behaved correctly (`GATE:` lines)
- [ ] Stop tightening happened on a ≥+15% winner and never widened
- [ ] No-trade days were journaled with reasons
- [ ] Two Friday reviews produced honest grades and at least one useful lesson
- [ ] No failed workflow runs without a Discord alert

## 6. Live cutover (only after validation)

1. Generate **live** API keys in Alpaca (funded account).
2. Update secrets `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`; set variable
   `APCA_BASE_URL` to `https://api.alpaca.markets`.
3. On day one, watch the market-open and midday runs in real time; confirm
   fills and stop placements in the Alpaca dashboard.
4. Keep the account under PDT awareness: under $25k equity, the engine's
   stop-fallback ladder handles same-day-stop rejections, and the 3-trades/week
   cap keeps day-trade counts naturally low.

## 7. Later: Moomoo port (optional phase)

Moomoo's OpenAPI requires their **OpenD** gateway — a persistent, login-bound
daemon — which doesn't fit ephemeral GitHub Actions runners. The port means:
a small VPS running OpenD 24/7, the runner becoming a cron job on that VPS
(same repo, same routines), and `scripts/engine.py`'s broker calls swapped to
the OpenD local API. The risk gates, memory model, and routines carry over
unchanged. Revisit once the Alpaca version has a profitable, stable track
record.

## Troubleshooting

- **Run skipped**: check the guard step log — wrong-DST duplicate crons and
  market holidays skip by design.
- **Cron fired late**: GitHub schedules can lag 5–15 min at busy times; the
  routines are written to tolerate this.
- **Push rejected**: the workflow retries with pull --rebase; if two runs
  overlapped, concurrency queues the second one.
- **`GATE:` rejections**: working as intended — the engine refuses orders that
  violate hard limits; read the message in the run log/journal.
