"""
Pulse — historical OHLCV fetch (free, no API key).

Pulls hourly klines from Binance public API for a basket of the hackathon's
eligible tokens. CMC's free tier paywalls historical OHLCV, so we validate the
edge on equivalent free data. The live Skill reads CMC; the backtest reads this.

Output: pulse/data/ohlcv_hourly.parquet  (and a CSV fallback)
"""
from __future__ import annotations
import time
import sys
from pathlib import Path

import requests
import pandas as pd

# Basket: liquid eligible tokens (BEP-20 listed on CMC) that trade as {SYM}USDT on Binance.
BASKET = [
    "ETH", "XRP", "DOGE", "ADA", "LINK", "BCH", "LTC", "AVAX", "DOT", "UNI",
    "ATOM", "FIL", "INJ", "FET", "CAKE", "TRX", "SHIB", "TON", "AAVE", "LDO",
]

INTERVAL = "1h"
DAYS = 365                      # how much history
BINANCE = "https://api.binance.com/api/v3/klines"
OUT_DIR = Path(__file__).resolve().parents[1] / "data"


def fetch_symbol(sym: str, days: int = DAYS, interval: str = INTERVAL) -> pd.DataFrame:
    """Fetch `days` of klines for SYMUSDT, paginating 1000 bars per call."""
    symbol = f"{sym}USDT"
    end = int(time.time() * 1000)
    start = end - days * 24 * 60 * 60 * 1000
    rows: list[list] = []
    cursor = start
    while cursor < end:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "limit": 1000,
        }
        r = requests.get(BINANCE, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  ! {symbol}: HTTP {r.status_code} {r.text[:120]}")
            break
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][0] + 1  # next ms after last open time
        time.sleep(0.25)           # be polite to the public endpoint
        if len(batch) < 1000:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbav", "tqav", "ignore",
    ])
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["symbol"] = sym
    return df[["time", "symbol", "open", "high", "low", "close", "volume"]]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for sym in BASKET:
        print(f"Fetching {sym}USDT ...", flush=True)
        df = fetch_symbol(sym)
        if df.empty:
            print(f"  skipped {sym} (no data)")
            continue
        print(f"  {len(df)} bars  {df['time'].min()} -> {df['time'].max()}")
        frames.append(df)
    if not frames:
        print("No data fetched. Check connectivity / Binance availability.")
        sys.exit(1)
    full = pd.concat(frames, ignore_index=True)
    pq = OUT_DIR / "ohlcv_hourly.parquet"
    try:
        full.to_parquet(pq, index=False)
        print(f"\nSaved {len(full)} rows -> {pq}")
    except Exception as e:  # pyarrow may be missing
        csv = OUT_DIR / "ohlcv_hourly.csv"
        full.to_csv(csv, index=False)
        print(f"\n(parquet failed: {e}) Saved CSV -> {csv}")


if __name__ == "__main__":
    main()
