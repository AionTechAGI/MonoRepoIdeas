# Limitations

## Current Historical Biases

- historical `S&P 500` and `S&P 100` membership is not reconstructed
- the app currently uses the current constituent list as an approximation for historical screens and backtests
- this introduces survivorship bias

## Point-in-Time Constraints

- the app filters historical financial statements by statement availability, but it is not yet a full filing-date point-in-time engine
- current-only sources like `Finviz` are not replayed historically
- external valuation websites are not replayed historically unless true point-in-time access exists

## Backtest Constraints

- no rebalance in the current main backtest flow
- no dividend short-cost modeling
- no delisting return modeling
- costs are still simplified:
  - commission is flat per order
  - slippage is proportional to notional turnover
  - borrow cost is a flat annualized assumption on short exposure
- margin interest is not modeled

## Data Source Constraints

- `yfinance` is used as a major fallback for both prices and financials
- some public websites may change layout or rate-limit requests
- `Morningstar`, `GuruFocus`, and `FAST Graphs` are not faked when unavailable
- restricted sources should be supplied through legal access paths such as user export, API key, or licensed product access

## Model Constraints

- fair value is still a model output, not a market truth
- DCF can still be unstable for companies with volatile cash generation
- sector guardrails plus anchor-consensus shrinkage reduce outliers, but they do not replace a full model-applicability framework
- no full peer-model engine yet
- no scenario registry yet
- no reverse DCF yet

## UX / Architecture Constraints

- the app is still largely a single-file Streamlit UI rather than a full multi-page research lab
- provenance and quality scoring are improved but still partial
- no central data lake or DuckDB storage yet
- model versioning is visible but not yet stored in every export packet

## Compliance Constraints

- this is a research tool, not a recommendation engine
- outputs should be independently verified before use in any real investment process
