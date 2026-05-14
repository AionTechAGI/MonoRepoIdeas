# Backtesting and optimization

## Event-Driven Backtester

The backtester must process historical bars in chronological order.

No look-ahead bias is allowed.

At each bar:

1. update indicators
2. update opening range
3. update state machine
4. generate signal
5. simulate order execution
6. update position
7. update PnL
8. record decision

## Fill Model

Use conservative fills.

Market order:

- fill at next bar open plus slippage

Stop order:

- fill when stop level is touched, with slippage

Limit order:

- fill only if price trades through limit price
- if price only touches limit, use configurable conservative assumption

One-minute OHLC ambiguity:

- if stop-loss and take-profit are both touched in the same bar, assume worse outcome unless using 5-second data

## Costs

Include:

- IBKR commission placeholder
- exchange fee placeholder
- SEC/FINRA fee placeholders where relevant
- spread cost
- slippage in ticks or bps
- borrow cost placeholder for shorts

## Optimization Objective

Do not optimize only for total PnL.

Evaluate each parameter set by:

- out-of-sample net PnL
- Sharpe or Sortino
- max drawdown
- profit factor
- average R per trade
- win rate
- trade count
- tail risk
- worst day
- worst week
- sensitivity stability
- turnover and commission burden

Reject parameter sets if:

- too few trades
- profitability depends on one or two outlier days
- small parameter changes destroy PnL
- performance exists only in sample
- strategy overtrades choppy days
- average win is too small relative to spread/slippage
- short trades depend on unrealistic fills

## Parameter Space

Core parameters:

- `opening_range_minutes`: 15
- `breakout_buffer_type`: ticks, bps, atr_fraction, hybrid
- `breakout_buffer_ticks`: 0, 1, 2, 3, 5
- `breakout_buffer_bps`: 0, 2, 5, 10, 15
- `breakout_buffer_atr_fraction`: 0.02, 0.05, 0.10, 0.15
- `hold_bars_for_acceptance`: 1, 2, 3, 5
- `confirmation_bar_size`: 5sec, 15sec, 1min
- `vwap_slope_lookback`: 3, 5, 10, 15
- `vwap_slope_min`: 0, small positive threshold, ATR-adjusted threshold
- `max_distance_from_vwap_for_entry`: 0.25 ATR, 0.5 ATR, 1.0 ATR, no limit
- `min_distance_from_vwap_for_continuation`: 0, 0.1 ATR, 0.2 ATR
- `relative_volume_threshold`: 1.0, 1.2, 1.5, 2.0
- `or_width_min_atr`: 0.1, 0.2, 0.3
- `or_width_max_atr`: 1.0, 1.5, 2.0
- `max_failure_minutes`: 1, 2, 3, 5, 10, 15
- `reclaim_required_close_inside`: true, false
- `reclaim_depth`: 0%, 10%, 25%, 50% of OR Width
- `wick_ratio_threshold`: 0.4, 0.5, 0.6, 0.7
- `cooldown_after_failed_signal`: 1, 3, 5, 10 minutes
- `max_flips_per_day`: 0, 1, 2
- `max_trades_per_symbol_per_day`: 1, 2, 3

Exit and risk parameters:

- `continuation_stop_mode`: opposite_OR_side, VWAP, breakout_level_reclaim, ATR_stop, swing_low_or_swing_high
- `reversal_stop_mode`: failure_extreme, OR_boundary_plus_buffer, ATR_stop
- `continuation_target_mode`: fixed_R, trailing_VWAP, previous_day_high_low, ATR_target, end_of_day
- `reversal_target_mode`: VWAP, OR_Mid, opposite_OR_side, fixed_R, partial_at_VWAP_then_OR_Mid
- `risk_reward`: 0.5R, 1R, 1.5R, 2R, 3R
- `partial_take_profit`: none, 50% at 1R, 50% at VWAP, 50% at OR Mid
- `trailing_stop`: none, VWAP trail, ATR trail, swing trail
- `time_stop_minutes`: 5, 10, 15, 30, 60
- `force_flat_time`: 15:45 America/New_York

## Walk-Forward Validation

Use walk-forward optimization.

Examples:

- train 6 months, validate 1 month, test next 1 month, then roll forward
- train 2022-2023, validate 2024, test 2025
- train 2023-2024, test 2025
- monthly walk-forward
- quarterly walk-forward

For each window:

1. select parameters only from training/validation
2. freeze parameters
3. test on unseen period
4. record performance

## Robustness

Generate heatmaps:

- breakout_buffer vs hold_bars
- max_failure_minutes vs reclaim_depth
- VWAP slope threshold vs RVOL threshold
- stop mode vs target mode
- max flips vs cooldown

Find stable parameter islands, not single best points.

A parameter set is acceptable only if neighboring combinations also perform reasonably.
