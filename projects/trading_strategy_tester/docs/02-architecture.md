# Architecture

Target modules:

```text
config/
  strategy_config.yaml
  ibkr_config.yaml
  instruments.yaml

data/
  ibkr_client.py
  historical_loader.py
  realtime_loader.py
  data_cache.py
  calendar.py
  bar_aggregator.py

strategy/
  indicators.py
  opening_range.py
  vwap.py
  features.py
  signal_engine.py
  state_machine.py
  risk_manager.py

backtest/
  event_backtester.py
  fill_model.py
  cost_model.py
  performance.py
  walk_forward.py
  optimizer.py
  robustness.py

execution/
  paper_trader.py
  order_manager.py
  bracket_orders.py
  position_manager.py
  kill_switch.py

research/
  exploratory_analysis.py
  parameter_search.py
  regime_analysis.py
  ml_classifier_research.py
  report_generation.py

storage/
  bars
  signals
  orders
  executions
  positions
  daily_metrics
  parameter_runs

tests/
  indicators
  opening range
  VWAP
  state machine
  backtest fills
  risk controls
```

## Storage

Use SQLite or parquet storage.

Required tables/datasets:

- bars
- signals
- orders
- executions
- positions
- daily_metrics
- parameter_runs

Generated reports, exports, charts, and datasets belong in `artifacts/` or `outputs/`, not the project root.

## Paper Trading Loop

At startup:

1. Connect to IBKR TWS or IB Gateway.
2. Verify paper account.
3. Verify market data status.
4. Load config.
5. Load instruments.
6. Warm up historical data.
7. Wait for session open.

During `09:30-09:45`:

1. Collect opening range bars.
2. Update VWAP.
3. Do not trade.

At `09:45`:

1. Finalize OR High/Low/Mid.
2. Validate OR Width.
3. Switch state to `ARMED`.

After `09:45`:

1. Process every realtime bar.
2. Update VWAP.
3. Update scores.
4. Generate decision.
5. Send order only if all risk checks pass.

## Order Flow

Continuation uses bracket orders:

- parent entry order
- stop-loss child order
- take-profit child order if applicable

Reversal flow:

1. If currently in opposite continuation, flatten first.
2. Wait until order status confirms flat.
3. Cancel remaining child orders.
4. Place new reversal bracket only after reconciliation.
