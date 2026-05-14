# AGENTS.md

## Project Expectations
- Use this project for trading strategy research, backtesting, and reporting.
- Keep repo-wide rules in `C:\develop\MonoRepoIdeas\AGENTS.md`.
- Keep assumptions explicit: data source, bar frequency, signal timing, execution timing, costs, slippage, position sizing, and benchmark.
- Avoid look-ahead bias. Signals must use only information available before the simulated execution time.
- IBKR connection code must default to paper-only and read-only. Do not allow live trading in the first version.
- Do not hardcode account numbers or symbols. Use `config/ibkr_config.yaml` and `config/instruments.yaml`.
- Keep generated reports and exported datasets in `artifacts/` or `outputs/`, not in the project root.
- Update `README.md` when adding install, run, or test commands.

## Validation
- Install dependencies with `py -m pip install -r requirements.txt`.
- Run tests with `py -m unittest discover -s tests`.
- Check paper connectivity with `py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml`.
