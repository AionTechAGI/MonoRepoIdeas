# IBKR paper connection

The system uses the official Interactive Brokers TWS API Python package `ibapi`.

## Default Connection Settings

- host: `127.0.0.1`
- paper TWS port: `7497`
- paper IB Gateway port: `4002`
- client id: configurable integer, default `3101`
- account: configurable, never hardcoded
- account should normally start with `DU`

Config file:

- `config/ibkr_config.yaml`

Default safety mode:

- `trading_enabled: false`
- `paper_trading_only: true`
- `allow_delayed_data_for_testing: false`

## Startup Safety Requirements

The system must never assume paper trading unless all conditions hold:

1. Configured or selected account starts with `DU`, or is explicitly marked paper.
2. TWS or IB Gateway is connected to paper mode.
3. Trading is enabled in config.
4. Startup warning prints:
   - account
   - mode
   - host
   - port
   - instruments
   - max daily loss
   - max position size

The current smoke test does not send orders.

The local PDF confirms that `nextValidId` is the practical readiness signal before sending further API requests. The smoke test waits for `nextValidId` and then verifies `reqCurrentTime`, managed accounts, and account summary.

## Local Setup Checklist

For TWS Paper:

1. Start TWS and log into Paper Trading.
2. Open `Edit -> Global Configuration -> API -> Settings`.
3. Enable `ActiveX and Socket EClients`.
4. Confirm socket port is `7497`.
5. Allow local connections from `127.0.0.1`.
6. Run:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml
```

For IB Gateway Paper:

1. Start IB Gateway and log into Paper Trading.
2. Enable API socket access.
3. Confirm socket port is `4002`.
4. Run:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml --port 4002
```

## Current Local Result

On 2026-05-14, local checks against `127.0.0.1:7497` and `127.0.0.1:4002` returned IBKR error `502`.

Meaning:

- TWS/IB Gateway is not listening locally, or
- API socket access is not enabled, or
- the configured port does not match the running IBKR application.
- firewall/security software blocks the local socket, or
- remote/trusted IP settings are wrong if not connecting from localhost.

No account was detected and no orders were sent.

See `07-user-setup-checklist.md` for the exact manual setup steps.

## Historical Data Requirements

Historical intraday bars must load from IBKR API and be cached locally to avoid pacing problems.

Default:

- 1-minute bars for backtests
- optional 5-second bars for more accurate simulation where available

Bars must include:

- timestamp UTC
- timestamp local exchange time
- symbol
- open
- high
- low
- close
- volume
- bar count if available
- WAP if available

The loader must support incremental updates by detecting the last cached timestamp and requesting only missing bars.

## Market Data Status

The system must detect/log live, delayed, frozen, or delayed-frozen data where possible.

If data is delayed, paper trading execution must be blocked unless:

- `allow_delayed_data_for_testing: true`

## Realtime Requirements

For paper trading:

1. Connect to TWS or IB Gateway.
2. Subscribe to realtime bars or streaming market data.
3. Build rolling 1-minute bars from 5-second bars or ticks.
4. Evaluate strategy from those bars.
5. Store realtime bars locally.
6. Store every decision with timestamp, symbol, state, price, VWAP, OR levels, signal, reason, and order action.

The paper system must be event-driven, not a simple sleep loop.
