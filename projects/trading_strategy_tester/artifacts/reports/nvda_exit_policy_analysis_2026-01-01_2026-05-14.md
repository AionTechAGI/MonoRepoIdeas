# NVDA exit policy and R analysis

- Range: `2026-01-01` through `2026-05-14`
- Entries analyzed: `89`
- Entry signal: first ORB + VWAP continuation signal per complete session
- Costs/slippage: not included

## MFE / MAE

- Average MFE: `0.784R`
- Median MFE: `0.690R`
- Average MAE: `0.763R`
- Median MAE: `0.531R`
- Trades reaching at least 0.75R: `43` / `89`
- Trades reaching at least 1.00R: `25` / `89`
- Trades reaching at least 1.50R: `11` / `89`
- Trades reaching at least 2.00R: `5` / `89`

## Exit policy comparison

| Rank | Policy | PnL/share | Avg R | Median R | Max DD/share | Win Rate | Stops | Targets/Partials | Session Close | Avg MFE | Avg MAE |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | fixed_0.80R | 20.66 | 0.090 | 0.348 | 12.25 | 59.6% | 22 | 41 | 26 | 0.78 | 0.76 |
| 2 | fixed_0.75R | 20.03 | 0.094 | 0.496 | 12.25 | 60.7% | 21 | 43 | 25 | 0.78 | 0.76 |
| 3 | partial_80pct_0.75R_then_vwap_trail | 17.00 | 0.079 | 0.496 | 12.25 | 60.7% | 35 | 43 | 0 | 0.78 | 0.76 |
| 4 | partial_80pct_0.75R_then_breakeven_session_close | 16.98 | 0.078 | 0.496 | 12.25 | 60.7% | 39 | 43 | 0 | 0.78 | 0.76 |
| 5 | partial_70pct_0.75R_then_vwap_trail | 15.48 | 0.072 | 0.496 | 12.25 | 60.7% | 35 | 43 | 0 | 0.78 | 0.76 |
| 6 | partial_70pct_0.75R_then_breakeven_session_close | 15.45 | 0.070 | 0.496 | 12.25 | 60.7% | 39 | 43 | 0 | 0.78 | 0.76 |
| 7 | fixed_0.50R | 15.13 | 0.077 | 0.500 | 10.00 | 67.4% | 16 | 55 | 18 | 0.78 | 0.76 |
| 8 | fixed_0.70R | 14.63 | 0.071 | 0.496 | 12.25 | 60.7% | 21 | 44 | 24 | 0.78 | 0.76 |
| 9 | fixed_0.60R | 14.13 | 0.071 | 0.600 | 12.25 | 64.0% | 19 | 49 | 21 | 0.78 | 0.76 |
| 10 | partial_50pct_0.75R_then_vwap_trail | 12.45 | 0.057 | 0.375 | 12.25 | 60.7% | 35 | 43 | 0 | 0.78 | 0.76 |
| 11 | partial_50pct_0.75R_then_breakeven_session_close | 12.40 | 0.055 | 0.375 | 12.25 | 60.7% | 39 | 43 | 0 | 0.78 | 0.76 |
| 12 | partial_50pct_0.75R_then_session_close | 12.36 | 0.055 | 0.146 | 12.25 | 55.1% | 26 | 43 | 0 | 0.78 | 0.76 |
| 13 | fixed_0.90R | 10.62 | 0.049 | 0.177 | 12.25 | 57.3% | 23 | 29 | 37 | 0.78 | 0.76 |
| 14 | fixed_1.25R | 9.90 | 0.030 | 0.080 | 12.25 | 55.1% | 25 | 16 | 48 | 0.78 | 0.76 |
| 15 | fixed_1.00R | 9.77 | 0.040 | 0.120 | 12.25 | 56.2% | 24 | 25 | 40 | 0.78 | 0.76 |
| 16 | trail_1.00R_from_high_low | 9.63 | 0.048 | -0.063 | 11.25 | 49.4% | 0 | 0 | 43 | 0.78 | 0.76 |
| 17 | fixed_0.25R | 8.94 | 0.068 | 0.250 | 10.87 | 82.0% | 8 | 71 | 10 | 0.78 | 0.76 |
| 18 | fixed_1.50R | 6.68 | 0.021 | 0.080 | 12.46 | 55.1% | 25 | 11 | 53 | 0.78 | 0.76 |
| 19 | fixed_2.00R | 5.15 | 0.013 | 0.055 | 13.60 | 53.9% | 26 | 5 | 58 | 0.78 | 0.76 |
| 20 | session_close_runner | 4.70 | 0.017 | 0.055 | 12.84 | 53.9% | 26 | 0 | 63 | 0.78 | 0.76 |
| 21 | trail_1.50R_from_high_low | 1.88 | 0.004 | 0.003 | 19.09 | 51.7% | 0 | 0 | 57 | 0.78 | 0.76 |

## Readout

- Best fixed target: `fixed_0.80R` with `20.66` gross PnL/share and `59.6%` win rate.
- Best partial-runner policy: `partial_80pct_0.75R_then_vwap_trail` with `17.00` gross PnL/share.
- Session-close runner with the original stop remains behind fixed targets: `4.70` gross PnL/share.

## First read

Fixed R targets show how much profit is available before reversals.
Partial exits test whether the strategy can bank the common move while leaving a runner.
Trailing policies test whether winners can run without giving back too much.
This is still in-sample and should feed walk-forward validation, not deployment.
