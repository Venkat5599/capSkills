# For the judges — mapped to the Track 2 criteria

Track 2 (Strategy Skills) is scored on four criteria. Here's exactly how Pulse
addresses each, with links to proof.

---

## 1. Technical execution — _does it work, is it real?_

- ✅ A working **CoinMarketCap AI Agent Hub Skill** (`SKILL.md`) — installs in one
  line across 16 agent platforms (`npx skills add ...`).
- ✅ A real **velocity engine** + regime classifier + signal generator, all
  deterministic and reproducible. ([ARCHITECTURE.md](ARCHITECTURE.md))
- ✅ **Live** end-to-end: `cmc_live.py` pulls real CMC quotes + Fear & Greed and
  emits a signal right now.
- ✅ Validated on **2.5 years** of data with a full, reproducible backtest suite.

## 2. Originality — _a new take on a real problem?_

- ✅ Pulse measures **repricing velocity** — the second derivative — not price level.
  Fear & Greed measures the level; **nobody ships the speed.**
- ✅ CoinMarketCap's own skill library has **no strategy skill and nothing
  velocity-based.** Pulse fills the exact gap. ([METHODOLOGY.md](METHODOLOGY.md))
- ✅ The "crypto VIX as a regime switch" framing is novel and immediately graspable.

## 3. Real-world relevance — _clear user, path to adoption?_

- ✅ Every trader wants a panic gauge that fires **before** the dump, not after.
- ✅ **20/20 crash capture** over 2.5 years — it demonstrably flags the crashes.
  ([VALIDATION.md](VALIDATION.md))
- ✅ Ships as an installable Skill any agent can use today; a fundable "crypto fear
  index" product beyond the hackathon.

## 4. Demo & presentation — _is it clear?_

- ✅ **Live site:** https://pulse-vix.vercel.app — the market's heartbeat as a live
  EKG, the 20/20 stat, the honest fee disclosure.
- ✅ One-line install + one-question demo ("what's the crypto market regime?").
- ✅ This docs folder: methodology, architecture, validation, FAQ.

---

## The thing we're proudest of: honesty

We **disclose our own fee math.** The high-frequency version of the strategy loses
to transaction costs — and we keep the failing test in the repo
(`backtest/backtest.py`) rather than hide it. The value is the **regime signal**,
which is fee-immune, and which Track 2 explicitly invites ("entry/exit rules **or
market regime alerts**").

A submission that survives every hard question beats one that looks perfect until
you ask the first one. → [FAQ.md](FAQ.md)
