# Strategy state machine

The strategy must be implemented as a state machine.

## States

- `PRE_OPEN`
- `WAITING_FOR_OPENING_RANGE`
- `OPENING_RANGE_COMPLETE`
- `ARMED`
- `LONG_BREAKOUT_CANDIDATE`
- `SHORT_BREAKOUT_CANDIDATE`
- `LONG_CONTINUATION`
- `SHORT_CONTINUATION`
- `LONG_FAILED_BREAKOUT`
- `SHORT_FAILED_BREAKOUT`
- `LONG_MEAN_REVERSION`
- `SHORT_MEAN_REVERSION`
- `FLAT_DONE`
- `LOCKED_OUT`

## State Logic

`PRE_OPEN`:

- Before session open.
- No trading.

`WAITING_FOR_OPENING_RANGE`:

- From session open until session open plus 15 minutes.
- Collect bars.
- No trading.

`OPENING_RANGE_COMPLETE`:

- Calculate OR High, OR Low, OR Mid, OR Width.
- Validate OR Width.
- Lock out the symbol for the day if width is too small or too large.

`ARMED`:

- After `09:45`.
- Watch for breakout above OR High or below OR Low.

`LONG_BREAKOUT_CANDIDATE`:

- Triggered when price trades above OR High plus buffer.
- Do not immediately enter unless configured to enter on touch.
- Prefer confirmation by bar close.

`SHORT_BREAKOUT_CANDIDATE`:

- Triggered when price trades below OR Low minus buffer.
- Do not immediately enter unless configured to enter on touch.
- Prefer confirmation by bar close.

`LONG_CONTINUATION`:

- Open/hold long after accepted upside breakout.

`SHORT_CONTINUATION`:

- Open/hold short after accepted downside breakout.

`LONG_FAILED_BREAKOUT`:

- Upside breakout failed.
- Price returned below OR High and inside the range.
- Flatten long if any and optionally enter short mean reversion.

`SHORT_FAILED_BREAKOUT`:

- Downside breakout failed.
- Price returned above OR Low and inside the range.
- Flatten short if any and optionally enter long mean reversion.

`LONG_MEAN_REVERSION`:

- Long after failed downside breakout.
- Target usually VWAP or OR Mid.

`SHORT_MEAN_REVERSION`:

- Short after failed upside breakout.
- Target usually VWAP or OR Mid.

`FLAT_DONE`:

- No more trading for the symbol today after max trades, max loss, or completed trade.

`LOCKED_OUT`:

- No trading due to risk, bad data, excessive spread, low liquidity, news window, or config rule.

## Continuation Breakout Rules

Upside breakout confirmation can include:

- close above OR High plus breakout buffer
- price above VWAP
- positive VWAP slope over last N bars
- breakout candle volume above relative volume threshold
- price remains above OR High for `hold_bars`
- spread below max spread bps
- OR Width acceptable relative to ATR
- market index confirmation, for example SPY/QQQ above VWAP
- no major scheduled news window
- time since open is not too late

Downside breakout is symmetrical:

- close below OR Low minus breakout buffer
- price below VWAP
- negative VWAP slope
- volume confirms
- hold below OR Low
- acceptable spread
- acceptable OR Width
- SPY/QQQ confirmation negative
- no major news window
- time filter passes

## Failed Breakout Rules

Failed upside breakout:

1. price trades above OR High plus buffer
2. continuation is not accepted or was invalidated
3. price closes back below OR High
4. price returns inside the opening range within `max_failure_minutes`
5. failure candle has upper wick ratio above threshold
6. rejection volume is acceptable
7. price is not strongly above rising VWAP
8. reversal score exceeds threshold

If valid, open short mean reversion.

Failed downside breakout:

1. price trades below OR Low minus buffer
2. continuation is not accepted or was invalidated
3. price closes back above OR Low
4. price returns inside the opening range within `max_failure_minutes`
5. failure candle has lower wick ratio above threshold
6. rejection volume is acceptable
7. price is not strongly below falling VWAP
8. reversal score exceeds threshold

If valid, open long mean reversion.

## Scores

Implement:

- `continuation_score`
- `reversal_score`

Continuation score inputs:

- close beyond OR boundary
- VWAP alignment
- VWAP slope
- volume expansion
- market index confirmation
- clean candle body
- low spread
- acceptable OR Width
- successful hold outside range

Reversal score inputs:

- failed hold outside OR
- close back inside range
- speed of reclaim
- wick rejection
- failure to expand volume in breakout direction
- stretched distance from VWAP
- opposite pressure from SPY/QQQ
- low continuation score
- return toward fair value

Decision rule:

- If `continuation_score >= continuation_threshold`, enter or hold continuation.
- If `reversal_score >= reversal_threshold`, enter opposite mean reversion.
- If both scores are weak, no trade.
- If both scores are strong, no trade by default because conflict means uncertainty.
