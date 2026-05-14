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
- Exit-policy / R analysis for the same continuation entries:
  - fixed R targets
  - partial exits
  - session-close runners
  - simple high/low and VWAP trailing exits

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

## Exit policy / R analysis

The exit-policy test reused the `89` first continuation entries and compared what happens after entry.

| Exit policy | PnL/share | Avg R | Max DD/share | Win rate | Notes |
|---|---:|---:|---:|---:|---|
| Fixed 0.80R | 20.66 | 0.090 | 12.25 | 59.6% | Best current fixed target by gross PnL |
| Fixed 0.75R | 20.03 | 0.094 | 12.25 | 60.7% | Very close, slightly higher hit rate and average R |
| 80% at 0.75R, VWAP trail runner | 17.00 | 0.079 | 12.25 | 60.7% | Best current partial-runner variant |
| 80% at 0.75R, breakeven runner to close | 16.98 | 0.078 | 12.25 | 60.7% | Similar to VWAP trail |
| 70% at 0.75R, VWAP trail runner | 15.48 | 0.072 | 12.25 | 60.7% | Better than 50/50 runner split |
| Fixed 0.50R | 15.13 | 0.077 | 10.00 | 67.4% | Higher hit rate, lower profit |
| 50% at 0.75R, VWAP trail | 12.45 | 0.057 | 12.25 | 60.7% | Better control, still below fixed 0.75R |
| 50% at 0.75R, breakeven runner to close | 12.40 | 0.055 | 12.25 | 60.7% | Banks profit, runner still gives back |
| 50% at 0.75R, original-stop runner to close | 12.36 | 0.055 | 12.25 | 55.1% | More room, lower hit rate |
| Fixed 1.00R | 9.77 | 0.040 | 12.25 | 56.2% | Original continuation baseline |
| Fixed 1.50R | 6.68 | 0.021 | 12.46 | 55.1% | Too few targets reached |
| Fixed 2.00R | 5.15 | 0.013 | 13.60 | 53.9% | Too ambitious for this signal |
| Session-close runner with original stop | 4.70 | 0.017 | 12.84 | 53.9% | Positive, but far below fixed 0.75R |

MFE / MAE diagnostics:

- Average MFE: `0.784R`
- Median MFE: `0.690R`
- Trades reaching at least `0.75R`: `43` / `89`
- Trades reaching at least `1.00R`: `25` / `89`
- Trades reaching at least `1.50R`: `11` / `89`
- Trades reaching at least `2.00R`: `5` / `89`

## Interpretation

The biggest simple improvement was reducing the continuation target from `1.00R` into the `0.75R` to `0.80R` zone.

The exit-policy analysis confirms why: median MFE is below `0.75R`, and only `25` of `89` trades reached `1.00R`. On this sample, the strategy produces many small intraday pushes rather than frequent large runners. The current best fixed target is `0.80R`, but the `0.75R` result is close enough that both should go into walk-forward validation rather than choosing one from this in-sample window.

Let-winners-run is still worth researching, but not as a simple session-close runner or a large 50/50 runner. The better partial-runner candidates so far are `80/20` and `70/30` at `0.75R`, especially with VWAP or breakeven protection, but they still trail fixed `0.75R` and `0.80R`. Next runner tests should activate the runner only after stronger trend confirmation or use ATR / VWAP / OR-boundary trailing logic.

The hybrid mode did not beat the best continuation by gross PnL, but it reduced drawdown from `12.25` to `7.65` per share in this in-sample run. That makes it worth carrying into walk-forward validation.

Reversal-only was not competitive as a standalone strategy on this sample. Failed-breakout logic currently looks more useful as a risk-shaping overlay than as the main engine.

Buy-and-hold still wins on this sample because `NVDA` had strong multi-day trend behavior. The strategy is intraday-only, so it gives up overnight and multi-day drift by design.

## Next validation step

The final review has now been run for the current candidate family:

- Best in-sample candidate: `continuation_0.80R`
- Best in-sample gross PnL: `20.66` per share
- Best in-sample net PnL after 5 bps: `12.24` per share
- Walk-forward gross PnL: `-0.53` per share
- Walk-forward net PnL after 5 bps: `-5.39` per share
- Positive walk-forward windows: `1` / `3`
- Verdict: reject the current rule set as a deployable trading strategy

Do not optimize further on this same window as if it were final. If research continues, the next step is not another R-target tweak. It must be a different entry filter or regime classifier, followed by the same walk-forward final review:

1. Split data by month.
2. Optimize on prior windows.
3. Freeze parameters.
4. Test on the next unseen month.
5. Compare against buy-and-hold, daily open-to-close long, and original continuation baseline.

If a new entry filter or regime classifier is built, carry these exit policies into its walk-forward test:

- fixed `0.50R`
- fixed `0.75R`
- fixed `0.80R`
- fixed `1.00R`
- hybrid continuation with fixed `0.75R`
- hybrid continuation with fixed `0.80R`
- partial `70/30` and `80/20` at `0.75R` with a stricter runner trail
