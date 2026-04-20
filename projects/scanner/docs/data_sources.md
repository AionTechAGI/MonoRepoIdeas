# Data Sources

## Current Priority Order

### Financial Statements

For US large caps in the current implementation:

1. `SEC EDGAR` for official filings evidence
2. `yfinance` as current practical fundamentals provider
3. public valuation pages as reference-only context

### Prices

Current implementation:

1. `yfinance` adjusted historical pricing
2. benchmark ETFs such as `SPY` and `QQQ` through the same provider

### Public Valuation Pages

Currently used when visible:

- `Alpha Spread`
- `Simply Wall St`
- `Finviz` snapshot

Restricted or conditional sources:

- `Morningstar`
- `GuruFocus`
- `FAST Graphs`

## Source Access v1.0

The app now distinguishes between several legal access states instead of lumping everything into `not_visible`.

### Official / public API paths

- `SEC EDGAR`
  - public official API
  - no API key
  - requires declared user agent and fair-access compliance
- `SimFin`
  - legal API / bulk-download path
  - free and paid plans depending on coverage and history
- `Alpha Vantage`
  - official API key path
- `Financial Modeling Prep`
  - official API key path

### Licensed / subscription paths

- `Morningstar`
  - public terminology pages are visible
  - per-ticker licensed data is a `requires_license` source unless the user provides licensed access or manual export
- `GuruFocus`
  - public site may be readable in a normal browser, but app requests can be blocked
  - official expansion path is the `GuruFocus Data API` or a user-supplied export
- `FAST Graphs`
  - active trial or subscription required for current valuation output
  - best legal path in this app is user-supplied export

### Manual import path

Single-stock analysis supports user-uploaded valuation files for licensed tools.

Recommended columns:

- `Source`
- `Exact Label`
- `Valuation Family`
- `Value`
- optional `Ratio`
- optional `Upside/Downside %`
- optional `Method`
- optional `Updated`
- optional `URL`

## Source Status Policy

When a source is requested, the app should surface status explicitly:

- `ok`
- `partial`
- `not_visible`
- `failed`
- `stale`
- `requires_api_key`
- `requires_license`
- `requires_subscription`
- `rate_limited`

The app should prefer an honest missing value to a fabricated value.
