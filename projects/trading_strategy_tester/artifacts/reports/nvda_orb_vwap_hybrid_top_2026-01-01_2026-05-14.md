# NVDA ORB + VWAP hybrid backtest

## Scope

- Symbol: `NVDA`
- Cached bar size: `5 mins`
- Requested range: `2026-01-01` through `2026-05-14`
- Opening range: first `3` bars, equivalent to 15 minutes on 5-minute data
- Full session definition: `78` RTH bars
- Target: `0.75R`
- Mode: `hybrid`
- Hold bars: `1`
- VWAP slope lookback: `0`
- VWAP slope min: `0.0`
- Max distance from VWAP in OR widths: `None`
- OR width bps filter: `0.0` to `None`
- Max failure bars: `2`
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
- Sessions with no valid trade: `2`
- Incomplete sessions skipped: `1`
- Trades: `89`
- Long trades: `53`
- Short trades: `36`
- Continuation trades: `65`
- Reversal trades: `24`
- Win rate: `58.43%`
- Gross PnL per share: `19.2125`
- Average R: `0.1542`
- Median R: `0.3849`
- Max drawdown per share: `7.6500`
- Target exits: `44`
- Stop exits: `29`
- Session-close exits: `16`

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

- ORB + VWAP gross PnL per share: `19.2125`
- Buy-and-hold PnL per share: `35.9900`
- Strategy minus buy-and-hold: `-16.7775`
- Interpretation: This candidate underperformed buy-and-hold on gross per-share PnL.

## First read

This is still a research backtest, not a deployable trading system.
Costs, slippage, and out-of-sample validation are not included yet.
Use this report as a candidate generator before walk-forward validation.

## Files

- Trade log CSV: `nvda_orb_vwap_hybrid_top_trades_2026-01-01_2026-05-14.csv`
