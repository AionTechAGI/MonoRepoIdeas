# AGENTS.md

## Project Expectations
- Use this project for trading strategy research, backtesting, and reporting.
- Keep repo-wide rules in `C:\develop\MonoRepoIdeas\AGENTS.md`.
- Keep assumptions explicit: data source, bar frequency, signal timing, execution timing, costs, slippage, position sizing, and benchmark.
- Avoid look-ahead bias. Signals must use only information available before the simulated execution time.
- Keep generated reports and exported datasets in `artifacts/` or `outputs/`, not in the project root.
- Update `README.md` when adding install, run, or test commands.

## Validation
- No local validation command exists yet.
- Add and document tests before introducing strategy logic with meaningful behavior.
