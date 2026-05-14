"""Analyze R targets, partial exits, and trailing stops for ORB/VWAP entries."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.backtest.exit_analysis import (
    collect_continuation_entries,
    default_exit_policies,
    simulate_exit_policies,
    summarize_mfe_mae,
)
from trading_strategy_tester.backtest.orb_vwap import BacktestConfig
from trading_strategy_tester.data.data_cache import read_bars
from trading_strategy_tester.data.range_downloader import filter_bars_by_date


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--bar-size", default="5 mins")
    parser.add_argument("--full-session-bars", default=78, type=int)
    parser.add_argument(
        "--cache",
        default=PROJECT_ROOT / "storage" / "trading_strategy_tester.sqlite3",
        type=Path,
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    bars = filter_bars_by_date(
        read_bars(args.cache, args.symbol, args.bar_size),
        args.start,
        args.end,
    )
    if not bars:
        print("ERROR: no cached bars found for requested range")
        return 1

    config = BacktestConfig(full_session_bars=args.full_session_bars)
    entries = collect_continuation_entries(bars, config)
    mfe_summary = summarize_mfe_mae(entries)
    policy_rows = simulate_exit_policies(entries, default_exit_policies())

    report_path = args.report or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_exit_policy_analysis_{args.start}_{args.end}.md"
    )
    csv_path = args.csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_exit_policy_analysis_{args.start}_{args.end}.csv"
    )
    write_policy_csv(csv_path, policy_rows)
    write_report(report_path, args.symbol.upper(), args.start, args.end, mfe_summary, policy_rows)

    top = policy_rows[0]
    print(f"entries: {mfe_summary['entry_count']}")
    print(f"top_policy: {top['policy']}")
    print(f"top_gross_pnl_per_share: {float(top['gross_pnl_per_share']):.4f}")
    print(f"top_average_r: {float(top['average_r']):.4f}")
    print(f"report: {report_path}")
    print(f"csv: {csv_path}")
    return 0


def write_policy_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    path: Path,
    symbol: str,
    start: date,
    end: date,
    mfe_summary: dict[str, float | int],
    policy_rows: list[dict[str, float | int | str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry_count = int(mfe_summary["entry_count"])
    best_fixed = next(
        (row for row in policy_rows if str(row["policy"]).startswith("fixed_")),
        None,
    )
    best_partial = next(
        (row for row in policy_rows if str(row["policy"]).startswith("partial_")),
        None,
    )
    session_runner = next(
        (row for row in policy_rows if row["policy"] == "session_close_runner"),
        None,
    )
    lines = [
        f"# {symbol} exit policy and R analysis",
        "",
        f"- Range: `{start}` through `{end}`",
        f"- Entries analyzed: `{entry_count}`",
        "- Entry signal: first ORB + VWAP continuation signal per complete session",
        "- Costs/slippage: not included",
        "",
        "## MFE / MAE",
        "",
        f"- Average MFE: `{float(mfe_summary['average_mfe_r']):.3f}R`",
        f"- Median MFE: `{float(mfe_summary['median_mfe_r']):.3f}R`",
        f"- Average MAE: `{float(mfe_summary['average_mae_r']):.3f}R`",
        f"- Median MAE: `{float(mfe_summary['median_mae_r']):.3f}R`",
        f"- Trades reaching at least 0.75R: `{mfe_summary['mfe_ge_0_75r']}` / `{entry_count}`",
        f"- Trades reaching at least 1.00R: `{mfe_summary['mfe_ge_1r']}` / `{entry_count}`",
        f"- Trades reaching at least 1.50R: `{mfe_summary['mfe_ge_1_5r']}` / `{entry_count}`",
        f"- Trades reaching at least 2.00R: `{mfe_summary['mfe_ge_2r']}` / `{entry_count}`",
        "",
        "## Exit policy comparison",
        "",
        "| Rank | Policy | PnL/share | Avg R | Median R | Max DD/share | Win Rate | Stops | Targets/Partials | Session Close | Avg MFE | Avg MAE |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(policy_rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    str(row["policy"]),
                    f"{float(row['gross_pnl_per_share']):.2f}",
                    f"{float(row['average_r']):.3f}",
                    f"{float(row['median_r']):.3f}",
                    f"{float(row['max_drawdown_per_share']):.2f}",
                    f"{float(row['win_rate']):.1%}",
                    str(row["stop_count"]),
                    str(row["target_or_partial_count"]),
                    str(row["session_close_count"]),
                    f"{float(row['average_mfe_r']):.2f}",
                    f"{float(row['average_mae_r']):.2f}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Readout",
            "",
        ]
    )
    if best_fixed is not None:
        lines.append(
            "- Best fixed target: "
            f"`{best_fixed['policy']}` with `{float(best_fixed['gross_pnl_per_share']):.2f}` "
            f"gross PnL/share and `{float(best_fixed['win_rate']):.1%}` win rate."
        )
    if best_partial is not None:
        lines.append(
            "- Best partial-runner policy: "
            f"`{best_partial['policy']}` with `{float(best_partial['gross_pnl_per_share']):.2f}` "
            "gross PnL/share."
        )
    if session_runner is not None:
        lines.append(
            "- Session-close runner with the original stop remains behind fixed targets: "
            f"`{float(session_runner['gross_pnl_per_share']):.2f}` gross PnL/share."
        )
    lines.extend(
        [
            "",
            "## First read",
            "",
            "Fixed R targets show how much profit is available before reversals.",
            "Partial exits test whether the strategy can bank the common move while leaving a runner.",
            "Trailing policies test whether winners can run without giving back too much.",
            "This is still in-sample and should feed walk-forward validation, not deployment.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
