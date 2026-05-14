# Project brief

Build a Python research and paper-trading system for a hybrid 15-minute Opening Range Breakout strategy with VWAP confirmation and Failed Breakout Mean Reversion reversal logic.

The system must use the Interactive Brokers TWS API connected to an IBKR Paper Trading account through TWS or IB Gateway.

The purpose is research first:

- backtest
- optimize
- validate out-of-sample
- run the same logic in paper trading
- enforce strict risk controls

It is not a live production trading bot in the first version.

## Strategy Concept

For each regular trading session:

1. Define the session. For US equities, default is `09:30-16:00 America/New_York`.
2. First 15 minutes are `09:30-09:45`.
3. Do not trade during `09:30-09:45`.
4. At `09:45`, calculate:
   - `OR High`: highest high of first 15 minutes
   - `OR Low`: lowest low of first 15 minutes
   - `OR Mid`: `(OR High + OR Low) / 2`
   - `OR Width`: `OR High - OR Low`
5. Calculate intraday VWAP anchored from session open:
   - `VWAP = cumulative sum(typical_price * volume) / cumulative sum(volume)`
   - `typical_price = (high + low + close) / 3`
6. After `09:45`, monitor breakouts above `OR High` or below `OR Low`.
7. If a breakout is accepted, trade continuation.
8. If breakout fails and price returns inside the opening range, avoid/close continuation and optionally open the opposite mean-reversion trade.
9. Mean-reversion target can be VWAP, OR Mid, or opposite OR side depending on optimized parameters.

The system must test:

- pure continuation ORB
- pure failed-breakout reversal
- hybrid continuation plus reversal state machine

## Main Research Problem

The system must not blindly reverse every breakout wick.

It must distinguish:

- accepted breakout
- failed breakout
- noise/no-trade

The main sensitivity problem is how much confirmation is needed before treating a breakout as real, and how much failure is needed before reversing.

## First Version Priority

The first operational priority is IBKR paper connectivity:

1. Connect to TWS or IB Gateway.
2. Verify paper account.
3. Refuse live account.
4. Keep trading disabled by default.
5. Run read-only signal mode before any order workflow.
