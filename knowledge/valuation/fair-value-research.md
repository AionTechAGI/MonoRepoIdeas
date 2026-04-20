# Fair value research guide

Use this note when a task asks for `fair value`, `intrinsic value`, `estimated value`, or `DCF value` for a public company.

## Source priority

Prefer these sources first when they are available:

1. `Morningstar`
2. `GuruFocus`
3. `Alpha Spread`
4. `Simply Wall St`
5. `FAST Graphs`

Keep each source's own label instead of renaming everything to one generic term.

## What to collect

- current price
- currency
- market cap
- `Fair Value Estimate`
- `Intrinsic Value`
- `GF Value`
- `DCF Value`
- `Peter Lynch Fair Value`
- `Graham Number`
- `Earnings Power Value`
- `Price/Fair Value`
- `P/GF Value`
- upside or downside percent
- undervalued or overvalued label
- bull, base, and bear cases when shown
- uncertainty or moat labels when shown
- last-updated date
- methodology label

## Output format

Default to a compact table with:

`Source | Exact Label | Valuation Family | Value | Ratio | Upside/Downside % | Method | Updated | URL`

If enough values are visible, add:

- median visible per-share valuation
- min and max visible valuation
- count of visible valuation models

## Normalization hints

- `Morningstar Fair Value Estimate` -> `Fair Value`
- `Morningstar Price/Fair Value` is a ratio, not a target
- `GuruFocus GF Value` -> `Fair Value`
- `GuruFocus Peter Lynch Fair Value` -> `Fair Value`
- `GuruFocus Graham Number` -> `Fair Value`
- `Alpha Spread Intrinsic Value` -> `Intrinsic Value`
- `Alpha Spread DCF Value` -> `DCF`
- `Simply Wall St Fair Value` -> `Fair Value`
- `Simply Wall St Intrinsic Value` -> `Intrinsic Value`

## Quality checks

- Verify the ticker and exchange.
- Verify the currency and per-share units.
- Do not mix enterprise value with per-share fair value.
- If a source only shows a ratio, do not invent the missing value target.
- Treat different methods as different lenses, not automatic contradictions.
