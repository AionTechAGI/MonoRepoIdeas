# Risk, execution, and reporting

## Hard Risk Controls

Per trade:

- `risk_per_trade <= 0.25%` of account equity by default in paper
- position size calculated from stop distance

Per day:

- max daily loss
- max number of trades
- max number of reversals
- max symbol loss
- max total open positions

Execution blocks:

- never enter if spread exceeds max spread
- never enter if data is delayed unless explicitly allowed
- never enter if current position is unknown
- never enter if open orders are not synchronized
- never reverse before previous position is confirmed flat
- never place a new bracket if old stop order is still active
- cancel all open orders on disconnect
- flatten position if emergency flag is triggered
- force flat before session close

## Logging

Every signal must include a reason.

Continuation example:

```text
symbol = AAPL
time = 2026-05-14 09:48:00 America/New_York
state = LONG_BREAKOUT_CANDIDATE
price = 191.25
OR High = 191.10
OR Low = 189.80
VWAP = 190.75
VWAP slope = positive
RVOL = 1.7
continuation_score = 0.82
reversal_score = 0.21
decision = ENTER_LONG_CONTINUATION
reason = close above OR High + buffer, price above VWAP, rising VWAP, high RVOL
```

Failed breakout example:

```text
decision = REVERSE_TO_SHORT_MEAN_REVERSION
reason = price broke OR High but closed back inside range within 3 minutes, upper wick ratio 0.68, continuation score collapsed, target OR Mid
```

## Reports

Research reports must include:

- total net PnL
- gross PnL
- commissions and slippage
- Sharpe
- Sortino
- max drawdown
- profit factor
- win rate
- average R
- median R
- trade count
- average holding time
- best day
- worst day
- performance by symbol
- performance by weekday
- performance by time bucket
- performance by regime
- continuation trades only
- reversal trades only
- hybrid strategy combined
- comparison against pure ORB
- comparison against pure VWAP mean reversion
- parameter stability heatmaps
- walk-forward results
- out-of-sample results

## Regime Analysis

Classify days by:

- trend day
- mean-reversion day
- chop day
- gap-and-go day
- gap-fill day
- high-volatility day
- low-volatility day
- news day
- normal day

Features:

- premarket gap
- premarket range
- opening range width
- first 15-minute volume
- relative volume
- ATR
- prior day range
- distance to previous day high/low
- SPY/QQQ VWAP alignment
- sector ETF alignment
- time of day
- spread
- liquidity
- breakout candle body ratio
- wick ratio
- distance from VWAP
- VWAP slope

Report performance separately for each regime.

## Optional ML Classifier

ML comes only after rule-based logic and backtests are stable.

Prediction point:

- moment of first breakout after `09:45`

Prediction target:

- continuation or reversal likelihood

Labels:

- `continuation_success = 1` if price reaches continuation target before reversal stop or before returning to OR Mid
- `reversal_success = 1` if failed breakout reaches VWAP/OR Mid before breaking failure extreme

Models:

- logistic regression baseline
- random forest
- gradient boosted trees
- calibrated classifier

Do not use deep learning initially.

Use time-series split only, never random train/test split.

ML output must not directly trade. It can produce:

- `P_continuation`
- `P_reversal`
- `P_no_trade`

Trading rule:

- if `P_continuation > threshold` and expected value is positive, allow continuation
- if `P_reversal > threshold` and expected value is positive, allow reversal
- otherwise no trade
