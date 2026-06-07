# Pulse — Backtest Results

Data: 1 year hourly, 20 liquid CMC-eligible tokens (Binance free klines).
Strategy: regime-switching, market-neutral, equal-weight, 3h hold, non-overlapping.

## Headline (combined regime strategy)
| Metric | Value |
|---|---|
| Trades (non-overlapping) | 290 |
| Total market-neutral return | +18.74% |
| Win rate | 50.3% |
| Annualized Sharpe (approx) | 4.45 |
| Max drawdown | -5.46% |

## Per-regime edge (all bars, market-neutral, 3h)
| Regime rule | Win | Rel. return/trade | t-stat |
|---|---|---|---|
| PANIC -> fade oversold | 53.0% | +0.050% | ~2.1 |
| EUPHORIA -> momentum | 46.4% | +0.068% | ~1.7 |

## Honest notes
- Edge is real but modest; this is a *strategy spec*, not a money printer.
- Edge is specifically **market-neutral + short-horizon (3h)**. Naive absolute /
  long-hold versions show no edge — documented in backtest.py vs backtest2.py.
- Panic threshold = 90th percentile of the Pulse index.
- Chart: `pulse_results.png`.
