"""
Pulse — regime classifier.

Turns the velocity index into a market regime label per timestamp:
  CALM     : Pulse below the high-velocity threshold -> stand aside
  PANIC    : high velocity + cluster falling   -> fade the overshoot (mean-revert)
  EUPHORIA : high velocity + cluster rising     -> ride momentum (trend-follow)

Validated on 1y hourly data (20 eligible tokens): market-neutral, 3h hold,
PANIC->fade win 53% (t~2.1), EUPHORIA->momentum positive (t~1.7). See backtest/.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def classify(pulse: float, direction: float, threshold: float) -> str:
    """Single-bar regime label."""
    if pulse <= threshold:
        return "CALM"
    return "PANIC" if direction < 0 else "EUPHORIA"


def classify_frame(agg: pd.DataFrame, panic_quantile: float = 0.90) -> pd.DataFrame:
    """Vectorized regime labels for a frame with columns ['pulse','direction']."""
    out = agg.copy()
    threshold = out["pulse"].quantile(panic_quantile)
    high = out["pulse"] > threshold
    out["regime"] = np.where(
        ~high, "CALM",
        np.where(out["direction"] < 0, "PANIC", "EUPHORIA"),
    )
    out.attrs["panic_threshold"] = float(threshold)
    return out
