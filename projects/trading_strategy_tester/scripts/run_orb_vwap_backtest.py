"""Run the baseline ORB + VWAP continuation backtest from cached bars."""

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

from trading_strategy_tester.backtest.orb_vwap import (
    MODE_CONTINUATION,
    MODE_HYBRID,
    MODE_REVERSAL,
    run_orb_vwap_backtest,
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
    parser.add_argument("--opening-range-bars", default=3, type=int)
    parser.add_argument("--full-session-bars", default=78, type=int)
    parser.add_argument("--target-r", default=1.0, type=float)
    parser.add_argument("--include-partial-sessions", action="store_true")
    parser.add_argument(
        "--mode",
        default=MODE_CONTINUATION,
        choices=[MODE_CONTINUATION, MODE_REVERSAL, MODE_HYBRID],
    )
    parser.add_argument("--hold-bars", default=1, type=int)
    parser.add_argument("--vwap-slope-lookback", default=0, type=int)
    parser.add_argument("--vwap-slope-min", default=0.0, type=float)
    parser.add_argument("--max-vwap-distance-or-width", type=float)
    parser.add_argument("--min-or-width-bps", default=0.0, type=float)
    parser.add_argument("--max-or-width-bps", type=float)
    parser.add_argument("--max-failure-bars", default=3, type=int)
    parser.add_argument("--wick-ratio-threshold", default=0.0, type=float)
    parser.add_argument(
        "--reversal-target-mode",
        default="OR_MID",
        choices=["OR_MID", "VWAP", "OPPOSITE_OR"],
    )
    parser.add_argument("--long-only", action="store_true")
    parser.add_argument("--short-only", action="store_true")
    parser.add_argument(
        "--cache",
        default=PROJECT_ROOT / "storage" / "trading_strategy_tester.sqlite3",
        type=Path,
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Markdown report output path.",
    )
    parser.add_argument(
        "--trades-csv",
        type=Path,
        help="CSV trade log output path.",
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

    result = run_orb_vwap_backtest(
        bars,
        opening_range_bars=args.opening_range_bars,
        full_session_bars=args.full_session_bars,
        target_r=args.target_r,
        include_partial_sessions=args.include_partial_sessions,
        mode=args.mode,
        hold_bars=args.hold_bars,
        vwap_slope_lookback=args.vwap_slope_lookback,
        vwap_slope_min=args.vwap_slope_min,
        max_vwap_distance_or_width=args.max_vwap_distance_or_width,
        min_or_width_bps=args.min_or_width_bps,
        max_or_width_bps=args.max_or_width_bps,
        max_failure_bars=args.max_failure_bars,
        wick_ratio_threshold=args.wick_ratio_threshold,
        reversal_target_mode=args.reversal_target_mode,
        allow_long=not args.short_only,
        allow_short=not args.long_only,
    )
    summary = summarize_trades(result.trades)

    report_path = args.report or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_{args.mode}_{args.start}_{args.end}.md"
    )
    trades_csv = args.trades_csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_{args.mode}_trades_{args.start}_{args.end}.csv"
    )
    write_markdown_report(
        report_path=report_path,
        symbol=args.symbol.upper(),
        start=args.start,
        end=args.end,
        bar_size=args.bar_size,
        opening_range_bars=args.opening_range_bars,
        full_session_bars=args.full_session_bars,
        target_r=args.target_r,
        mode=args.mode,
        hold_bars=args.hold_bars,
        vwap_slope_lookback=args.vwap_slope_lookback,
        vwap_slope_min=args.vwap_slope_min,
        max_vwap_distance_or_width=args.max_vwap_distance_or_width,
        min_or_width_bps=args.min_or_width_bps,
        max_or_width_bps=args.max_or_width_bps,
        max_failure_bars=args.max_failure_bars,
        wick_ratio_threshold=args.wick_ratio_threshold,
        reversal_target_mode=args.reversal_target_mode,
        trades_csv_name=trades_csv.name,
        result=result,
        summary=summary,
    )
    write_trades_csv(trades_csv, result.trades)

    print(f"sessions_tested: {result.sessions_tested}")
    print(f"incomplete_sessions_skipped: {result.incomplete_sessions_skipped}")
    print(f"trade_count: {summary['trade_count']}")
    print(f"orb_vwap_gross_pnl_per_share: {summary['gross_pnl_per_share']:.4f}")
    print(f"orb_vwap_average_r: {summary['average_r']:.4f}")
    print(f"buy_hold_pnl_per_share: {result.buy_and_hold.pnl_per_share:.4f}")
    print(f"buy_hold_return_pct: {result.buy_and_hold.return_pct:.2%}")
    print(f"daily_open_close_long_pnl_per_share: {result.daily_open_close_long.pnl_per_share:.4f}")
    print(f"daily_after_or_long_pnl_per_share: {result.daily_after_or_long.pnl_per_share:.4f}")
    print(f"report: {report_path}")
    print(f"trades_csv: {trades_csv}")
    return 0


def write_markdown_report(
    report_path: Path,
    symbol: str,
    start: date,
    end: date,
    bar_size: str,
    opening_range_bars: int,
    full_session_bars: int,
    target_r: float,
    mode: str,
    hold_bars: int,
    vwap_slope_lookback: int,
    vwap_slope_min: float,
    max_vwap_distance_or_width: float | None,
    min_or_width_bps: float,
    max_or_width_bps: float | None,
    max_failure_bars: int,
    wick_ratio_threshold: float,
    reversal_target_mode: str,
    trades_csv_name: str,
    result,
    summary: dict[str, float | int],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    buy_hold = result.buy_and_hold
    win_rate = float(summary["win_rate"])
    exit_counts = {}
    for trade in result.trades:
        exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1
    strategy_pnl = float(summary["gross_pnl_per_share"])
    benchmark_gap = strategy_pnl - buy_hold.pnl_per_share
    comparison_note = (
        "This candidate outperformed buy-and-hold on gross per-share PnL."
        if benchmark_gap > 0
        else "This candidate underperformed buy-and-hold on gross per-share PnL."
    )
    lines = [
        f"# {symbol} ORB + VWAP {mode} backtest",
        "",
        "## Scope",
        "",
        f"- Symbol: `{symbol}`",
        f"- Cached bar size: `{bar_size}`",
        f"- Requested range: `{start}` through `{end}`",
        f"- Opening range: first `{opening_range_bars}` bars, equivalent to 15 minutes on 5-minute data",
        f"- Full session definition: `{full_session_bars}` RTH bars",
        f"- Target: `{target_r:.2f}R`",
        f"- Mode: `{mode}`",
        f"- Hold bars: `{hold_bars}`",
        f"- VWAP slope lookback: `{vwap_slope_lookback}`",
        f"- VWAP slope min: `{vwap_slope_min}`",
        f"- Max distance from VWAP in OR widths: `{max_vwap_distance_or_width}`",
        f"- OR width bps filter: `{min_or_width_bps}` to `{max_or_width_bps}`",
        f"- Max failure bars: `{max_failure_bars}`",
        f"- Wick ratio threshold: `{wick_ratio_threshold}`",
        f"- Reversal target mode: `{reversal_target_mode}`",
        "- Entry: next bar open after close breaks OR boundary and aligns with VWAP",
        "- Long filter: signal close > OR High and signal close > VWAP",
        "- Short filter: signal close < OR Low and signal close < VWAP",
        "- Stop: opposite opening-range boundary",
        "- Same-bar stop/target conflict: stop wins",
        "- Max trades: one trade per day",
        "- Costs/slippage: not included in this first baseline",
        "- Incomplete sessions: excluded from performance",
        "",
        "## Results",
        "",
        f"- Complete sessions tested: `{result.sessions_tested}`",
        f"- Sessions with no valid trade: `{result.sessions_skipped}`",
        f"- Incomplete sessions skipped: `{result.incomplete_sessions_skipped}`",
        f"- Trades: `{summary['trade_count']}`",
        f"- Long trades: `{summary['long_count']}`",
        f"- Short trades: `{summary['short_count']}`",
        f"- Continuation trades: `{summary['continuation_count']}`",
        f"- Reversal trades: `{summary['reversal_count']}`",
        f"- Win rate: `{win_rate:.2%}`",
        f"- Gross PnL per share: `{float(summary['gross_pnl_per_share']):.4f}`",
        f"- Average R: `{float(summary['average_r']):.4f}`",
        f"- Median R: `{float(summary['median_r']):.4f}`",
        f"- Max drawdown per share: `{float(summary['max_drawdown_per_share']):.4f}`",
        f"- Target exits: `{exit_counts.get('TARGET', 0)}`",
        f"- Stop exits: `{exit_counts.get('STOP', 0)}`",
        f"- Session-close exits: `{exit_counts.get('SESSION_CLOSE', 0)}`",
        "",
        "## Buy-and-hold benchmark",
        "",
        f"- Assumption: buy one share at first complete-window bar open and hold to final complete-window bar close",
        f"- Entry: `{buy_hold.entry_timestamp}` at `{buy_hold.entry_price:.4f}`",
        f"- Exit: `{buy_hold.exit_timestamp}` at `{buy_hold.exit_price:.4f}`",
        f"- PnL per share: `{buy_hold.pnl_per_share:.4f}`",
        f"- Return: `{buy_hold.return_pct:.2%}`",
        "",
        "## Intraday benchmarks",
        "",
        f"- Daily open-to-close long PnL per share: `{result.daily_open_close_long.pnl_per_share:.4f}`",
        f"- Daily open-to-close long win rate: `{result.daily_open_close_long.win_rate:.2%}`",
        f"- Daily after-opening-range long PnL per share: `{result.daily_after_or_long.pnl_per_share:.4f}`",
        f"- Daily after-opening-range long win rate: `{result.daily_after_or_long.win_rate:.2%}`",
        "",
        "## Comparison",
        "",
        f"- ORB + VWAP gross PnL per share: `{strategy_pnl:.4f}`",
        f"- Buy-and-hold PnL per share: `{buy_hold.pnl_per_share:.4f}`",
        f"- Strategy minus buy-and-hold: `{benchmark_gap:.4f}`",
        f"- Interpretation: {comparison_note}",
        "",
        "## First read",
        "",
        "This is still a research backtest, not a deployable trading system.",
        "Costs, slippage, and out-of-sample validation are not included yet.",
        "Use this report as a candidate generator before walk-forward validation.",
        "",
        "## Files",
        "",
        f"- Trade log CSV: `{trades_csv_name}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_trades_csv(path: Path, trades) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "session_date",
        "direction",
        "signal_timestamp",
        "entry_timestamp",
        "exit_timestamp",
        "entry_price",
        "exit_price",
        "stop_price",
        "target_price",
        "risk_per_share",
        "pnl_per_share",
        "r_multiple",
        "exit_reason",
        "or_high",
        "or_low",
        "vwap_at_signal",
        "setup_type",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            writer.writerow({field: getattr(trade, field) for field in fieldnames})


if __name__ == "__main__":
    raise SystemExit(main())
