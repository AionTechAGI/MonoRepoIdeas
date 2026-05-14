# NVDA ORB + VWAP reversal backtest

## Scope

- Symbol: `NVDA`
- Cached bar size: `5 mins`
- Requested range: `2026-01-01` through `2026-05-14`
- Opening range: first `3` bars, equivalent to 15 minutes on 5-minute data
- Full session definition: `78` RTH bars
- Target: `1.00R`
- Mode: `reversal`
- Hold bars: `1`
- VWAP slope lookback: `0`
- VWAP slope min: `0.0`
- Max distance from VWAP in OR widths: `None`
- OR width bps filter: `0.0` to `None`
- Max failure bars: `3`
- Wick ratio threshold: `0.4`
- Reversal target mode: `OR_MID`
- Entry: next bar open after close breaks OR boundary and aligns with VWAP
- Long filter: signal close > OR High and signal close > VWAP
- Short filter: signal close < OR Low and signal close < VWAP
- Stop: opposite opening-range boundary
- Same-bar stop/target conflict: stop wins
- Max trades: one trade per day
- Costs/slippage: not included in this first baseline
- Incomplete sessions: excluded from performance

## Results

- Complete sessions tested: `91`
- Sessions with no valid trade: `48`
- Incomplete sessions skipped: `1`
- Trades: `43`
- Long trades: `24`
- Short trades: `19`
- Continuation trades: `0`
- Reversal trades: `43`
- Win rate: `46.51%`
- Gross PnL per share: `1.0400`
- Average R: `0.0657`
- Median R: `-1.0000`
- Max drawdown per share: `3.9800`
- Target exits: `19`
- Stop exits: `23`
- Session-close exits: `1`

## Buy-and-hold benchmark

- Assumption: buy one share at first complete-window bar open and hold to final complete-window bar close
- Entry: `20260102  15:30:00` at `189.8400`
- Exit: `20260513  21:55:00` at `225.8300`
- PnL per share: `35.9900`
- Return: `18.96%`

## Intraday benchmarks

- Daily open-to-close long PnL per share: `14.1100`
- Daily open-to-close long win rate: `57.14%`
- Daily after-opening-range long PnL per share: `-6.6200`
- Daily after-opening-range long win rate: `47.25%`

## Comparison

- ORB + VWAP gross PnL per share: `1.0400`
- Buy-and-hold PnL per share: `35.9900`
- Strategy minus buy-and-hold: `-34.9500`
- Interpretation: This candidate underperformed buy-and-hold on gross per-share PnL.

## First read

This is still a research backtest, not a deployable trading system.
Costs, slippage, and out-of-sample validation are not included yet.
Use this report as a candidate generator before walk-forward validation.

## Files

- Trade log CSV: `nvda_orb_vwap_reversal_trades_2026-01-01_2026-05-14.csv`
