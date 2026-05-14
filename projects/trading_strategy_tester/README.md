# Trading Strategy Tester

`Trading Strategy Tester` is the workspace for building and validating trading strategy experiments.

## Purpose

- define strategy ideas with explicit assumptions
- test strategies on historical market data
- compare results against buy-and-hold or benchmark portfolios
- produce auditable reports for follow-up research

## Quick start

Install dependencies:

```powershell
cd C:\develop\MonoRepoIdeas\projects\trading_strategy_tester
py -m pip install -r requirements.txt
```

Check the IBKR paper connection:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml
```

Request a read-only historical data sample and cache it locally:

```powershell
py scripts\probe_historical_data.py --symbol SPY --primary-exchange ARCA --duration "1 D" --bar-size "1 min"
```

Download a historical range and generate a candlestick/volume HTML chart:

```powershell
py scripts\download_historical_range.py --symbol NVDA --primary-exchange NASDAQ --start 2026-01-01 --end 2026-05-14 --bar-size "5 mins" --duration "1 M" --output artifacts\reports\nvda_5min_rth_2026-01-01_2026-05-14.html
```

Probe market data status without placing orders:

```powershell
py scripts\probe_market_data_status.py --symbol SPY --primary-exchange ARCA --market-data-type 1
```

Expected local paper ports:

- TWS paper: `127.0.0.1:7497`
- IB Gateway paper: `127.0.0.1:4002`

TWS paper on port `7497` is enough for the first version. IB Gateway is optional.

The first version is read-only by default. `trading_enabled` must remain `false` until read-only signal mode is verified.

If IBKR returns delayed market data, execution remains blocked unless `allow_delayed_data_for_testing` is explicitly enabled.

Latest generated report:

- `artifacts/reports/nvda_5min_rth_2026-01-01_2026-05-14.html`
- `artifacts/reports/nvda_5min_rth_2026-01-01_2026-05-14_summary.md`

Charts use compressed market time so weekends, holidays, and overnight market closures do not create empty visual gaps.

The report renderer uses TradingView Lightweight Charts on canvas for intraday OHLC data. This is much faster than SVG-based Plotly candlesticks for multi-thousand-bar charts.

## Structure

- `docs/` local project documentation
- `config/` YAML configuration
- `src/` source code
- `tests/` automated checks
- `artifacts/` reports and outputs
