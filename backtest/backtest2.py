"""
Pulse — edge test v2 (market-neutral + short holds + momentum side).

Fixes v1's flaws:
  - whole basket drifted down -> measure RELATIVE return: token_fwd - basket_mean_fwd
    (cross-sectional / market-neutral; removes the beta so we isolate the signal)
  - bounce is fast -> test short holds [1,2,3,4,6]
  - never tested the trend side -> test EUPHORIA momentum continuation

Strategies (all market-neutral, equal-weight, no lookahead):
  FADE   : in PANIC bars, long the K most-oversold (most negative last-bar ret) tokens
  MOM    : in EUPHORIA bars, long the K strongest (most positive last-bar ret) tokens
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from velocity import load_panel, compute  # noqa: E402

HOLDS = [1, 2, 3, 4, 6, 12]
K = 5


def build(panel: pd.DataFrame, h: int) -> pd.DataFrame:
    panel = panel.sort_values(["symbol", "time"]).copy()
    panel["fwd"] = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-h) / s - 1.0)
    panel["lastret"] = panel.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1.0)
    # market-neutral forward return = token fwd minus cross-sectional mean at that time
    panel["mkt_fwd"] = panel.groupby("time")["fwd"].transform("mean")
    panel["rel_fwd"] = panel["fwd"] - panel["mkt_fwd"]
    return panel


def stat(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) == 0:
        return "n=0"
    mean = x.mean()
    sharpe = mean / (x.std() + 1e-12) * np.sqrt(len(x))  # crude t-stat-ish
    return f"n={len(x):5d}  rel_mean={mean*100:+6.3f}%  win={(x>0).mean()*100:5.1f}%  t~={sharpe:5.1f}"


def main() -> None:
    raw = load_panel()
    agg = compute(raw)
    regime = agg[["regime"]].reset_index()

    print("=" * 70)
    print("PULSE EDGE TEST v2  (market-neutral)")
    print("=" * 70)

    best = (None, -1e9)
    for h in HOLDS:
        panel = build(raw, h).merge(regime, on="time", how="left")
        panic = panel[panel["regime"] == "PANIC"]
        euph = panel[panel["regime"] == "EUPHORIA"]

        fade = (panic.sort_values(["time", "lastret"]).groupby("time").head(K)["rel_fwd"])
        mom = (euph.sort_values(["time", "lastret"], ascending=[True, False])
               .groupby("time").head(K)["rel_fwd"])

        print(f"--- hold {h}h ".ljust(70, "-"))
        print(f"  FADE oversold in PANIC   : {stat(fade)}")
        print(f"  MOM strongest in EUPHORIA: {stat(mom)}")
        for name, s in [("FADE", fade), ("MOM", mom)]:
            m = s.dropna().mean()
            if m > best[1]:
                best = (f"{name} hold {h}h", m)
        print()

    print("=" * 70)
    print(f"BEST: {best[0]}  rel_mean={best[1]*100:+.3f}% per trade")
    if best[1] > 0.001:
        print(">> GREEN: market-neutral edge found. Build the skill around this.")
    else:
        print(">> still weak. Next: use Pulse as a FILTER for momentum, not standalone.")
    print("=" * 70)


if __name__ == "__main__":
    main()
