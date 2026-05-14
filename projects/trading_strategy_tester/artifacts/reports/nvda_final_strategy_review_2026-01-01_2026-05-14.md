# NVDA final strategy review

## Verdict

**REJECT current strategy logic.**

The current ORB + VWAP / failed-breakout rule set is useful as research infrastructure,
but it is not strong enough as a tradable strategy candidate. Do not move it to paper
order execution. Keep the data pipeline and backtester, but discard this specific rule set
unless a future version passes out-of-sample validation.

## Scope

- Symbol: `NVDA`
- Bar size: `5 mins`
- Range: `2026-01-01` through `2026-05-14`
- Cached bars: `7103`
- Complete sessions: `91`
- Incomplete sessions: `1`
- Cost stress used for pass/fail: `5` bps round-trip per trade
- Position size: one share for comparability

## Acceptance checklist

| Test | Result | Pass? |
|---|---:|---|
| Best in-sample gross PnL | `20.66`/share | pass |
| Best in-sample net PnL after 5 bps | `12.24`/share | pass |
| Walk-forward gross PnL | `-0.53`/share | fail |
| Walk-forward net PnL after 5 bps | `-5.39`/share | fail |
| Positive walk-forward windows | `1` / `3` | fail |
| Top 5 winner contribution for best candidate | `100.7%` | fail |
| Best candidate minus buy-and-hold net 5 bps | `-23.65`/share | fail |

Pass/fail rule: this strategy must survive walk-forward and cost stress. It does not.

## Candidate Summary

| Rank | Candidate | Gross/share | Net 5bps | Net 10bps | Net 15bps | Trades | Win | Avg R | Max DD | PF | Pos Months | Top 5 Winners |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | continuation_0.80R | 20.66 | 12.24 | 3.83 | -4.58 | 89 | 59.6% | 0.090 | 12.25 | 1.27 | 4/5 | 100.7% |
| 2 | continuation_0.75R | 20.03 | 11.62 | 3.20 | -5.21 | 89 | 60.7% | 0.094 | 12.25 | 1.27 | 4/5 | 97.4% |
| 3 | hybrid_0.75R | 19.21 | 10.80 | 2.38 | -6.04 | 89 | 58.4% | 0.154 | 7.65 | 1.31 | 4/5 | 92.2% |
| 4 | hybrid_0.80R | 18.47 | 10.05 | 1.64 | -6.78 | 89 | 57.3% | 0.144 | 7.65 | 1.29 | 4/5 | 102.3% |
| 5 | continuation_0.50R | 15.13 | 6.72 | -1.69 | -10.10 | 89 | 67.4% | 0.077 | 10.00 | 1.24 | 3/5 | 95.6% |
| 6 | continuation_1.00R | 9.77 | 1.36 | -7.05 | -15.47 | 89 | 56.2% | 0.040 | 12.25 | 1.12 | 3/5 | 231.7% |

## Walk-Forward

Expanding train window. Each test month uses only parameters selected from prior months.

| Train | Test | Selected | Test Gross/share | Test Net/share | Trades | Win | Test DD | Buy/Hold | Open/Close Long |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01-01 to 2026-02-28 | 2026-03 | hybrid_0.80R | 1.72 | -0.25 | 22 | 59.1% | 4.93 | -0.65 | 0.95 |
| 2026-01-01 to 2026-03-31 | 2026-04 | hybrid_0.80R | 3.48 | 1.53 | 20 | 50.0% | 7.24 | 23.52 | 29.36 |
| 2026-01-01 to 2026-04-30 | 2026-05 | continuation_0.80R | -5.74 | -6.68 | 9 | 55.6% | 12.25 | 24.55 | 15.25 |

## Diagnostics

- The best in-sample candidate is `continuation_0.80R`, but it collapses in the final May test window.
- The strategy's edge is concentrated: the top five winning trades explain roughly the whole in-sample profit.
- `1.00R+` targets are too ambitious for the current entry signal; most trades do not produce enough follow-through.
- Hybrid reversal logic lowers drawdown in-sample, but it does not create robust out-of-sample profitability.
- Buy-and-hold dominates on this NVDA sample, so the intraday system is not capturing the main source of return.

## Decision

Discard the current trading logic as a deployable candidate. The next research iteration should not continue
tuning only R targets. It needs a different entry filter or regime classifier, then the same final review must
be rerun before any paper order execution.

## Files

- Candidate CSV: `nvda_final_strategy_candidates_2026-01-01_2026-05-14.csv`
- Walk-forward CSV: `nvda_final_strategy_walk_forward_2026-01-01_2026-05-14.csv`
