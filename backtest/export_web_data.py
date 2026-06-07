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

    # --- indicator validation stats (the honest headline) ---
    bk = raw.sort_values(["symbol", "time"]).copy()
    bk["r"] = bk.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1)
    basket = bk.groupby("time")["r"].mean().dropna()
    beq = (1 + basket).cumprod()
    vdf = pd.DataFrame({"eq": beq}).join(agg[["regime"]], how="inner").dropna()
    vdf["fwd24"] = vdf["eq"].shift(-24) / vdf["eq"] - 1
    daily = vdf["eq"].resample("1D").last().pct_change().dropna()
    worst = daily.nsmallest(20)
    pmax = agg["pulse"].resample("1D").max()
    p90 = agg["pulse"].quantile(0.90)
    captured = sum(1 for d in worst.index if pmax.get(d, 0) > p90
                   or pmax.get(d - pd.Timedelta(days=1), 0) > p90)
    validation = {
        "crash_capture": f"{captured}/20",
        "fwd24_after_panic": round(float(vdf.loc[vdf.regime == "PANIC", "fwd24"].mean()) * 100, 3),
        "fwd24_after_calm": round(float(vdf.loc[vdf.regime == "CALM", "fwd24"].mean()) * 100, 3),
        "fwd24_after_euphoria": round(float(vdf.loc[vdf.regime == "EUPHORIA", "fwd24"].mean()) * 100, 3),
        "years": round((agg.index.max() - agg.index.min()).days / 365, 1),
    }

    out = {
        "metrics": metrics,
        "validation": validation,
        "panic_threshold": round(float(thr), 3),
        "series": series,
        "equity": eq,
        "latest_signal": sig,
        "regime_counts": agg["regime"].value_counts().to_dict(),
    }
    dest = ROOT / "site" / "data"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "pulse_data.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {dest / 'pulse_data.json'}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
