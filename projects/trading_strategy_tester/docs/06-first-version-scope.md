# First version scope

Implement in this order:

1. IBKR paper connection smoke test.
2. Historical downloader.
3. Local data cache.
4. VWAP and opening range calculation.
5. Rule-based state machine.
6. Backtester.
7. Parameter optimizer.
8. Walk-forward validation.
9. Report.
10. Paper trading in read-only signal mode.
11. Paper trading with orders only after read-only mode is verified.

Do not start with ML.

## Important Implementation Rules

- Do not hardcode account numbers.
- Do not hardcode symbols.
- Do not trade live account.
- Do not allow live trading mode in the first version.
- Do not use future data in features.
- Do not optimize on the test period.
- Do not report in-sample performance as final performance.
- Do not ignore slippage and commissions.
- Do not reverse on wick alone.
- Do not allow unlimited flips.
- Do not place orders if data is delayed unless config explicitly allows it.
- Do not continue trading after disconnect/reconnect until positions and orders are reconciled.

## Current Implemented Checkpoint

Implemented:

- package skeleton
- YAML config files
- IBKR paper connection smoke-test client
- safety startup warning
- DU account guard
- CLI overrides for host, port, client id, and account

Blocked until local IBKR app is ready:

- actual connection to paper account
- account summary verification
- market data status verification
