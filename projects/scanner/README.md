# Scanner

`Scanner` is the valuation and market research app migrated from the original `stock_valuation_lab` folder.

## What it does

- single-stock valuation
- external fair-value collection
- point-in-time screening
- forward backtesting
- report generation

## Quick start

```powershell
cd C:\develop\MonoRepoIdeas\projects\scanner
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

You can also use:

```powershell
cd C:\develop\MonoRepoIdeas\projects\scanner
.\run_scanner.bat
```

## Tests

```powershell
cd C:\develop\MonoRepoIdeas\projects\scanner
py -m unittest discover -s tests
```

## Structure

- `app.py` Streamlit entrypoint
- `src/` valuation, data-source, and backtest modules
- `tests/` unit tests
- `docs/` methodology and limitation notes
- `artifacts/reports/` saved HTML and markdown outputs

## Notes

- `requirements.txt` is still the current dependency file.
- A later migration may move this project to `pyproject.toml`, but that is not part of this structural pass.
