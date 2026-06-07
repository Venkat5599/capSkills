"""
Pulse — live signal from CoinMarketCap AI Agent Hub.

Uses CMC's free Basic-tier endpoints (no historical OHLCV needed):
  - cryptocurrency/quotes/latest  -> percent_change_1h per token (live "speed")
  - v3/fear-and-greed/latest       -> confirming sentiment context

Computes a live Pulse proxy from cross-token 1h dispersion, classifies the
regime, and emits the market-neutral signal. This is the live path the SKILL.md
describes; the backtest validates the same logic on history.
"""
from __future__ import annotations
import os
import json
from pathlib import Path

import requests

BASKET = ["ETH", "XRP", "DOGE", "ADA", "LINK", "BCH", "LTC", "AVAX", "DOT", "UNI",
          "ATOM", "FIL", "INJ", "FET", "CAKE", "TRX", "SHIB", "TON", "AAVE", "LDO"]
BASE = "https://pro-api.coinmarketcap.com"
K = 5


def load_key() -> str:
    key = os.environ.get("CMC_API_KEY")
    if key:
        return key
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("CMC_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("No CMC_API_KEY (set env var or pulse/.env)")


def get(path: str, params: dict, key: str) -> dict:
    r = requests.get(BASE + path, params=params,
                     headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"},
                     timeout=20)
    return {"status": r.status_code, "json": r.json() if r.content else {}}


def main() -> None:
    key = load_key()
    q = get("/v1/cryptocurrency/quotes/latest",
            {"symbol": ",".join(BASKET), "convert": "USD"}, key)
    if q["status"] != 200:
        print(f"Quotes error {q['status']}: {json.dumps(q['json'])[:200]}")
        raise SystemExit(1)

    data = q["json"].get("data", {})
    moves = {}
    for sym in BASKET:
        d = data.get(sym)
        if isinstance(d, list):
            d = d[0] if d else None
        if not d:
            continue
        usd = d["quote"]["USD"]
        pc1h = usd.get("percent_change_1h")
        if pc1h is not None:
            moves[sym] = pc1h / 100.0

    if not moves:
        raise SystemExit("No quote data returned.")

    import statistics as st
    vals = list(moves.values())
    spread = st.pstdev(vals) or 1e-9
    pulse = sum(abs(v) for v in vals) / len(vals) / spread   # live speed proxy
    direction = sum(vals) / len(vals)

    # Fear & Greed (context) — endpoint may need a paid tier; degrade gracefully
    fg = get("/v3/fear-and-greed/latest", {}, key)
    fg_val = None
    if fg["status"] == 200:
        try:
            fg_val = fg["json"]["data"]["value"]
        except Exception:
            fg_val = None

    # regime: high dispersion-adjusted speed = high velocity. Threshold ~1.0 on proxy.
    high = pulse > 1.0
    regime = "CALM" if not high else ("PANIC" if direction < 0 else "EUPHORIA")
    if regime == "PANIC":
        picks = sorted(moves, key=moves.get)[:K]            # most oversold
        action = "FADE_LONG"
    elif regime == "EUPHORIA":
        picks = sorted(moves, key=moves.get, reverse=True)[:K]
        action = "MOMENTUM_LONG"
    else:
        picks, action = [], "FLAT"

    out = {
        "source": "CoinMarketCap AI Agent Hub (quotes/latest + fear-and-greed)",
        "pulse_index": round(pulse, 3),
        "direction_1h": round(direction * 100, 3),
        "regime": regime,
        "action": action,
        "picks": picks,
        "fear_greed": fg_val,
        "hold_hours": 3,
        "stop_loss": -0.05,
        "take_profit": 0.06,
        "sizing": "equal-weight, market-neutral",
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
