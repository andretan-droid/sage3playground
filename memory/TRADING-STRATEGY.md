# Trading Strategy

Baseline capital: $10,000 paper account. Long-only US equity swing trading.

## Hard risk gates

> These are enforced by `scripts/engine.py`. This table is documentation —
> editing it does NOT change enforcement. Parameter changes require a
> human-reviewed PR against the engine.

| Parameter | Value |
|---|---|
| Eligible assets | US common stocks/ETFs, listed exchanges only (no OTC) |
| Prohibited | Options, shorting, leverage, crypto, fractional shares |
| Max open positions | 6 |
| Max position size | 20% of equity, also capped by available cash |
| Max new trades per week | 3 (Mon–Fri, ET) |
| Entry stop | 10% GTC trailing stop immediately on fill |
| PDT fallback ladder | trailing stop → static −7% stop → queued for next open |
| Hard exit | −7% from entry, checked every routine |
| Stop ladder | trail 7% at ≥ +15% peak gain; trail 5% at ≥ +20% |
| Stop constraints | tighten-only, never within 3% of spot |
| Sector block | 2 consecutive realized losses → no new entries until review |

## Playbooks

Pick exactly one playbook per trade and name it in the buy command and journal.
If no setup meets its playbook's bar, the correct trade count for the day is zero.

### 1. `momentum` — Momentum swing (default)

- **Entry**: stock in an established uptrend (price above rising 20d and 50d
  SMA), showing relative strength vs SPY, with a concrete catalyst (earnings
  momentum, guidance raise, sector tailwind). Prefer entries on strength
  confirmation, not on extended gaps (avoid chasing >5% gap-ups at the open).
- **Hold**: days to weeks; let the trailing-stop ladder do the exiting.
- **Avoid**: earnings announcements within the next 3 trading days unless that
  is explicitly the thesis.

### 2. `news-sentiment` — Catalyst/news driven

- **Entry**: confirmed, dated catalyst (earnings beat + raise, FDA decision,
  major contract, product launch with strong reception). Enter on confirmation,
  never on rumor. Sentiment from research must be corroborated by at least two
  independent sources.
- **Hold**: shorter — days. Reassess at every routine whether the catalyst is
  still driving price; exit when the news is absorbed even if above stops.
- **Avoid**: low-float small caps and anything that looks like a pump.

### 3. `mean-reversion` — Quality pullback

- **Entry**: quality large/mid-cap in a longer-term uptrend pulling back to the
  20d/50d SMA on no thesis-breaking news; oversold short-term (e.g. RSI < 40).
- **Hold**: until reversion toward the recent range mid/high; this playbook
  takes profits proactively rather than trailing for a big run.
- **Avoid**: knife-catching — the pullback must hold above the 50d SMA region,
  and the cause must be market noise, not deteriorating fundamentals.

## Regime guidance

- Broad uptrend, low volatility → favor `momentum`.
- Choppy/range-bound tape → favor `mean-reversion`, smaller and fewer trades.
- Heavy news week (Fed, CPI, mega-cap earnings) → favor `news-sentiment` after
  the event, and avoid initiating the day before a major macro print.
- VIX > 30 or market in sharp drawdown → capital preservation: no new entries
  unless an exceptional setup; respect stops without hesitation.
- Keep a cash buffer: target ≥ 10% of equity uninvested in normal conditions.

## Qualitative discipline

- The thesis must be falsifiable: every journal entry states what would prove
  it wrong. If that happens, exit — don't wait for the stop.
- Never average down. Never widen a stop. Never "give it one more day" below
  the hard exit.
- Spread check before entry: skip if the bid/ask spread exceeds 0.5% of price.
- These qualitative sections MAY be refined by the weekly review based on
  journaled evidence. Hard gates above may not.

## Change log

| Date | Change | Reason |
|---|---|---|
| (init) | Initial strategy document | System launch |
