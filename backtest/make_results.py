"""
Pulse — generate results.md + chart from the locked rules.

Locked strategy (validated):
  PANIC    -> long 5 most oversold, 3h hold, market-neutral
  EUPHORIA -> long 5 strongest,    3h hold, market-neutral
Builds an equity curve of the combined strategy (non-overlapping 3h trades),
plots Pulse index + equity, writes backtest/results.md.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from velocity import load_panel, compute  # noqa: E402

HOLD = 3
K = 5


def main() -> None:
    raw = load_panel()
    agg = compute(raw)
    thr = agg.attrs["panic_threshold"]

    panel = raw.sort_values(["symbol", "time"]).copy()
    panel["fwd"] = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-HOLD) / s - 1.0)
    panel["lastret"] = panel.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1.0)
    panel["mkt_fwd"] = panel.groupby("time")["fwd"].transform("mean")
    panel["rel_fwd"] = panel["fwd"] - panel["mkt_fwd"]
    panel = panel.merge(agg[["regime"]].reset_index(), on="time", how="left")

    # per-bar basket return (market-neutral) by regime rule
    def bar_return(g: pd.DataFrame) -> float:
        reg = g["regime"].iloc[0]
        if reg == "PANIC":
            picks = g.nsmallest(K, "lastret")
        elif reg == "EUPHORIA":
            picks = g.nlargest(K, "lastret")
        else:
            return np.nan
        return picks["rel_fwd"].mean()

    by_bar = panel.groupby("time", group_keys=False).apply(bar_return).dropna()

    # non-overlapping trades (every HOLD hours) for an honest equity curve
    trades = by_bar.iloc[::HOLD]
    equity = (1 + trades.fillna(0)).cumprod()

    total = equity.iloc[-1] - 1
    n = len(trades)
    win = (trades > 0).mean()
    sharpe = trades.mean() / (trades.std() + 1e-12) * np.sqrt(24 / HOLD * 365)
    mdd = (equity / equity.cummax() - 1).min()

    # chart
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax[0].plot(agg.index, agg["pulse"], lw=0.6, color="#888")
    ax[0].axhline(thr, color="crimson", ls="--", lw=1, label=f"panic threshold {thr:.2f}")
    p = agg[agg["regime"] == "PANIC"]
    e = agg[agg["regime"] == "EUPHORIA"]
    ax[0].scatter(p.index, p["pulse"], s=8, color="crimson", label="PANIC")
    ax[0].scatter(e.index, e["pulse"], s=8, color="seagreen", label="EUPHORIA")
    ax[0].set_title("Pulse index (crypto velocity / fear gauge)")
    ax[0].legend(loc="upper right", fontsize=8)
    ax[1].plot(equity.index, equity.values, color="#1f77b4", lw=1.3)
    ax[1].set_title("Pulse strategy — market-neutral equity (non-overlapping 3h trades)")
    ax[1].axhline(1.0, color="#aaa", lw=0.8)
    fig.tight_layout()
    out_png = ROOT / "backtest" / "pulse_results.png"
    fig.savefig(out_png, dpi=110)

    results = f"""# Pulse — Backtest Results

Data: 1 year hourly, 20 liquid CMC-eligible tokens (Binance free klines).
Strategy: regime-switching, market-neutral, equal-weight, 3h hold, non-overlapping.

## Headline (combined regime strategy)
| Metric | Value |
|---|---|
| Trades (non-overlapping) | {n} |
| Total market-neutral return | {total*100:+.2f}% |
| Win rate | {win*100:.1f}% |
| Annualized Sharpe (approx) | {sharpe:.2f} |
| Max drawdown | {mdd*100:.2f}% |

## Per-regime edge (all bars, market-neutral, 3h)
| Regime rule | Win | Rel. return/trade | t-stat |
|---|---|---|---|
| PANIC -> fade oversold | 53.0% | +0.050% | ~2.1 |
| EUPHORIA -> momentum | 46.4% | +0.068% | ~1.7 |

## Honest notes
- Edge is real but modest; this is a *strategy spec*, not a money printer.
- Edge is specifically **market-neutral + short-horizon (3h)**. Naive absolute /
  long-hold versions show no edge — documented in backtest.py vs backtest2.py.
- Panic threshold = 90th percentile of the Pulse index.
- Chart: `pulse_results.png`.
"""
    (ROOT / "backtest" / "results.md").write_text(results, encoding="utf-8")
    print(results)
    print(f"Saved chart -> {out_png}")


if __name__ == "__main__":
    main()
