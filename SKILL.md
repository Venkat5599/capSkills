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
  "timestamp": "...",
  "pulse_index": 1.84,
  "panic_threshold": 1.33,
  "regime": "PANIC",
  "fear_greed": 18,
  "action": "FADE_LONG",
  "picks": ["INJ", "FET", "LDO", "AAVE", "DOT"],
  "hold_hours": 3,
  "stop_loss": -0.05,
  "take_profit": 0.06,
  "sizing": "equal-weight, market-neutral",
  "note": "High velocity + falling cluster: fade the overshoot."
}
```
Then explain in plain language: the regime, why, and the trade rationale.

## How to run (reference implementation)

```bash
python scripts/velocity.py      # Pulse index + regime over history
python scripts/signals.py       # current signal from a regime + last returns
python backtest/backtest2.py    # market-neutral edge validation
```
The reference scripts read OHLCV (Binance free klines for backtest; swap in CMC
quotes for live). The strategy logic is identical across data sources.

## Validation (see backtest/results.md)

Backtested on 1 year of hourly data, 20 liquid eligible tokens, market-neutral:
- **PANIC -> fade oversold, 3h hold: win 53.0%, +0.050%/trade, t~2.1** (real edge)
- **EUPHORIA -> momentum, 3h hold: +0.068%/trade** (positive)
- Naive (non-market-neutral, long holds) shows no edge — the edge is specifically
  market-neutral + short-horizon. Honesty: edge is modest but statistically present.

## Why it's novel

CoinMarketCap's own skill library has data + report + research skills but **no
strategy/backtest skill, and nothing measuring repricing *velocity*.** Pulse is a
new primitive: a leading "crypto VIX" that drives a regime-switching strategy.
