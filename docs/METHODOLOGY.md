# Methodology — why speed leads mood

## The core insight

Markets have two observable dimensions traders usually collapse into one:

1. **Level** — where price / sentiment *is*. (Fear & Greed, RSI, price.)
2. **Velocity** — how *fast* it's changing, and whether everything moves *together*.

Almost every retail signal is a level. Levels are lagging by construction: by the
time Fear & Greed prints "extreme fear," the crowd has *already* sold. The
information is in the **transition**, not the state.

Pulse measures the transition. When dozens of tokens reprice abnormally hard in the
same hour, that synchronized burst is the market's **heart rate spiking** — the
signature of capitulation (or euphoria). That moment leads the level.

## From idea to number

For each token `i`, on hourly bars:

```
log_return_i(t) = ln( close_i(t) / close_i(t-1) )
vol_i           = rolling_std( log_return_i, window = 168h )   # its own 1-week baseline
speed_i(t)      = | log_return_i(t) | / vol_i                   # z-scored: "how abnormal is this move?"
```

Dividing by each token's *own* volatility is the key step — it makes a 5% move in a
calm stablecoin-like asset and a 5% move in a wild alt comparable. We're measuring
*surprise*, not raw magnitude.

Aggregate across the basket:

```
Pulse(t)     = mean_i speed_i(t)          # the index — a "crypto VIX"
direction(t) = mean_i log_return_i(t)     # which way the cluster is moving
```

`Pulse` is high only when **many** tokens are surprising **at once** — systemic
velocity, not one coin's noise.

## From number to regime

```
threshold = 90th percentile of Pulse over the window

regime =
  CALM      if Pulse <= threshold
  PANIC     if Pulse >  threshold AND direction < 0     # fast + falling
  EUPHORIA  if Pulse >  threshold AND direction >= 0     # fast + rising
```

## From regime to action

- **CALM** → stand aside. No velocity edge.
- **PANIC** → *contrarian*: the synchronized sell-off overshoots; fade it by buying
  the most oversold members. Historically followed by a bounce (see VALIDATION).
- **EUPHORIA** → *momentum*: synchronized strength tends to continue short-term.

All market-neutral, equal-weight — we isolate the regime signal from market beta.

## Why market-neutral

A basket of alts can fall 50% in a year (it did, 2024–25). Measuring absolute
returns in that window makes *everything* look like alpha or garbage depending on
the tape. Subtracting the cross-sectional mean (`token_return − basket_mean`)
removes the beta and exposes whether the *selection* (oversold vs strongest) adds
value. It's the honest way to test a signal.

## What Pulse is — and isn't

- ✅ A **leading regime / capitulation gauge** built from CMC data.
- ✅ A **backtestable strategy spec** (entry/exit/sizing rules per regime).
- ❌ Not a high-frequency money printer. The per-trade edge is small and, at retail
  fees, the HF version is unprofitable — we prove and disclose this in VALIDATION.
  The value is the *signal*, which is fee-immune as an alert.
