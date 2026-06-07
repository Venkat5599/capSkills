"""
Pulse — edge test (make-or-break).

Question: after a PANIC bar (high cluster velocity + negative direction),
does FADING it (buying) earn an abnormal forward return vs baseline?

Method (no lookahead):
  - regime computed per timestamp from velocity.py
  - on each bar, forward return over H hours per token = close[t+H]/close[t] - 1
  - entry assumed at the bar AFTER the signal in practice; here we measure the
    forward return starting at signal close as the screening test
  - compare mean forward return + win rate: PANIC vs CALM vs ALL (baseline)
  - "fade oversold": within PANIC bars, buy the K tokens with the most negative
    last-bar return (the overshoot), measure their forward return

Prints a verdict. Green = edge exists -> build full skill. Weak = pivot.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from velocity import load_panel, compute  # noqa: E402

HOLDS = [6, 12, 24, 48]      # hours to hold
K_OVERSOLD = 5               # how many most-oversold tokens to fade per panic bar


def with_forward_returns(panel: pd.DataFrame, h: int) -> pd.DataFrame:
    panel = panel.sort_values(["symbol", "time"]).copy()
    panel["fwd"] = panel.groupby("symbol")["close"].transform(
        lambda s: s.shift(-h) / s - 1.0
    )
    panel["lastret"] = panel.groupby("symbol")["close"].transform(
        lambda s: s / s.shift(1) - 1.0
    )
    return panel


def summarize(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) == 0:
        return "n=0"
    return (f"n={len(x):5d}  mean={x.mean()*100:+6.3f}%  "
            f"win={ (x>0).mean()*100:5.1f}%  median={x.median()*100:+6.3f}%")


def main() -> None:
    raw = load_panel()
    agg = compute(raw)                      # per-time regime
    regime = agg[["regime", "pulse", "direction"]].reset_index()

    print("=" * 64)
    print("PULSE EDGE TEST")
    print("=" * 64)
    print(f"Panic threshold: {agg.attrs['panic_threshold']:.3f}")
    print(regime["regime"].value_counts().to_string())
    print()

    verdict_rows = []
    for h in HOLDS:
        panel = with_forward_returns(raw, h)
        merged = panel.merge(regime, on="time", how="left")

        baseline = merged["fwd"]
        panic = merged.loc[merged["regime"] == "PANIC", "fwd"]
        calm = merged.loc[merged["regime"] == "CALM", "fwd"]

        # fade oversold: within PANIC, take K most negative last-bar returns per timestamp
        panic_bars = merged[merged["regime"] == "PANIC"].copy()
        fade = (
            panic_bars.sort_values(["time", "lastret"])
            .groupby("time")
            .head(K_OVERSOLD)["fwd"]
        )

        print(f"--- Hold {h}h ".ljust(64, "-"))
        print(f"  BASELINE (all bars) : {summarize(baseline)}")
        print(f"  CALM                : {summarize(calm)}")
        print(f"  PANIC (buy cluster) : {summarize(panic)}")
        print(f"  PANIC fade oversold : {summarize(fade)}")
        edge = panic.dropna().mean() - baseline.dropna().mean()
        fade_edge = fade.dropna().mean() - baseline.dropna().mean()
        print(f"  edge(PANIC-base)={edge*100:+.3f}%   "
              f"edge(FADE-base)={fade_edge*100:+.3f}%")
        print()
        verdict_rows.append((h, edge, fade_edge,
                             fade.dropna().mean(), (fade > 0).mean()))

    print("=" * 64)
    print("VERDICT")
    best = max(verdict_rows, key=lambda r: r[2])  # best fade edge
    h, edge, fade_edge, fade_mean, fade_win = best
    print(f"Best fade: hold {h}h | fade mean {fade_mean*100:+.3f}% | "
          f"win {fade_win*100:.1f}% | edge vs baseline {fade_edge*100:+.3f}%")
    if fade_edge > 0.003 and fade_mean > 0:
        print(">> GREEN: fade-the-panic shows edge. Build the full skill.")
    elif edge > 0.003:
        print(">> AMBER: cluster bounce shows edge; refine the fade selection.")
    else:
        print(">> RED: weak edge. Pivot to regime-gated momentum, keep the index story.")
    print("=" * 64)


if __name__ == "__main__":
    main()
