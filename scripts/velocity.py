"""
Pulse — the velocity / panic index.

Idea: don't measure price level (Fear & Greed already does). Measure the *speed*
and *synchronization* of repricing across the whole basket. A burst where many
tokens move abnormally hard at once = panic. Panic overshoots -> reverts.

Builds a tidy panel from the OHLCV parquet and computes:
  v_i(t)  = |log return_i| / rolling_std_i      (z-scored move size per token)
  P(t)    = mean_i v_i(t)                        (the Pulse index = "crypto VIX")
  m(t)    = mean_i log_return_i                  (cluster direction)
  regime  = CALM / PANIC / EUPHORIA
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
VOL_WINDOW = 168            # 1 week of hourly bars for the rolling vol baseline
PANIC_Q = 0.90              # P above its 90th percentile = high-velocity regime


def load_panel() -> pd.DataFrame:
    pq = DATA / "ohlcv_hourly.parquet"
    csv = DATA / "ohlcv_hourly.csv"
    if pq.exists():
        df = pd.read_parquet(pq)
    elif csv.exists():
        df = pd.read_csv(csv, parse_dates=["time"])
    else:
        raise FileNotFoundError("Run data_fetch.py first (no OHLCV found).")
    return df.sort_values(["symbol", "time"]).reset_index(drop=True)


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Return a per-(time) frame with the Pulse index, direction, and regime."""
    df = df.copy()
    df["logret"] = (
        df.groupby("symbol")["close"].transform(lambda s: np.log(s / s.shift(1)))
    )
    # rolling vol baseline per token
    df["vol"] = df.groupby("symbol")["logret"].transform(
        lambda s: s.rolling(VOL_WINDOW, min_periods=VOL_WINDOW // 2).std()
    )
    df["speed"] = (df["logret"].abs() / df["vol"]).replace([np.inf, -np.inf], np.nan)

    # aggregate across the basket per timestamp
    agg = df.groupby("time").agg(
        pulse=("speed", "mean"),
        direction=("logret", "mean"),
        n=("speed", "count"),
    ).dropna()

    # regime classification
    thresh = agg["pulse"].quantile(PANIC_Q)
    agg["high_velocity"] = agg["pulse"] > thresh
    agg["regime"] = np.where(
        ~agg["high_velocity"], "CALM",
        np.where(agg["direction"] < 0, "PANIC", "EUPHORIA"),
    )
    agg.attrs["panic_threshold"] = float(thresh)
    return agg


def main() -> None:
    panel = load_panel()
    agg = compute(panel)
    print(f"Bars: {len(agg)}  ({agg.index.min()} -> {agg.index.max()})")
    print(f"Panic threshold (P @ {PANIC_Q:.0%}): {agg.attrs['panic_threshold']:.3f}")
    print("\nRegime counts:")
    print(agg["regime"].value_counts())
    print("\nTop 5 panic bars (highest Pulse):")
    print(agg.sort_values("pulse", ascending=False).head())


if __name__ == "__main__":
    main()
