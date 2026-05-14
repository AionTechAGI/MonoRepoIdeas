"""Run a compact ORB + VWAP parameter sweep from cached bars."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import date
from itertools import product
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.backtest.orb_vwap import (
    MODE_CONTINUATION,
    MODE_HYBRID,
    MODE_REVERSAL,
    BacktestConfig,
    run_orb_vwap_backtest_with_config,
    summarize_trades,
)
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
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Sweep CSV output path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Sweep markdown report path.",
    )
    args = parser.parse_args()

    bars = filter_bars_by_date(
        read_bars(args.cache, args.symbol, args.bar_size),
        args.start,
        args.end,
    )
    if not bars:
        print("ERROR: no cached bars found for requested range")
        return 1

    rows = []
    for config in build_parameter_grid(args.full_session_bars):
        result = run_orb_vwap_backtest_with_config(bars, config)
        summary = summarize_trades(result.trades)
        rows.append(
            {
                **asdict(config),
                "sessions_tested": result.sessions_tested,
                "sessions_skipped": result.sessions_skipped,
                "trade_count": summary["trade_count"],
                "win_rate": summary["win_rate"],
                "gross_pnl_per_share": summary["gross_pnl_per_share"],
                "average_r": summary["average_r"],
                "median_r": summary["median_r"],
                "max_drawdown_per_share": summary["max_drawdown_per_share"],
                "long_count": summary["long_count"],
                "short_count": summary["short_count"],
                "continuation_count": summary["continuation_count"],
                "reversal_count": summary["reversal_count"],
                "buy_hold_pnl_per_share": result.buy_and_hold.pnl_per_share,
                "daily_open_close_long_pnl_per_share": result.daily_open_close_long.pnl_per_share,
                "daily_after_or_long_pnl_per_share": result.daily_after_or_long.pnl_per_share,
            }
        )

    rows.sort(
        key=lambda row: (
            float(row["gross_pnl_per_share"]),
            float(row["average_r"]),
            -float(row["max_drawdown_per_share"]),
        ),
        reverse=True,
    )

    csv_path = args.output_csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_sweep_{args.start}_{args.end}.csv"
    )
    report_path = args.report or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_sweep_{args.start}_{args.end}.md"
    )
    write_sweep_csv(csv_path, rows)
    write_sweep_report(report_path, args.symbol.upper(), args.start, args.end, rows)

    top = rows[0]
    print(f"parameter_sets: {len(rows)}")
    print(f"top_mode: {top['mode']}")
    print(f"top_gross_pnl_per_share: {float(top['gross_pnl_per_share']):.4f}")
    print(f"top_average_r: {float(top['average_r']):.4f}")
    print(f"top_trade_count: {top['trade_count']}")
    print(f"csv: {csv_path}")
    print(f"report: {report_path}")
    return 0


def build_parameter_grid(full_session_bars: int) -> list[BacktestConfig]:
    configs: list[BacktestConfig] = []
    for (
        mode,
        target_r,
        hold_bars,
        vwap_slope_lookback,
        max_vwap_distance,
        min_or_width_bps,
        max_failure_bars,
        wick_ratio_threshold,
        reversal_target_mode,
    ) in product(
        [MODE_CONTINUATION, MODE_REVERSAL, MODE_HYBRID],
        [0.75, 1.0, 1.5, 2.0],
        [1, 2],
        [0, 3],
        [None, 1.0, 2.0],
        [0.0, 40.0],
        [2, 3, 5],
        [0.0, 0.4],
        ["OR_MID", "VWAP"],
    ):
        if mode == MODE_CONTINUATION and (
            max_failure_bars != 2
            or wick_ratio_threshold != 0.0
            or reversal_target_mode != "OR_MID"
        ):
            continue
        configs.append(
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=mode,
                target_r=target_r,
                hold_bars=hold_bars,
                vwap_slope_lookback=vwap_slope_lookback,
                max_vwap_distance_or_width=max_vwap_distance,
                min_or_width_bps=min_or_width_bps,
                max_failure_bars=max_failure_bars,
                wick_ratio_threshold=wick_ratio_threshold,
                reversal_target_mode=reversal_target_mode,
            )
        )
    return configs


def write_sweep_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_sweep_report(
    path: Path,
    symbol: str,
    start: date,
    end: date,
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = rows[:20]
    lines = [
        f"# {symbol} ORB + VWAP parameter sweep",
        "",
        f"- Range: `{start}` through `{end}`",
        f"- Parameter sets: `{len(rows)}`",
        "- Costs/slippage: not included",
        "- Purpose: quick in-sample research screen before walk-forward validation",
        "",
        "## Top 20 by gross PnL per share",
        "",
        "| Rank | Mode | PnL/share | Avg R | Max DD/share | Trades | Win Rate | Hold | Target R | VWAP slope | Max VWAP dist | OR min bps | Failure bars | Wick | Reversal target |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(top_rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    str(row["mode"]),
                    f"{float(row['gross_pnl_per_share']):.2f}",
                    f"{float(row['average_r']):.3f}",
                    f"{float(row['max_drawdown_per_share']):.2f}",
                    str(row["trade_count"]),
                    f"{float(row['win_rate']):.1%}",
                    str(row["hold_bars"]),
                    str(row["target_r"]),
                    str(row["vwap_slope_lookback"]),
                    str(row["max_vwap_distance_or_width"]),
                    str(row["min_or_width_bps"]),
                    str(row["max_failure_bars"]),
                    str(row["wick_ratio_threshold"]),
                    str(row["reversal_target_mode"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "This sweep is intentionally in-sample. Do not treat the best row as deployable.",
            "The next step is to take stable clusters from the top rows into walk-forward validation.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
