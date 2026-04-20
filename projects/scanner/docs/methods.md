# Methods

## Purpose

This project is a research-oriented Streamlit application for equity valuation, point-in-time screening, and forward backtesting.

The application is designed as an honest laboratory:

`data -> quality checks -> model outputs -> scenarios -> backtest -> report -> sources`

It is not a brokerage terminal, and it does not fabricate values for unavailable or restricted sources.

## Current App Structure

- `app.py`
- `src/data_sources.py`
- `src/valuation.py`
- `src/backtest.py`
- `src/core/`
- `scripts/build_top20_undervalued_report.py`

## Current Functional Areas

### Single Stock Valuation

For a selected ticker and analysis date, the app currently shows:

- price as of the selected date
- company identity fields
- basic financial snapshot
- `house fair value`
- `fair value range`
- `DCF anchor`
- `earnings anchor`
- `data quality score`
- `stability score`
- external valuation rows where public data is visible
- source-status and source-access information
- `Finviz` current snapshot and chart
- price history chart
- optional manual import of licensed valuation rows

### Universe Screener

The screener currently supports:

- `S&P 500`
- `S&P 100`

The user can choose an `as_of_date`, and the app will compute a point-in-time approximation of fair value and `% undervaluation` across the selected universe.

### Portfolio Backtest

The backtest currently supports:

- `Long undervalued`
- `Short overvalued`
- `Long / Short`

The user can choose:

- analysis date
- universe
- portfolio size
- end date / horizon
- initial capital
- commission per order
- slippage in basis points
- borrow cost for short exposure
- whether to liquidate the portfolio at the end of the test

Benchmarks:

- `QQQ`
- `SPY`

## Current Valuation Logic

The current `house fair value` is a deterministic blend of anchors from `src/valuation.py`.

### Inputs

The current model uses:

- point-in-time price history from `yfinance`
- available annual income statement, cash flow, and balance sheet data on or before the selected date
- basic market metadata when available
- official SEC filings links for evidence

### Core Anchors

The current model uses:

1. `DCF anchor`
2. `earnings anchor`
3. `book value anchor` for financial-like businesses

### DCF

The DCF leg uses:

- normalized free cash flow
- two-stage growth
- risk-free rate proxy from `^TNX`
- equity-risk-style discount rate approximation
- terminal growth

### Earnings Anchor

The earnings leg uses:

- trailing EPS or forward EPS when available
- a sector-aware fair P/E estimate
- quality and beta adjustments

### Sector Guardrails and Outlier Control

To avoid unrealistic outputs, the app currently applies:

- financials: DCF is skipped or de-emphasized; earnings and book-value anchors dominate
- telecom / utilities / energy: earnings anchor gets higher weight than DCF
- sector-specific fair-value ratio caps versus the observed price
- anchor-consensus shrinkage when DCF and earnings anchors disagree sharply

### Current Output Contract

The house model currently returns:

- `blended fair value`
- `fair value low`
- `fair value high`
- `% undervaluation`
- `quality score`
- `confidence score`
- `data quality score`
- `stability score`
- `model version`

## Point-in-Time Rules

The app currently follows these rules:

- price is taken from the last available trading day on or before the selected `as_of_date`
- financial statements are filtered to statement periods available on or before that date
- current-only sources like `Finviz` are disabled in historical mode
- external valuation pages are marked unavailable in historical mode unless point-in-time replay is actually supported

This reduces look-ahead bias, but it is not yet a full filing-date point-in-time engine.

## Backtest Logic

Current backtests are signal-free portfolio tests constructed from a ranking at one point in time.

### Portfolio Construction

- sort the universe by `% undervaluation`
- for long mode: buy top `N`
- for short mode: short bottom `N`
- for long/short mode: long top `N`, short bottom `N`
- execute on the next completed trading session after the screen date
- use equal weighting within each active leg

### Return Calculation

- `Adjusted Close` data from `yfinance`
- no rebalance in the current implementation
- optional commission per order
- optional slippage based on gross notional turnover
- optional borrow cost on short exposure
- optional liquidation cost at the end of the test
- no delisting return modeling

### Reported Metrics

- ending value
- total return
- CAGR
- volatility
- Sharpe
- Sortino
- max drawdown
- Calmar
- alpha vs `SPY`
- beta vs `SPY`
- turnover
- contribution by position
- sector exposure

## Provenance and Source Status

The app now tracks or should track for every major source:

- source name
- status
- access mode
- retrieval time
- as-of date relevance
- notes / warnings
- direct source link

Supported statuses:

- `ok`
- `partial`
- `not_visible`
- `failed`
- `stale`
- `requires_api_key`
- `requires_license`
- `requires_subscription`
- `rate_limited`

## Research-Only Disclaimer

This tool is for research and education.

Valuation outputs depend on assumptions, data quality, source availability, and model design.

It is not personalized investment advice.
