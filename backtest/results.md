# Pulse — Results

Data: **2.5 years** hourly (2023-12 → 2026-06), 20 liquid CMC-eligible tokens.
Backtest data = Binance free klines; live Skill reads CoinMarketCap.

## Indicator validation (the core claim)

Pulse is a **velocity / capitulation gauge**. When the basket reprices fastest
and in sync, that burst is the crowd capitulating — historically a bounce follows.

**Crash capture: 20/20** of the worst daily drops had Pulse in its top
decile within 24h. The gauge catches the crashes.

| Forward 24h basket return | by regime |
|---|---|
| after CALM | -0.030% |
| after EUPHORIA | +0.103% |
| **after PANIC** | **+0.370%** (capitulation bounce) |

- Forward volatility after PANIC is **1.3x** the CALM level
  (4.71% vs 3.68%) — panic readings flag turbulent tape.
- Chart: `validation_results.png`.

## Strategy spec (derived from the gauge)

- **PANIC** -> contrarian: long the most oversold basket members (the overshoot bounces).
- **EUPHORIA** -> momentum: long the strongest (trend continues).
- **CALM** -> flat. Market-neutral, equal weight.

## Honest scope (read this)

- The signal's **gross** edge is **real but small per trade** (~0.05% market-neutral at 3h).
- At realistic round-trip cost (~0.30% on BSC), **no version we tested beats fees**:
  the HF rule loses (break-even <0.30%, `backtest_fees.py`), and the conviction-gated
  + directional versions are negative in-sample *and* out-of-sample across a full
  parameter sweep (`strategy_gated.py`). The only "positive" cells in the extreme
  sweep (`backtest_extreme.py`) are tiny-sample (n~17) cherry-picks — we don't claim them.
- The real, robust value is the **regime / capitulation alert** — fee-immune, and
  exactly what Track 2 asks for ("entry/exit rules OR market regime alerts").
- This is a **validated indicator + backtestable strategy spec**, not a profitable HFT bot.

## Fees-aware results (round-trip cost per position)

| fee% rt | net return | Sharpe | maxDD | win% |
|---|---|---|---|---|
| 0.00% | +56.42% | 4.83 | -12.41% | 51.0% |
| 0.10% | -23.70% | -2.61 | -33.81% | 42.6% |
| 0.20% | -62.81% | -10.06 | -63.26% | 34.8% |
| 0.30% | -81.89% | -17.51 | -82.05% | 28.8% |
| 0.40% | -91.18% | -24.95 | -91.25% | 22.7% |
| 0.50% | -95.71% | -32.40 | -95.74% | 17.5% |

**Break-even round-trip cost: 0.070%** (typical BSC liquid ~0.30%).

## The conviction-gated stress test (why Pulse is an alert, not post-fee alpha)

We tested hard for a fee-surviving trade: the disciplined version — enter only the deep-panic tail (Pulse > 97% pct), hold 24h, market-neutral, non-overlapping. The gross edge is **real** but it is **smaller than a realistic 0.30% BSC round-trip cost**, so the net is negative. We publish the failing PnL openly — the honest takeaway is that Pulse's value is the **fee-immune regime/capitulation alert**, exactly what Track 2 allows ("entry/exit rules OR market regime alerts").

| metric | value |
|---|---|
| trades (2.5y) | 233 (~93/yr) |
| gross return | +40.42% (the edge is real) |
| net return @ 0.30% rt | -30.21% (cost eats it) |
| avg / trade (net) | -14.1 bps |
| max drawdown | -45.02% |
| win rate | 35.2% |
| **break-even cost** | **0.146%** — *below* the ~0.30% you actually pay |

**Out-of-sample (fixed rules, no refit):** in-sample net -24.46%, out-of-sample net -7.61% — negative in both halves. Not a curve-fit that broke; the edge is simply thinner than the toll.

**Parameter sweep** (net of 0.30%) — negative across every setting, so this isn't one unlucky point either:

| gate_q | hold (h) | net % | Sharpe | maxDD % | win % |
|---|---|---|---|---|---|
| 0.95 | 12 | -63.93% | -6.38 | -63.14% | 36.4% |
| 0.95 | 24 | -60.38% | -3.64 | -61.41% | 35.3% |
| 0.95 | 48 | -34.81% | -1.01 | -50.41% | 38.7% |
| 0.97 | 12 | -42.24% | -4.26 | -47.61% | 36.8% |
| 0.97 | 24 | -30.21% | -1.67 | -45.02% | 35.2% |
| 0.97 | 48 | -17.79% | -0.46 | -46.73% | 40.6% |
| 0.99 | 12 | -16.09% | -2.52 | -27.46% | 38.5% |
| 0.99 | 24 | -17.19% | -1.74 | -27.08% | 37.2% |
| 0.99 | 48 | -24.38% | -1.63 | -27.62% | 38.7% |
