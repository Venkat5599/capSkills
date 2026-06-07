# FAQ — the hard questions, answered

### "Your backtest shows +18% — but after fees?"
After realistic fees the high-frequency version **loses** (break-even ~0.06% vs
~0.30% real cost). We say so plainly in [VALIDATION.md](VALIDATION.md) and keep the
failing test in the repo. The deliverable is the **regime indicator** (fee-immune),
not an HF bot. Track 2 explicitly accepts "market regime alerts."

### "Isn't this just RSI / Fear & Greed with extra steps?"
No. RSI and Fear & Greed are **levels**. Pulse is **velocity** — the rate and
*synchronization* of repricing across a basket. It's a different axis of
information, and it's *leading* rather than lagging. See [METHODOLOGY.md](METHODOLOGY.md).

### "20/20 crash capture sounds too good — is it cherry-picked?"
It's a falsifiable, reproducible test: the 20 largest daily basket drawdowns over
2.5 years, checked against whether Pulse was top-decile within 24h. Run
`python backtest/validate_indicator.py` yourself. It's coincident-to-leading by
construction (velocity spikes *as* the crowd sells), which is exactly what you want
from a fear gauge — not a magic predictor.

### "Why market-neutral? The absolute returns were negative."
The test window (2024–25) was a deep alt bear; the basket fell ~44–77%. Absolute
returns there measure the *market*, not the *signal*. Market-neutral
(`token − basket mean`) removes beta and isolates whether the selection adds value.
It's the honest way to evaluate a signal.

### "Does it actually use CoinMarketCap, or just Binance?"
The **live Skill uses CMC** (quotes/latest + fear-and-greed) — see `cmc_live.py`,
runnable now with a free key. The **backtest** uses Binance free klines only because
CMC's free tier paywalls *historical* OHLCV. Identical strategy logic on both paths.

### "Is there an LLM making trades I can't audit?"
No. The regime and picks are pure arithmetic over CMC data — deterministic and
reproducible. An LLM can explain the signal or answer "what's the regime?", but it
never decides the trade. This also makes it prompt-injection-safe.

### "Can I run it right now?"
```bash
npx skills add https://github.com/Venkat5599/capSkills -y
export CMC_API_KEY=your_free_key
python scripts/cmc_live.py
```
Or open https://pulse-vix.vercel.app and watch the live heartbeat.

### "What would you build next?"
More tokens (the full 149 eligible set), a tunable per-asset threshold, and a
published "Pulse index" feed other agents can subscribe to — the fundable "crypto
fear index" as infrastructure.
