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
    )
    summary = summarize_trades(result.trades)

    report_path = args.report or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_baseline_{args.start}_{args.end}.md"
    )
    trades_csv = args.trades_csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_orb_vwap_baseline_trades_{args.start}_{args.end}.csv"
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
    lines = [
        f"# {symbol} ORB + VWAP baseline backtest",
        "",
        "## Scope",
        "",
        f"- Symbol: `{symbol}`",
        f"- Cached bar size: `{bar_size}`",
        f"- Requested range: `{start}` through `{end}`",
        f"- Opening range: first `{opening_range_bars}` bars, equivalent to 15 minutes on 5-minute data",
        f"- Full session definition: `{full_session_bars}` RTH bars",
        f"- Target: `{target_r:.2f}R`",
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
        "## Comparison",
        "",
        f"- ORB + VWAP gross PnL per share: `{strategy_pnl:.4f}`",
        f"- Buy-and-hold PnL per share: `{buy_hold.pnl_per_share:.4f}`",
        f"- Strategy minus buy-and-hold: `{benchmark_gap:.4f}`",
        "- Interpretation: this unoptimized continuation baseline underperformed buy-and-hold on this NVDA sample.",
        "",
        "## First read",
        "",
        "This is a baseline continuation test, not an optimized strategy.",
        "It is useful as the control case before adding failed-breakout reversal logic.",
        "Next research step: inspect days where continuation stopped out and test whether failed-breakout reversal improves those cases.",
        "",
        "## Files",
        "",
        f"- Trade log CSV: `{report_path.with_name(report_path.stem.replace('baseline', 'baseline_trades') + '.csv').name}`",
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
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            writer.writerow({field: getattr(trade, field) for field in fieldnames})


if __name__ == "__main__":
    raise SystemExit(main())
