# Codex handoff

Date: `2026-05-15`

This document captures the active chat context so work can continue from another Codex session inside the monorepo.

## Repository

- Repo: `https://github.com/AionTechAGI/MonoRepoIdeas.git`
- Local path: `C:\develop\MonoRepoIdeas`
- Project path: `C:\develop\MonoRepoIdeas\projects\trading_strategy_tester`
- Main branch is used for the current work.
- Commit and push every meaningful checkpoint so another Codex session can resume safely.

## User goal

Build a Python research and paper-trading system for an Interactive Brokers paper account.

Initial strategy idea:

- 15-minute Opening Range Breakout on US equities.
- VWAP confirmation.
- Failed-breakout mean-reversion reversal logic.
- Research first, then read-only paper signals, then paper orders only after validation.

Important user preference:

- First priority was connecting to IBKR paper TWS.
- TWS paper socket port is `7497`.
- IB Gateway is optional and was not confirmed by the user.
- Current work should stay paper-only and read-only unless explicitly changed later.

## Current implementation state

Implemented infrastructure includes:

- IBKR connection checks.
- Historical data probe and range downloader.
- Local SQLite data cache.
- NVDA cached 5-minute RTH bars from `2026-01-01` through `2026-05-14`.
- Lightweight canvas HTML chart renderer using compressed market time.
- ORB + VWAP continuation, failed-breakout reversal, and hybrid backtests.
- Parameter sweep reports.
- Exit-policy / R analysis.
- Final reject/accept strategy review.

Useful commands:

```powershell
cd C:\develop\MonoRepoIdeas\projects\trading_strategy_tester
py -m unittest discover -s tests
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml
py scripts\run_final_strategy_review.py --symbol NVDA --start 2026-01-01 --end 2026-05-14 --bar-size "5 mins" --cost-bps 5
```

## Data notes

- Cached DB: `storage/trading_strategy_tester.sqlite3`
- The DB is local and ignored by git.
- NVDA bars used for the research:
  - bar size: `5 mins`
  - source: IBKR historical data
  - regular trading hours
  - first cached bar: `20260102  15:30:00`
  - last cached bar: `20260514  15:50:00`
  - unique cached bars: `7103`

## Final strategy verdict

The current ORB + VWAP / failed-breakout rule set was rejected as a deployable trading candidate.

Reason:

- Best in-sample candidate: `continuation_0.80R`
- Best in-sample gross PnL: `20.66` per share
- Best in-sample net PnL after `5 bps`: `12.24` per share
- Walk-forward gross PnL: `-0.53` per share
- Walk-forward net PnL after `5 bps`: `-5.39` per share
- Positive walk-forward windows: `1` / `3`
- Top five winners explain roughly the whole in-sample profit.
- Buy-and-hold dominates this NVDA sample.

Decision:

- Do not move this strategy to paper order execution.
- Keep the project infrastructure.
- Discard this specific rule set unless a new version passes walk-forward validation.

## Key reports

- `artifacts/reports/nvda_5min_rth_2026-01-01_2026-05-14.html`
- `artifacts/reports/nvda_orb_vwap_research_notes_2026-01-01_2026-05-14.md`
- `artifacts/reports/nvda_exit_policy_analysis_2026-01-01_2026-05-14.md`
- `artifacts/reports/nvda_final_strategy_review_2026-01-01_2026-05-14.md`
- `artifacts/reports/nvda_final_strategy_candidates_2026-01-01_2026-05-14.csv`
- `artifacts/reports/nvda_final_strategy_walk_forward_2026-01-01_2026-05-14.csv`

## What to do next

Do not keep tuning only `R` targets for the rejected strategy.

Next useful research direction:

1. Build a different entry filter or regime classifier.
2. Test whether ORB only works in specific regimes:
   - gap-and-go days
   - high first-15-minute relative volume
   - SPY/QQQ alignment
   - strong VWAP slope
   - specific OR width buckets
3. Run the same final review:
   - candidate comparison
   - cost stress
   - walk-forward validation
   - benchmark comparison
4. Only then consider read-only paper signal mode.

## Safety rules

- Never hardcode account numbers.
- Never assume live trading is allowed.
- Keep `trading_enabled = false` by default.
- Do not place orders if market data is delayed unless explicitly configured for testing.
- Reconcile positions and open orders before any future paper-order work.
