---
name: pulse-velocity-regime
description: >
  Pulse turns CoinMarketCap data into a regime-switching crypto trading strategy
  based on market VELOCITY (the speed and synchronization of repricing) rather
  than price level. Computes a "Pulse index" (a crypto VIX), classifies the
  market into CALM / PANIC / EUPHORIA, and emits market-neutral entry/exit rules:
  fade the overshoot in panic, ride momentum in euphoria, stand aside when calm.
license: MIT
metadata:
  track: "BNB Hack — Track 2: Strategy Skills"
  data_source: CoinMarketCap AI Agent Hub
  type: backtestable-strategy-spec
---

# Pulse — the Velocity Regime Skill

> **Fear & Greed tells you the crowd's *mood*. Pulse tells you the crowd's *speed*.**
> Mood is lagging. Speed is leading. Pulse measures how fast and how synchronized
> the whole market reprices at once — the second derivative — and trades the regime.

## What this Skill does

Given live CoinMarketCap data for a basket of tokens, this Skill:
1. Computes the **Pulse index** — average z-scored move size across the basket.
2. Classifies the **regime**: CALM / PANIC / EUPHORIA.
3. Emits a **market-neutral strategy**: which tokens to long, hold time, stop/TP.

It is a **strategy spec**, not a live-execution agent — no wallet, no signing.

## When to use it

Trigger when the user asks any of:
- "What's the market regime right now?"
- "Is the market panicking / is this a dip to fade?"
- "Give me a crypto trading signal based on volatility / velocity."
- "Run the Pulse strategy on <basket>."

## CoinMarketCap data inputs (AI Agent Hub)

Use these CMC endpoints / MCP tools:
- **Latest quotes / OHLCV** — `cryptocurrency/quotes/latest` (and `ohlcv/historical`
  on Hobbyist+ tiers) for recent hourly closes per token. Needed for returns + velocity.
- **Fear & Greed** — `fear-and-greed/latest` — used as a confirming context flag
  (extreme fear strengthens a PANIC fade; extreme greed strengthens EUPHORIA momentum).
- **Derivatives / funding** (optional) — to corroborate regime (crowded longs in euphoria).
- **Trending** (optional) — narrative tilt.

Default basket = liquid CMC-listed tokens (e.g. ETH, XRP, DOGE, ADA, LINK, BCH,
LTC, AVAX, DOT, UNI, ATOM, FIL, INJ, FET, CAKE, TRX, SHIB, TON, AAVE, LDO).

## Algorithm (deterministic core — the LLM orchestrates, math decides)

For each token i over the last ~200 hourly bars:
```
logret_i(t) = ln(close_i(t) / close_i(t-1))
vol_i       = rolling_std(logret_i, window=168)         # 1-week baseline
speed_i(t)  = |logret_i(t)| / vol_i                      # z-scored move size
```
Across the basket at time t:
```
Pulse(t)     = mean_i speed_i(t)                         # the crypto VIX
direction(t) = mean_i logret_i(t)                        # cluster drift
threshold    = 90th percentile of Pulse over the window
regime(t) = CALM      if Pulse(t) <= threshold
            PANIC     if Pulse(t) >  threshold and direction(t) < 0
            EUPHORIA  if Pulse(t) >  threshold and direction(t) >= 0
```
Signal:
```
CALM     -> FLAT (no positions)
PANIC    -> long the 5 most OVERSOLD tokens (most negative last-bar return)
EUPHORIA -> long the 5 STRONGEST tokens (most positive last-bar return)
sizing   -> equal weight, market-neutral; hold 3h; stop -5%; take-profit +6%
```

## Output format

Return JSON the agent can act on or display:
```json
{
  "pulse_index": 1.84,
  "regime": "PANIC",
  "action": "FADE_LONG",
  "picks": ["INJ", "FET", "LDO", "AAVE", "DOT"],
  "fear_greed": 18,
  "hold_hours": 3,
  "stop_loss": -0.05,
  "take_profit": 0.06,
  "sizing": "equal-weight, market-neutral",
  "conviction": {
    "grade": "HIGH",
    "reason": "velocity panic + extreme fear agree (capitulation)",
    "fear_greed": 18,
    "fg_label": "extreme fear"
  }
}
```
Then explain in plain language: the regime, the conviction, and the rationale.

### Conviction layer
The signal is graded by combining the velocity **regime** with CMC's **Fear & Greed**:
PANIC + extreme fear (≤25) or EUPHORIA + extreme greed (≥75) = HIGH conviction
(price and crowd agree). Disagreement = LOW (size down / wait). Both inputs are
CMC-native.

### Optional live bonus — X / social corroboration
For a richer live read, an agent with the **agent-reach** skill can also search
X/Twitter ("search crypto panic/fear on twitter") to corroborate the regime.
Shown in the demo; not hard-wired (free social scrapers are rate-limited).

## How to run

**Live signal (primary — what to run when asked for the regime/signal):**
```bash
export CMC_API_KEY=<your CoinMarketCap key>   # free Basic tier works
python scripts/cmc_live.py                    # -> JSON: regime, action, picks, fear_greed
```
`cmc_live.py` pulls live CoinMarketCap quotes + Fear & Greed, computes the Pulse
index, classifies the regime, and emits the market-neutral signal. This is the
deliverable a judge runs.

**Validation / backtest (reproduce the proof):**
```bash
python scripts/data_fetch.py        # pull history (free Binance klines, no key)
python backtest/validate_indicator.py   # 20/20 crash capture, regime fwd returns
python backtest/backtest_fees.py    # honest fee-survival disclosure
```
Backtest uses Binance free klines (CMC free tier paywalls historical OHLCV);
live path uses CMC. Identical strategy logic across both.

## Validation (2.5y hourly, 20 tokens — see backtest/results.md)

Pulse is validated as a **capitulation / fear gauge**:
- **Crash capture: 20/20** — every one of the worst daily drops had Pulse in its
  top decile within 24h.
- **Forward 24h after PANIC: +0.385%** (capitulation bounce — best of all regimes)
  vs −0.026% after CALM. Panic = contrarian buy.
- Forward volatility after PANIC is **1.3×** the calm level — flags turbulent tape.

**Honest fee disclosure:** the per-trade signal is small (~0.05% at 3h). At realistic
BSC round-trip cost (~0.30%) the high-frequency version loses (break-even ~0.06%,
`backtest_fees.py`). The value is the **regime alert** — fee-immune, and exactly what
Track 2 asks for. We keep the failed naive test (`backtest.py`) in the repo.

## Why it's novel

CoinMarketCap's own skill library has data + report + research skills but **no
strategy/backtest skill, and nothing measuring repricing *velocity*.** Pulse is a
new primitive: a leading "crypto VIX" that drives a regime-switching strategy.
