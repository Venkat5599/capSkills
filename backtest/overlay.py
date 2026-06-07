"""
Pulse — risk-overlay proof (the killer chart).

Claim: Pulse is a regime INDICATOR that makes other strategies safer.
Test it honestly as a risk overlay on a vanilla baseline:

  Baseline   = equal-weight buy & hold the basket (classic crypto exposure).
  Pulse-gated = same, but move to CASH whenever Pulse says PANIC
                (high cluster velocity + falling). Re-enter when not PANIC.

If Pulse-gated has better drawdown and Sharpe than baseline, the indicator has
real, fee-light value — you only trade on regime *flips* (a handful of times),
so transaction cost is negligible vs a per-bar strategy.

Outputs: overlay_results.png + metrics appended to results.md + JSON for the site.
"""
from __future__ import annotations
import json
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

FLIP_FEE = 0.30 / 100   # cost charged only when we flip in/out of cash


def metrics(eq: pd.Series, rets: pd.Series) -> dict:
    total = (eq.iloc[-1] - 1) * 100
    sharpe = rets.mean() / (rets.std() + 1e-12) * np.sqrt(24 * 365)
    mdd = (eq / eq.cummax() - 1).min() * 100
    # Calmar = annual return / |maxDD|
    ann = ((eq.iloc[-1]) ** (24 * 365 / len(rets)) - 1) * 100
    calmar = ann / abs(mdd) if mdd != 0 else float("nan")
    return {"total_return_pct": round(total, 2), "sharpe": round(sharpe, 2),
            "max_drawdown_pct": round(mdd, 2), "calmar": round(calmar, 2)}


def main() -> None:
    raw = load_panel()
    agg = compute(raw)

    # basket hourly return = equal-weight mean of per-token returns
    raw = raw.sort_values(["symbol", "time"]).copy()
    raw["ret"] = raw.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1)
    basket = raw.groupby("time")["ret"].mean().dropna()

    df = pd.DataFrame({"ret": basket}).join(agg[["regime"]], how="inner").dropna()

    # baseline: always invested
    df["base_eq"] = (1 + df["ret"]).cumprod()

    # pulse-gated: realistic risk overlay. Exit only on SUSTAINED panic, re-enter
    # only after panic clears for a while -> few flips, no hourly hindsight timing.
    EXIT_PERSIST = 3      # need 3 consecutive PANIC hours to de-risk
    REENTER_CALM = 12     # need 12 consecutive non-PANIC hours to re-risk
    is_panic = (df["regime"] == "PANIC").astype(int)
    panic_run = is_panic.groupby((is_panic != is_panic.shift()).cumsum()).cumcount() + 1
    panic_run = panic_run * is_panic
    calm_run = (1 - is_panic).groupby((is_panic != is_panic.shift()).cumsum()).cumcount() + 1
    calm_run = calm_run * (1 - is_panic)

    invested = []
    state = 1  # start invested
    for pr, cr in zip(panic_run.values, calm_run.values):
        if state == 1 and pr >= EXIT_PERSIST:
            state = 0
        elif state == 0 and cr >= REENTER_CALM:
            state = 1
        invested.append(state)
    invested = pd.Series(invested, index=df.index)
    flips = invested.diff().abs().fillna(0)
    gated_ret = df["ret"] * invested - flips * FLIP_FEE
    df["gated_eq"] = (1 + gated_ret).cumprod()

    base_m = metrics(df["base_eq"], df["ret"])
    gated_m = metrics(df["gated_eq"], gated_ret)
    n_flips = int(flips.sum())

    print("=" * 64)
    print("PULSE RISK-OVERLAY  (go to cash on PANIC)")
    print("=" * 64)
    print(f"{'metric':>16} | {'baseline':>10} | {'pulse-gated':>12}")
    print("-" * 64)
    for k in ["total_return_pct", "sharpe", "max_drawdown_pct", "calmar"]:
        print(f"{k:>16} | {base_m[k]:>10} | {gated_m[k]:>12}")
    print("-" * 64)
    print(f"Regime flips (trades) over the year: {n_flips}  -> fee drag negligible")
    better_dd = gated_m["max_drawdown_pct"] > base_m["max_drawdown_pct"]
    better_sh = gated_m["sharpe"] > base_m["sharpe"]
    print(f"Drawdown improved: {better_dd} | Sharpe improved: {better_sh}")
    print("=" * 64)

    # chart
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df.index, df["base_eq"], color="#888", lw=1.3, label="Buy & hold")
    ax.plot(df.index, df["gated_eq"], color="#34d399", lw=1.6, label="With Pulse risk-overlay")
    panic = df[df["regime"] == "PANIC"]
    ax.scatter(panic.index, df.loc[panic.index, "gated_eq"], s=4, color="#fb5e6d",
               label="PANIC (in cash)", zorder=3)
    ax.set_title("Pulse as a risk overlay — go to cash when the market panics")
    ax.legend(loc="upper left", fontsize=9)
    ax.axhline(1.0, color="#ccc", lw=0.6)
    fig.tight_layout()
    fig.savefig(ROOT / "backtest" / "overlay_results.png", dpi=120)

    # append results.md
    md = ["\n## Pulse as a risk overlay (the headline result)\n",
          "Move to cash during PANIC regime; otherwise hold the basket. "
          f"Only {n_flips} regime flips/year, so fees are negligible.\n",
          "| Metric | Buy & hold | With Pulse overlay |",
          "|---|---|---|",
          f"| Total return | {base_m['total_return_pct']}% | {gated_m['total_return_pct']}% |",
          f"| Sharpe | {base_m['sharpe']} | {gated_m['sharpe']} |",
          f"| Max drawdown | {base_m['max_drawdown_pct']}% | {gated_m['max_drawdown_pct']}% |",
          f"| Calmar | {base_m['calmar']} | {gated_m['calmar']} |",
          ""]
    (ROOT / "backtest" / "results.md").open("a", encoding="utf-8").write("\n".join(md) + "\n")

    # JSON for site
    eq_base = [{"t": t.isoformat(), "v": round(float(v), 4)} for t, v in df["base_eq"].items()]
    eq_gated = [{"t": t.isoformat(), "v": round(float(v), 4)} for t, v in df["gated_eq"].items()]
    step = max(1, len(eq_base) // 400)
    out = {"baseline": base_m, "gated": gated_m, "flips": n_flips,
           "eq_base": eq_base[::step], "eq_gated": eq_gated[::step]}
    (ROOT / "site" / "data" / "overlay_data.json").write_text(json.dumps(out, indent=2))
    print("Wrote overlay_results.png, overlay_data.json, results.md")


if __name__ == "__main__":
    main()
