"""
Pulse — conviction layer (sentiment confirmation).

Combines the Pulse velocity regime with CoinMarketCap's Fear & Greed index to
produce a conviction grade. Both come from CMC (reliable, no flaky scrapers) —
this strengthens the "Best Use of Agent Hub" story.

Logic: high conviction when price velocity AND crowd sentiment agree.
  PANIC    + extreme fear  (F&G <= 25) -> HIGH (capitulation, contrarian long)
  EUPHORIA + extreme greed (F&G >= 75) -> HIGH (momentum)
  agreement-ish                        -> MEDIUM
  disagreement                         -> LOW (size down / wait)

Optional bonus for a LIVE demo: an agent with the `agent-reach` skill can also
pull X/Twitter chatter ("search crypto fear/panic on twitter") to corroborate —
shown in the demo, not hard-wired here (free social scrapers are rate-limited).
"""
from __future__ import annotations


def conviction(regime: str, fear_greed: int | None) -> dict:
    if fear_greed is None:
        return {"grade": "MEDIUM", "reason": "price signal only; F&G unavailable",
                "fear_greed": None}
    fg = int(fear_greed)
    label = ("extreme fear" if fg <= 25 else "fear" if fg <= 45 else
             "neutral" if fg <= 55 else "greed" if fg < 75 else "extreme greed")
    if regime == "PANIC" and fg <= 25:
        grade, reason = "HIGH", "velocity panic + extreme fear agree (capitulation)"
    elif regime == "EUPHORIA" and fg >= 75:
        grade, reason = "HIGH", "velocity euphoria + extreme greed agree (momentum)"
    elif regime == "PANIC" and fg <= 45:
        grade, reason = "MEDIUM", "velocity panic + fearful crowd"
    elif regime == "EUPHORIA" and fg >= 55:
        grade, reason = "MEDIUM", "velocity euphoria + greedy crowd"
    elif regime == "CALM":
        grade, reason = "LOW", "calm regime — no trade"
    else:
        grade, reason = "LOW", "velocity and sentiment disagree; size down or wait"
    return {"grade": grade, "reason": reason, "fear_greed": fg, "fg_label": label}


if __name__ == "__main__":
    import json
    for r, fg in [("PANIC", 12), ("EUPHORIA", 82), ("PANIC", 60), ("CALM", 40)]:
        print(r, fg, "->", json.dumps(conviction(r, fg)))
