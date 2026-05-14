# NVDA ORB + VWAP research notes

## Scope

- Symbol: `NVDA`
- Data: cached IBKR 5-minute RTH bars
- Range: `2026-01-01` through `2026-05-14`
- Complete sessions tested: `91`
- Incomplete sessions excluded: `1`
- Costs/slippage: not included

## Implemented strategy improvements

- Continuation mode with configurable target R.
- Hold-bars confirmation.
- VWAP slope filter.
- Maximum distance from VWAP as a multiple of OR width.
- OR width filter in basis points.
- Failed-breakout reversal mode.
- Hybrid continuation plus failed-breakout reversal mode.
- Intraday long benchmarks:
  - daily open-to-close long
  - daily after-opening-range long
- Parameter sweep across continuation, reversal, and hybrid modes.

## Key results

| Candidate | PnL/share | Avg R | Max DD/share | Trades | Win rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| Original continuation, 1.00R | 9.77 | 0.040 | 12.25 | 89 | 56.18% | Initial baseline |
| Top continuation, 0.75R | 20.03 | 0.094 | 12.25 | 89 | 60.67% | Best gross PnL in sweep |
| Top hybrid, 0.75R + failed breakout | 19.21 | 0.154 | 7.65 | 89 | 58.43% | Similar PnL, lower drawdown |
| Reversal-only best mode family | 2.05 | 0.181 | n/a | 36 | n/a | Not competitive alone |
| Buy-and-hold | 35.99 | n/a | n/a | 1 | n/a | Still best on this trend sample |
| Daily open-to-close long | 14.11 | n/a | n/a | 91 | 57.14% | Intraday benchmark |
| Daily after-OR long | -6.62 | n/a | n/a | 91 | 47.25% | Weak benchmark |

## Interpretation

The biggest simple improvement was reducing the continuation target from `1.00R` to `0.75R`.

The hybrid mode did not beat the best continuation by gross PnL, but it reduced drawdown from `12.25` to `7.65` per share in this in-sample run. That makes it worth carrying into walk-forward validation.

Reversal-only was not competitive as a standalone strategy on this sample. Failed-breakout logic currently looks more useful as a risk-shaping overlay than as the main engine.

Buy-and-hold still wins on this sample because `NVDA` had strong multi-day trend behavior. The strategy is intraday-only, so it gives up overnight and multi-day drift by design.

## Next validation step

Do not optimize further on this same window as if it were final. The next step is walk-forward validation:

1. Split data by month.
2. Optimize on prior windows.
3. Freeze parameters.
4. Test on the next unseen month.
5. Compare against buy-and-hold, daily open-to-close long, and original continuation baseline.
