"""
Pulse — extreme-signal sweep (fee-survival search).

The 3h/top-10% strategy's per-trade edge (~0.05%) < fees (~0.30%) -> dies.
Fix hypothesis: act ONLY on extreme velocity events (higher percentile) and
hold LONGER. Bigger per-trade moves can clear the fee hurdle even with far
fewer trades.

Sweep: panic percentile threshold x hold horizon. Report per-trade edge,
net-of-0.30%-fee return, and trade count. Find a fee-surviving config (or
conclude Pulse is best as a regime indicator, not an HFT strategy).
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from velocity import load_panel  # noqa: E402

FEE = 0.30 / 100        # round-trip per position
K = 3                   # tighter basket on extreme events
PCTS = [0.90, 0.95, 0.98, 0.99]
HOLDS = [3, 6, 12, 24, 48]
MIN_TRADES = 30         # below this, a "positive" cell is a cherry-pick, not an edge


def main() -> None:
    raw = load_panel()
    # build velocity panel once
    raw = raw.sort_values(["symbol", "time"]).copy()
    raw["logret"] = raw.groupby("symbol")["close"].transform(lambda s: np.log(s / s.shift(1)))
    raw["vol"] = raw.groupby("symbol")["logret"].transform(
        lambda s: s.rolling(168, min_periods=84).std())
    raw["speed"] = (raw["logret"].abs() / raw["vol"]).replace([np.inf, -np.inf], np.nan)
    agg = raw.groupby("time").agg(pulse=("speed", "mean"),
                                  direction=("logret", "mean")).dropna()

    print("=" * 72)
    print("PULSE — EXTREME-SIGNAL SWEEP (net of 0.30% round-trip fee)")
    print("=" * 72)
    print(f"{'pct':>5} {'hold':>5} {'trades':>7} {'edge/trade':>11} "
          f"{'net/trade':>10} {'netRet':>9} {'win%':>6}")
    print("-" * 72)

    best = None
    for pct in PCTS:
        thr = agg["pulse"].quantile(pct)
        panic_times = agg[(agg["pulse"] > thr) & (agg["direction"] < 0)].index
        for h in HOLDS:
            p = raw.copy()
            p["fwd"] = p.groupby("symbol")["close"].transform(lambda s: s.shift(-h) / s - 1)
            p["lastret"] = p.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1)
            p["mkt_fwd"] = p.groupby("time")["fwd"].transform("mean")
            p["rel_fwd"] = p["fwd"] - p["mkt_fwd"]
            sub = p[p["time"].isin(panic_times)]
            # fade: K most oversold per panic timestamp
            picks = (sub.sort_values(["time", "lastret"]).groupby("time").head(K))
            # one return per timestamp (avg of the K), non-overlapping by hold
            per_ts = picks.groupby("time")["rel_fwd"].mean().dropna().sort_index()
            per_ts = per_ts.iloc[::max(1, h // 3)]   # crude non-overlap
            if len(per_ts) < 5:
                continue
            edge = per_ts.mean()
            net = per_ts - FEE
            net_ret = ((1 + net).prod() - 1) * 100
            win = (net > 0).mean() * 100
            print(f"{pct:>5.2f} {h:>5} {len(per_ts):>7} {edge*100:>+10.3f}% "
                  f"{net.mean()*100:>+9.3f}% {net_ret:>+8.2f}% {win:>5.1f}")
            # Only count a config as "fee-surviving" if it has a credible sample
            # size. A positive cell with a dozen trades out of a 20-config sweep is
            # a cherry-pick, not an edge — we refuse to claim it.
            if net.mean() > 0 and len(per_ts) >= MIN_TRADES and (best is None or net_ret > best[-1]):
                best = (pct, h, len(per_ts), edge, net_ret)

    print("-" * 72)
    if best:
        print(f">> Best cell (n>={MIN_TRADES}): pct={best[0]} hold={best[1]}h "
              f"trades={best[2]} netRet={best[4]:+.2f}% (~{best[4]/2.5:.1f}%/yr) — MARGINAL.")
        print(">> NOT robust: this is the best of a 20-config sweep, and it flips negative")
        print(">>   under proper non-overlap, K=5, and out-of-sample (strategy_gated.py).")
    else:
        print(f">> No credible-sample (n>={MIN_TRADES}) config beats the 0.30% fee.")
    print(">> Honest verdict either way: the gross edge is real but does NOT robustly")
    print(">> survive 0.30% BSC cost. Pulse = REGIME / CAPITULATION ALERT (fee-immune),")
    print(">> not an HFT strategy. Track 2 explicitly allows regime alerts.")
    print("=" * 72)


if __name__ == "__main__":
    main()
