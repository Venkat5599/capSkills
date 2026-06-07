"""
Pulse — signal generator.

Given the current regime + per-token last-bar returns, emit a market-neutral
basket of long picks with entry/exit/sizing rules. This is the strategy spec
the SKILL.md wraps.

Rules (validated, see backtest/):
  CALM     -> no positions
  PANIC    -> long the K most OVERSOLD tokens (most negative last-bar return);
              the overshoot reverts. Hold ~3h. Market-neutral, equal weight.
  EUPHORIA -> long the K STRONGEST tokens (most positive last-bar return);
              momentum continues. Hold ~3h. Market-neutral, equal weight.

All positions: equal weight, hold HOLD_HOURS, stop-loss STOP, take-profit TP.
"""
from __future__ import annotations
from dataclasses import dataclass, field

import pandas as pd

K = 5                 # tokens per basket
HOLD_HOURS = 3        # validated sweet spot
STOP = -0.05          # per-position stop-loss
TP = 0.06             # per-position take-profit (>= 1:1, fade bounces are quick)


@dataclass
class Signal:
    regime: str
    action: str                       # "FADE_LONG" | "MOMENTUM_LONG" | "FLAT"
    picks: list[str] = field(default_factory=list)
    hold_hours: int = HOLD_HOURS
    stop: float = STOP
    take_profit: float = TP
    note: str = ""


def generate(regime: str, last_returns: pd.Series, k: int = K) -> Signal:
    """
    last_returns: index = token symbol, value = most recent bar return.
    Returns a Signal with the long basket for this bar.
    """
    if regime == "CALM" or last_returns.dropna().empty:
        return Signal(regime=regime, action="FLAT",
                      note="Low cluster velocity. No edge. Stand aside.")
    if regime == "PANIC":
        picks = last_returns.nsmallest(k).index.tolist()   # most oversold
        return Signal(regime, "FADE_LONG", picks,
                      note="High velocity + falling cluster: fade the overshoot.")
    if regime == "EUPHORIA":
        picks = last_returns.nlargest(k).index.tolist()    # strongest
        return Signal(regime, "MOMENTUM_LONG", picks,
                      note="High velocity + rising cluster: ride the momentum.")
    return Signal(regime, "FLAT", note="Unknown regime.")


def to_dict(sig: Signal) -> dict:
    return {
        "regime": sig.regime,
        "action": sig.action,
        "picks": sig.picks,
        "hold_hours": sig.hold_hours,
        "stop_loss": sig.stop,
        "take_profit": sig.take_profit,
        "sizing": "equal-weight, market-neutral",
        "note": sig.note,
    }
