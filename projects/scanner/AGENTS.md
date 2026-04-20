# AGENTS.md

## Purpose
- Use this file as the operating manual for market-facing agent work.
- Optimize for factual accuracy, timestamp clarity, and controlled execution.
- Treat this file as a map: keep decisions short, explicit, and auditable.

## Scope
- Applies to workflows that use any of these market plugins:
- `Alpaca`
- `Morningstar`
- `Moody's`
- `MT Newswires`
- `Dow Jones Factiva`
- and the fallback market data source `Yahoo Finance` when plugin-native historical data is unavailable in-session

## Core Operating Principles
- Separate `market data`, `fundamentals`, `credit risk`, `news`, and `execution`.
- Never treat a single plugin as the full truth for every market question.
- Prefer the freshest source for intraday state and the deepest source for slow-moving facts.
- State exact timestamps and time zones for all market-sensitive claims.
- Distinguish `confirmed fact`, `model inference`, and `trading hypothesis`.
- For market-moving decisions, require at least two independent confirmations when possible.
- If data is stale, delayed, incomplete, or contradictory, say so before giving any conclusion.

## Source of Truth by Task

### Alpaca
- Primary source for:
- live and recent market prices available through the plugin
- daily and intraday bars used for backtests or execution context
- order status, fills, positions, buying power, account state, and tradability
- session state such as market open, extended hours, and available execution venue context
- Use `Alpaca` first when the question is about `what is trading now`, `what was filled`, `can this order be placed`, or `what did the strategy do on bars`.
- Do not use Alpaca alone for deep fundamental or credit conclusions.

### Morningstar
- Primary source for:
- company fundamentals
- ETF and fund holdings, fees, style, sector exposure, and category context
- valuation context, peer comparison, portfolio analytics, and research-oriented investment descriptions
- Use `Morningstar` first when the question is about `what this business/fund is`, `how it is valued`, `what it owns`, or `how it compares with peers`.
- Prefer Morningstar over fast news feeds for slow-moving business facts.

### Moody's
- Primary source for:
- credit ratings
- rating outlooks and rating actions
- issuer-level and sovereign credit risk interpretation
- refinancing, leverage, liquidity, covenant, and default-risk framing
- Use `Moody's` when the task touches debt, creditworthiness, downgrade risk, or macro credit transmission into equities and bonds.
- Do not restate a credit conclusion as a price target or trading recommendation.

### MT Newswires
- Primary source for:
- fast, market-moving, time-sensitive headlines
- earnings headlines, guidance changes, M&A headlines, analyst actions, and macro release coverage
- event detection during market hours
- Use `MT Newswires` first for `what just happened` questions.
- Treat MT Newswires as fast signal detection, not as the only confirmation layer.

### Dow Jones Factiva
- Primary source for:
- broader news confirmation
- company timeline reconstruction
- cross-publication verification
- historical context around headlines, management commentary, and corporate events
- Use `Factiva` when you need higher confidence, cross-source corroboration, or a wider media and research context than a single newswire headline.
- Prefer Factiva over a single article or rumor when reconstructing a complex event.

### Yahoo Finance
- Fallback source for:
- public historical daily and intraday price series used in ad hoc analysis and backtests
- quick verification of widely followed symbols, ETFs, and benchmark history
- Use `Yahoo Finance` only when plugin-native market data is unavailable, incomplete, or unnecessarily slow for the task.
- Prefer `Alpaca` over Yahoo Finance for execution-facing workflows, current market state, and account-linked decisions.
- Treat Yahoo Finance as convenient public data, not as the source of truth for fills, tradability, or brokerage state.

## Plugin Priority Rules
- For `execution` and `account state`: `Alpaca` wins.
- For `breaking news`: `MT Newswires` first, then confirm with `Factiva`.
- For `fundamentals` and `fund analytics`: `Morningstar` wins.
- For `credit risk`: `Moody's` wins.
- For `historical narrative` and `multi-source verification`: `Factiva` wins.
- For `public fallback historical bars`: `Yahoo Finance` may be used when `Alpaca` data is unavailable in-session.
- If a question spans domains, use the plugin owning each domain instead of forcing one plugin to answer all parts.

## Conflict Resolution
- Resolve conflicts in this order:
1. Newer timestamp beats older timestamp for live market facts.
2. Execution-system facts beat analytics-system facts for orders, fills, and positions.
3. Domain-specialist sources beat general sources for their domain.
4. Primary company filings or exchange notices beat media summaries when available.
5. If conflict remains unresolved, present both views and stop short of a definitive claim.
- Never smooth over contradictions. Call them out explicitly.

## Timestamp and Freshness Rules
- Always include:
- exact date
- exact time when relevant
- time zone, preferably both exchange-local time and user-local time when the distinction matters
- Label data as one of:
- `real-time`
- `delayed`
- `previous close`
- `last completed session`
- `historical`
- Before market open, after market close, on weekends, and on holidays, do not describe stale last-trade data as `today's close`.
- For YTD and similar performance requests, state the exact end date used.

## Market Data Handling
- Confirm whether prices are split-adjusted, dividend-adjusted, or raw before computing returns.
- If using `Yahoo Finance`, state whether `Close` or `Adj Close` was used.
- For backtests, state:
- bar frequency
- signal definition
- execution assumption
- commissions
- slippage
- position sizing
- whether partial shares are allowed
- Use pre-YTD history when an indicator requires lookback data, such as `SMA50`.
- When computing strategy results, separate:
- gross return
- transaction costs
- end-of-period mark-to-market value
- hypothetical liquidation value if the final position were closed

## News Handling
- Never trade solely because of one headline without checking timestamp, issuer, and whether the market has already absorbed it.
- For breaking news:
1. Read the headline and timestamp from `MT Newswires`.
2. Check whether the news is company-specific, sector-wide, macro, or rumor-adjacent.
3. Confirm with `Factiva` or another independent source if the implication is material.
4. Verify whether price action, volume, and spread behavior are consistent with the headline.
- Differentiate:
- `reported`
- `confirmed by company`
- `regulatory filing`
- `market rumor`

## Fundamental and Credit Workflow
- Use `Morningstar` to establish the business, instrument structure, peer group, and baseline valuation context.
- Use `Moody's` to assess balance sheet fragility, funding risk, downgrade risk, and credit transmission channels.
- If Morningstar and Moody's imply different risk pictures, explain the difference in lens:
- equity upside/downside framing from fundamentals
- downside protection or distress framing from credit

## Order and Execution Safety
- Never imply an order has been placed unless `Alpaca` confirms accepted status.
- Never imply an order has been filled unless `Alpaca` confirms a fill.
- Before suggesting execution, check:
- asset symbol normalization
- listing venue and tradability
- session status
- position and buying power
- corporate actions or halts if relevant
- If an order depends on a headline, verify that the headline is not stale and not already invalidated by a later update.
- Prefer limit orders when spread, volatility, or liquidity uncertainty is material.
- Call out extended-hours caveats explicitly.

## Required Answer Format for Market-Critical Requests
- Every market-sensitive answer should include these items when relevant:
- `Instrument`
- `Question being answered`
- `Data sources used`
- `As-of timestamp`
- `What is confirmed`
- `What is inferred`
- `Key risks or caveats`
- `Next best action`

## Research-to-Execution Protocol
1. Identify the instrument, market, and time horizon.
2. Pull the execution-state and price context from `Alpaca`.
3. Pull fundamentals from `Morningstar` if the question is not purely tactical.
4. Pull credit context from `Moody's` if debt quality, refinancing, sovereign risk, or issuer fragility matter.
5. Pull fast news from `MT Newswires` for catalyst detection.
6. Confirm major headlines or narratives in `Factiva`.
7. State what is known versus inferred.
8. Only then suggest a trading plan or backtest interpretation.

## Backtesting Rules
- Do not mix delayed narrative data with forward-known execution assumptions.
- No look-ahead bias: signals must be generated from information available before execution.
- If using daily bars, prefer `signal on close, execute next open` unless the user requests another convention.
- State whether commissions are per order, per side, or round-trip.
- When comparing with buy-and-hold, use the same cost assumptions where applicable.
- Report trade count and whether the strategy finishes in cash or in position.

## Fair Value / Intrinsic Value Research Guide
- When the task is to find `fair value`, `intrinsic value`, `estimated value`, `DCF value`, or similar valuation outputs for a public company, prioritize primary product pages and official help or definition pages from the source itself.
- Always prefer current source terminology over generic labels. Different platforms use different names for the same idea.

### Source Priority
- Use these sources first when available:
- `Morningstar`
- `GuruFocus`
- `Alpha Spread`
- `Simply Wall St`
- `FAST Graphs`
- If multiple sources are available, collect as many valuation outputs as possible and keep the source-specific label intact.

### Source-Specific Labels
- Map each platform's wording to the broader fair value concept:

### Morningstar
- `Fair Value Estimate`
- `Price/Fair Value`
- `Morningstar Rating for Stocks`
- `Uncertainty Rating`

### GuruFocus
- `GF Value`
- `P/GF Value`
- `GF Value Rank`
- `Peter Lynch Fair Value`
- `Graham Number`
- `Earnings Power Value (EPV)` if shown

### Alpha Spread
- `Intrinsic Value`
- `DCF Value`
- `Base Case / Bull Case / Bear Case`
- `Overvaluation / Undervaluation %`
- `Discount Rate`

### Simply Wall St
- `Fair Value`
- `Fair Value Estimate`
- `Intrinsic Value`
- `Discounted Cash Flow (DCF)`
- `Undervalued / Overvalued %`

### FAST Graphs
- `Fair Value`
- `Normal P/E`
- `Valuation`
- valuation ranges derived from earnings-based fair value views

### Search Workflow
- For each ticker, search in this order:
1. official term or definition page for the platform's valuation label
2. platform stock summary page for the ticker
3. valuation-specific page for the ticker
4. help center or methodology page if the stock page is ambiguous
- Recommended search patterns:
- `site:morningstar.com <ticker> fair value estimate`
- `site:gurufocus.com <ticker> GF Value`
- `site:gurufocus.com <ticker> Peter Lynch Fair Value`
- `site:alphaspread.com <ticker> intrinsic value`
- `site:alphaspread.com <ticker> dcf valuation`
- `site:simplywall.st <ticker> fair value`
- `site:simplywall.st <ticker> intrinsic value`
- `site:fastgraphs.com <ticker> fair value`

### What To Collect
- When available, collect the maximum number of valuation fields below. Do not collapse different models into one number.
- `current price`
- `currency`
- `market cap`
- `Fair Value Estimate`
- `Intrinsic Value`
- `GF Value`
- `DCF Value`
- `Peter Lynch Fair Value`
- `Graham Number`
- `Earnings Power Value`
- `Price/Fair Value`
- `P/GF Value`
- upside or downside to fair value in percent
- undervalued or overvalued label
- bull / base / bear valuation scenarios
- uncertainty rating
- moat rating
- discount rate, `WACC`, or cost of equity if explicitly shown
- terminal growth if explicitly shown
- forecast horizon if explicitly shown
- last updated date of the valuation model
- methodology label used by the source

### Output Rules
- When reporting results:
- keep one row per source
- preserve the exact source label, for example `GF Value` instead of renaming it to `Fair Value`
- add a normalized column called `Valuation Family` with values such as `Fair Value`, `Intrinsic Value`, `DCF`, `Historical-Multiples`, `Hybrid`
- include the page URL if available
- include the valuation date or last-updated date if available
- clearly separate model outputs from market multiples
- if a number is behind login or paywall, mark it as `not visible`

### Normalization Hints
- Use these normalization rules:
- `Morningstar Fair Value Estimate -> Fair Value`
- `Morningstar Price/Fair Value -> ratio, not a value target`
- `GuruFocus GF Value -> Fair Value`
- `GuruFocus Peter Lynch Fair Value -> Fair Value`
- `GuruFocus Graham Number -> Fair Value`
- `Alpha Spread Intrinsic Value -> Intrinsic Value`
- `Alpha Spread DCF Value -> DCF`
- `Simply Wall St Fair Value -> Fair Value`
- `Simply Wall St Intrinsic Value -> Intrinsic Value`
- `FAST Graphs fair value range -> Historical-Multiples or Earnings-Based depending on the page context`

### Quality Checks
- Before finalizing:
- verify ticker and exchange match the company
- verify currency and per-share units
- note when two sources are using different methods rather than treating them as contradictory
- do not mix company-level enterprise value with per-share fair value
- prefer the latest available valuation date
- if a source only shows a ratio like `Price/Fair Value`, do not invent the missing fair value number

### Useful References
- Use these official methodology pages as the base reference for terminology:
- `Morningstar Fair Value Estimate`: https://www.morningstar.com/investing-terms/fair-value-estimate
- `Morningstar Portfolio Price/Fair Value`: https://www.morningstar.com/investing-terms/portfolio-price-fair-value
- `Morningstar Price/Fair Value Chart`: https://www.morningstar.com/markets/morningstar-price-fair-value-chart
- `GuruFocus GF Value`: https://www.gurufocus.com/glossary/gf_value
- `GuruFocus GF Value tutorial`: https://www.gurufocus.com/tutorial/article/99/gf-value
- `Alpha Spread Intrinsic Value Calculator`: https://www.alphaspread.com/intrinsic-value-calculator
- `Simply Wall St valuation methodology`: https://support.simplywall.st/hc/en-us/articles/4751563581071-Understanding-the-Valuation-section-in-the-company-report

### Preferred Deliverable
- When asked to gather valuations, default to a compact table with these columns:
- `Source | Exact Label | Valuation Family | Value | Ratio | Upside/Downside % | Method | Updated | URL`
- If enough data is available, add a second summary line:
- median per-share valuation across visible sources
- min and max visible valuation
- count of visible valuation models

## Risk and Compliance Guardrails
- Do not present outputs as personalized investment advice.
- Do not hide uncertainty behind confident language.
- For leveraged, options, crypto, microcap, or illiquid instruments, increase caution and state liquidity and gap risk explicitly.
- If a plugin is unavailable in the current session, do not fabricate access; say the plugin is unavailable and continue with the best supported fallback.
- Never invent ratings, price targets, earnings figures, order fills, or headlines.

## Session Availability Rule
- The requested plugin set may not all be enabled in every session.
- If a named plugin is unavailable:
- keep the workflow structure the same
- note the missing plugin explicitly
- use the closest reliable substitute only for that missing domain
- mark the answer as lower-confidence for that domain
- `Yahoo Finance` is the preferred fallback for public historical price data when no plugin-native source is available.

## Maintenance Guidance
- Keep this file short and operational.
- Add deeper playbooks in separate docs if the workflow grows beyond this file.
- Update rules when a recurring market-error pattern is discovered.

## Reference Links
- AGENTS.md format overview: https://github.com/agentsmd/agents.md
- GitLab guidance on keeping AGENTS.md specific and actionable: https://docs.gitlab.com/development/documentation/agents_md/
- OpenAI note on using AGENTS.md as a short map instead of a giant manual: https://openai.com/index/harness-engineering/
- Alpaca platform and market data docs: https://docs.alpaca.markets/
- Alpaca market data overview: https://docs.alpaca.markets/docs/about-market-data-api
- OpenAI Morningstar app page: https://openai.com/business/apps/morningstar/
- Moody's research assistant announcement: https://ir.moodys.com/press-releases/news-details/2023/Moodys-Launches-Moodys-Research-Assistant-a-GenAI-Tool-to-Power-Analytic-Insights/default.aspx
- MT Newswires overview: https://www.mtnewswires.com/
- MT Newswires AI and MCP page: https://www.mtnewswires.com/ai-enablement
- Dow Jones Factiva context: https://www.axios.com/2025/02/25/dow-jones-ai-factiva-publishers
- Yahoo Finance historical data landing page example: https://finance.yahoo.com/quote/SPY/history
