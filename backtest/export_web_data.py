"""
Export Pulse data as JSON for the demo website.
Produces site/public/pulse_data.json: pulse index series, regimes, equity curve,
headline metrics, latest signal. Downsampled for a snappy web payload.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from velocity import load_panel, compute  # noqa: E402
from signals import generate, to_dict      # noqa: E402

HOLD, K = 3, 5


def main() -> None:
    raw = load_panel()
    agg = compute(raw)
    thr = agg.attrs["panic_threshold"]

    panel = raw.sort_values(["symbol", "time"]).copy()
    panel["fwd"] = panel.groupby("symbol")["close"].transform(lambda s: s.shift(-HOLD) / s - 1)
    panel["lastret"] = panel.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1)
    panel["mkt_fwd"] = panel.groupby("time")["fwd"].transform("mean")
    panel["rel_fwd"] = panel["fwd"] - panel["mkt_fwd"]
    panel = panel.merge(agg[["regime"]].reset_index(), on="time", how="left")

    def bar_return(g):
        reg = g["regime"].iloc[0]
        if reg == "PANIC":
            return g.nsmallest(K, "lastret")["rel_fwd"].mean()
        if reg == "EUPHORIA":
            return g.nlargest(K, "lastret")["rel_fwd"].mean()
        return np.nan

    by_bar = panel.groupby("time", group_keys=False).apply(bar_return).dropna()
    trades = by_bar.iloc[::HOLD]
    equity = (1 + trades.fillna(0)).cumprod()

    metrics = {
        "total_return_pct": round(float(equity.iloc[-1] - 1) * 100, 2),
        "sharpe": round(float(trades.mean() / (trades.std() + 1e-12) * np.sqrt(24 / HOLD * 365)), 2),
        "max_drawdown_pct": round(float((equity / equity.cummax() - 1).min()) * 100, 2),
        "win_rate_pct": round(float((trades > 0).mean()) * 100, 1),
        "trades": int(len(trades)),
        "tokens": int(raw["symbol"].nunique()),
    }

    # downsample index series to ~600 points for web
    idx = agg.reset_index()
    step = max(1, len(idx) // 600)
    idx_s = idx.iloc[::step]
    series = [
        {"t": r["time"].isoformat(), "pulse": round(float(r["pulse"]), 3), "regime": r["regime"]}
        for _, r in idx_s.iterrows()
    ]
    eq = [{"t": t.isoformat(), "v": round(float(v), 4)} for t, v in equity.items()]
    eq = eq[:: max(1, len(eq) // 400)]

    # latest signal
    last_time = agg.index.max()
    last_regime = agg.loc[last_time, "regime"]
    last_bar = panel[panel["time"] == last_time].set_index("symbol")["lastret"]
    sig = to_dict(generate(last_regime, last_bar))
    sig["pulse_index"] = round(float(agg.loc[last_time, "pulse"]), 3)
    sig["timestamp"] = last_time.isoformat()

    out = {
        "metrics": metrics,
        "panic_threshold": round(float(thr), 3),
        "series": series,
        "equity": eq,
        "latest_signal": sig,
        "regime_counts": agg["regime"].value_counts().to_dict(),
    }
    dest = ROOT / "site" / "public"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "pulse_data.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {dest / 'pulse_data.json'}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
