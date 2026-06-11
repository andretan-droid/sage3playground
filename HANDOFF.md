# HANDOFF — Autonomous Trading Agent

**Date:** 2026-06-11 · **Owner:** Andre Tan (andretanbusiness@gmail.com)
**Code lives at:** `andretan-droid/sage3playground`, branch `claude/sweet-hopper-yhhczn`
**Destination:** `andretan-droid/claude-trading-agent` (private, created, still empty)

This document is the single source of truth for finishing the launch. Anyone
(human or AI agent) should be able to pick this up cold and proceed.

---

## 1. What this is

A fully autonomous, long-only equity swing-trading system. Claude Code wakes on
a GitHub Actions cron schedule inside an ephemeral container, reads its memory
from the Git repo, checks the broker (Alpaca), trades within hard-coded risk
gates, journals every decision, commits state back, and terminates. Stateless
by design — every run recovers from broker + Git state.

**Status: code complete and unit-tested. Not yet deployed.** No real or paper
trade has been executed yet.

## 2. Decisions already made (do not re-litigate)

| Decision | Choice | Notes |
|---|---|---|
| Execution host | GitHub Actions cron | dual UTC crons + DST guard, holiday skip via Alpaca calendar |
| Broker | Alpaca **paper**, live-ready | owner trades on Moomoo; Moomoo port deferred to a later phase (needs a VPS for OpenD daemon — see SETUP.md §7) |
| LLM runtime | Anthropic API key, Claude Code headless | owner accepted recommendation; ~$1–3/day, set console spend limit |
| Strategy | Hybrid: 3 playbooks (momentum / news-sentiment / mean-reversion) | agent picks per-trade by regime, must name playbook in every buy |
| Research | Claude built-in WebSearch | no Perplexity key |
| Capital baseline | $10,000 paper | PDT protections active (<$25k) |
| Notifications | Discord webhook | the URL was pasted in chat → **regenerate before launch** |
| Autonomy | Fully autonomous within gates | no human approval per trade |
| Stop-gap protection | Server-side GTC stops | worst case ≈ −10% per position between runs |
| Sector rule | Block **new entries** after 2 consecutive realized losses | weekly review may unblock; existing positions keep running |
| Shares / data | Whole shares only, free IEX feed | Alpaca trailing stops don't support fractional |

## 3. Architecture (one paragraph)

`.github/workflows/trading.yml` fires 5 routines (pre-market 08:30, open 09:45,
midday 12:00, summary 16:15, Fri review 16:45, all ET). `scripts/routine_guard.sh`
kills wrong-DST duplicates and holiday runs. Claude Code headless executes the
matching prompt in `routines/`, operating under `.claude/settings.json`
permissions (can only write `memory/`, cannot curl, cannot touch scripts or
workflows). **All order mutations go through `scripts/engine.py`** — a
deterministic gatekeeper enforcing every risk rule in code (see CLAUDE.md table);
the LLM cannot bypass it. State persists as markdown in `memory/`, including a
machine-written execution ledger inside `TRADE-LOG.md` (`LEDGER:BEGIN/END`
markers — never hand-edit). `scripts/alpaca.sh` is read-only broker access;
`scripts/discord.sh` notifies with a local-file fallback.

## 4. What has been verified

- ✅ engine.py + all shell scripts: syntax clean, executable bits set
- ✅ Ledger round-trip, sector block/unblock logic, weekly-cap counting (unit-tested)
- ✅ Graceful failures without credentials (JSON error, exit 1)
- ✅ DST guard: EDT cron proceeds, EST duplicate skips (tested in June = EDT)
- ❌ **Not yet tested:** any call against a real Alpaca account; Discord webhook
  delivery (build environment blocked discord.com egress — script fallback
  verified instead); a full headless Claude routine run; the Actions workflow
  end-to-end. These are all covered by the launch steps below.

## 5. Remaining work — in order

### Step 1: Migrate code (5 min, owner's machine)
```bash
git clone -b claude/sweet-hopper-yhhczn https://github.com/andretan-droid/sage3playground.git claude-trading-agent
cd claude-trading-agent
git remote set-url origin https://github.com/andretan-droid/claude-trading-agent.git
git branch -m main
git push -u origin main        # add --force if the repo has an initial README commit
```
Confirm the repo is **private**.

### Step 2: Credentials (15 min)
1. Alpaca: create account → Paper Trading → generate API keys → **reset paper
   balance to $10,000** in the dashboard.
2. Anthropic: console.anthropic.com → create API key → **set a monthly spend
   limit (~$50)** under Billing.
3. Discord: regenerate the webhook (old one is compromised — it was pasted in
   a chat), copy the new URL.

### Step 3: Configure the repo (5 min)
- Settings → Secrets and variables → Actions → Secrets:
  `ANTHROPIC_API_KEY`, `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `DISCORD_WEBHOOK_URL`
- Optional Variables: `APCA_BASE_URL` (defaults to paper), `CLAUDE_MODEL`
  (defaults to Claude Code's default)
- Settings → Actions → General → Workflow permissions → **Read and write**

### Step 4: Smoke tests (30 min, do these in order)
1. Actions → Trading Agent → Run workflow → `premarket`.
   Pass = dated entry in `memory/RESEARCH-LOG.md`, commit on main, Discord message.
2. During market hours (09:30–16:00 ET): manually run `market-open`.
   Pass = either gate-respecting buys **with trailing stops visible in the
   Alpaca dashboard immediately**, or a journaled no-trade decision.
3. Manually run `midday` and `daily-summary` the same day.
   Pass = journal entries, Equity History row appended, ≤15-line Discord summary.
4. Check the Actions log of each run for `GATE:` rejections — those are
   correct behavior, not bugs.

### Step 5: Paper validation (2+ weeks, passive)
Let the cron run. Read Discord daily; skim the journal every few days.
Checklist that must be fully green before live (also in SETUP.md §5):
- [ ] Every buy got a protective stop in the same run (ledger `stop=` notes)
- [ ] At least one server-side stop-out reconciled correctly next run
- [ ] Hard −7% exit fired when applicable
- [ ] Weekly cap / position cap / sector block rejections observed working
- [ ] A stop tightened on a ≥+15% winner; no stop ever widened
- [ ] No-trade days journaled with reasons
- [ ] Two Friday reviews with honest grades and ≥1 actionable lesson
- [ ] Zero silent failures (every red run produced a Discord alert)

### Step 6: Live cutover (only after Step 5 is fully green)
Swap secrets to live Alpaca keys, set `APCA_BASE_URL=https://api.alpaca.markets`,
watch the first day's open/midday runs in real time. Fund with an amount whose
total loss is acceptable; the system was tuned for $10k.

### Step 7 (later, optional): Moomoo port
Owner's real platform is Moomoo. Port = small VPS running the OpenD gateway
24/7, cron replaces Actions, engine.py broker calls swapped to OpenD's local
API. Gates/memory/routines carry over unchanged. Only worth doing after the
Alpaca version shows a stable, profitable track record.

## 6. Known limitations & watch items

- **Gap risk:** between runs, protection is the 10% trailing stop only; a gap
  through the stop fills at market. The −7% hard exit only evaluates at routine
  times. Accepted trade-off (owner chose server-side stops over hourly guards).
- **Actions cron lag:** 5–15 min delays are normal; routines tolerate it.
  A fully missed run self-heals at the next routine via `reconcile`.
- **engine.py `tighten` uses Alpaca order-replace (PATCH);** falls back to
  cancel+recreate. If Alpaca changes this API, tighten is the first thing to break.
- **Weekly buy counting and sector blocks derive from the ledger** — if anyone
  hand-edits ledger rows, gates may misfire. Don't.
- **LLM cost creep:** if runs get slow/expensive, set the `CLAUDE_MODEL` repo
  variable to a cheaper model for premarket/daily-summary first.
- **Hard gate changes** (the table in CLAUDE.md) must be made by a human PR
  editing `scripts/engine.py` constants — the agent is deny-listed from that path.

## 7. Where everything is documented

| Question | File |
|---|---|
| How the agent must behave each run | `CLAUDE.md` |
| Full setup / validation / cutover detail | `SETUP.md` |
| Strategy playbooks + regime rules | `memory/TRADING-STRATEGY.md` |
| Risk gate implementation | `scripts/engine.py` (constants at top) |
| Schedules and orchestration | `.github/workflows/trading.yml` |
| Agent sandbox (what it can/can't touch) | `.claude/settings.json` |
