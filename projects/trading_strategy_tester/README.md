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

Expected local paper ports:

- TWS paper: `127.0.0.1:7497`
- IB Gateway paper: `127.0.0.1:4002`

The first version is read-only by default. `trading_enabled` must remain `false` until read-only signal mode is verified.

## Structure

- `docs/` local project documentation
- `config/` YAML configuration
- `src/` source code
- `tests/` automated checks
- `artifacts/` reports and outputs
