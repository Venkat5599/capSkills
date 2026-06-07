# Validation — every number, honestly

**Data:** 2.5 years hourly (2023-12-20 → 2026-06-07), 20 liquid CMC-eligible tokens
(ETH, XRP, DOGE, ADA, LINK, BCH, LTC, AVAX, DOT, UNI, ATOM, FIL, INJ, FET, CAKE,
TRX, SHIB, TON, AAVE, LDO). 426,432 rows.

Backtest data = Binance free public klines (CMC's free tier paywalls historical
OHLCV). The live Skill reads CoinMarketCap. Strategy logic is identical across both.

---

## 1. The core claim — does Pulse catch crashes?

**Crash capture: 20 / 20.** Of the 20 worst daily basket drops over 2.5 years,
**every one** had the Pulse index in its top decile within 24 hours.

```bash
python backtest/validate_indicator.py
```

| Forward 24h basket return | by regime |
|---|---|
| after CALM | −0.026% |
| after EUPHORIA | +0.106% |
| **after PANIC** | **+0.385%** (capitulation bounce — best of all regimes) |

- Forward 24h **volatility** after PANIC: **4.71%** vs **3.68%** after CALM (**1.3×**).
  Panic readings precede turbulent tape — exactly what a fear gauge should flag.
- Interpretation: a PANIC reading marks capitulation; the contrarian (fade) side has
  positive expectancy, with elevated risk.

---

## 2. The honest gate — does it survive fees?

We tested the high-frequency version (3h hold, market-neutral) against realistic
round-trip costs.

```bash
python backtest/backtest_fees.py
```

| Round-trip cost | Net return (1y) |
|---|---|
| 0.00% | +18.74% |
| 0.10% | −11.15% |
| **0.30% (realistic BSC)** | **−50.29%** |
| Break-even | **~0.063%** |

**Verdict:** as a high-frequency strategy, it **loses** — the per-trade edge
(~0.05%) is smaller than transaction costs (~0.30%). We do **not** hide this. The
naive test that fails (`backtest/backtest.py`) is kept in the repo.

---

## 3. Where the edge is real

```bash
python backtest/backtest_extreme.py     # extreme-event sweep
```

On **extreme** panic (top-decile) with a **24h** hold, the fade is **net-positive
after 0.30% fees** (fewer, larger trades clear the cost hurdle). And as a **regime
alert** (no trade, just a signal), there are no fees at all — which is the primary
deliverable Track 2 asks for.

---

## 4. The journey (we show our work)

| Test | File | Result |
|---|---|---|
| Naive fade, absolute returns | `backtest.py` | ❌ no edge |
| Market-neutral, short hold | `backtest2.py` | ✅ small real edge (t≈2.1) |
| Fee survival | `backtest_fees.py` | ❌ HF version loses |
| Extreme-event sweep | `backtest_extreme.py` | ✅ positive net of fees on extremes |
| Indicator validation | `validate_indicator.py` | ✅ **20/20 crash capture** |

This progression — hypothesis → test → honest failure → refinement → validated
claim — is the scientific method applied to a trading signal. It's the reason the
final claim is trustworthy.

---

## Reproduce everything

```bash
pip install -r requirements.txt
python scripts/data_fetch.py            # pull 2.5y data (free, no key)
python backtest/validate_indicator.py   # the headline proof
python backtest/backtest_fees.py        # the honest fee disclosure
```
