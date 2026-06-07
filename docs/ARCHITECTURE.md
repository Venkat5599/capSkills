# Architecture

Pulse is deliberately small and deterministic. The math decides; the LLM only
orchestrates and explains. No model is in the trade-decision path.

## Data flow

```mermaid
flowchart TD
    subgraph CMC[CoinMarketCap AI Agent Hub]
        Q[quotes/latest<br/>percent_change_1h]
        FG[fear-and-greed/latest]
    end
    Q --> V[velocity.py<br/>speed = |move| / own vol]
    V --> P[Pulse index<br/>mean across basket]
    P --> R[regime.py<br/>CALM / PANIC / EUPHORIA]
    R --> S[signals.py<br/>fade / momentum / flat]
    FG --> C[sentiment.py<br/>conviction grade]
    S --> C
    C --> O[cmc_live.py<br/>signal JSON]
    O --> AGENT[Your agent / dashboard]
```

## Components

| File | Responsibility | Pure? |
|---|---|---|
| `scripts/velocity.py` | Pulse index from OHLCV | deterministic |
| `scripts/regime.py` | classify CALM/PANIC/EUPHORIA | deterministic |
| `scripts/signals.py` | regime → long basket + sizing | deterministic |
| `scripts/sentiment.py` | regime + CMC Fear&Greed → conviction | deterministic |
| `scripts/cmc_live.py` | live CMC fetch → signal JSON | I/O |
| `scripts/data_fetch.py` | historical OHLCV for backtest | I/O |
| `backtest/*` | validation, fees, crash-capture proof | deterministic |

## Design principles

1. **Math decides, not the LLM.** The regime and picks come from arithmetic over
   CMC data. An LLM can *explain* the signal or be asked "what's the regime?", but
   it never invents the trade. This keeps it reproducible and prompt-injection-safe.
2. **Deterministic + reproducible.** Same data in → same signal out. Every number in
   the README is regenerable from the scripts.
3. **Fail open.** Optional layers (Fear&Greed, social) degrade to neutral if
   unavailable; they never block the core signal.
4. **Two data paths, one logic.** Backtest reads Binance free klines; live reads
   CMC. The velocity/regime/signal code is shared — what you validate is what runs.

## Live signal output

```jsonc
{
  "source": "CoinMarketCap AI Agent Hub (quotes/latest + fear-and-greed)",
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

## The conviction layer

Combines two CMC-native signals so they cross-check each other:

| Regime | Fear & Greed | Conviction |
|---|---|---|
| PANIC | ≤ 25 (extreme fear) | **HIGH** — velocity & sentiment agree |
| EUPHORIA | ≥ 75 (extreme greed) | **HIGH** |
| PANIC/EUPHORIA | mild agreement | MEDIUM |
| disagreement / CALM | — | LOW (size down / wait) |
