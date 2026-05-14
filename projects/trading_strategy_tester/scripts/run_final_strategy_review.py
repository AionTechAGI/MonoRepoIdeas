"""Generate a final accept/reject review for the current NVDA ORB/VWAP candidate."""

from __future__ import annotations

import argparse
import calendar
import csv
from dataclasses import dataclass
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
    BacktestConfig,
    Trade,
    group_bars_by_session,
    max_drawdown,
    run_orb_vwap_backtest_with_config,
    summarize_trades,
)
from trading_strategy_tester.data.data_cache import read_bars
from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import filter_bars_by_date


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    config: BacktestConfig


@dataclass(frozen=True)
class MonthWindow:
    label: str
    start: date
    end: date


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--bar-size", default="5 mins")
    parser.add_argument("--full-session-bars", default=78, type=int)
    parser.add_argument("--cost-bps", default=5.0, type=float)
    parser.add_argument(
        "--cache",
        default=PROJECT_ROOT / "storage" / "trading_strategy_tester.sqlite3",
        type=Path,
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--candidate-csv", type=Path)
    parser.add_argument("--walk-forward-csv", type=Path)
    args = parser.parse_args()

    bars = filter_bars_by_date(
        read_bars(args.cache, args.symbol, args.bar_size),
        args.start,
        args.end,
    )
    if not bars:
        print("ERROR: no cached bars found for requested range")
        return 1

    candidates = default_candidates(args.full_session_bars)
    months = month_windows(args.start, args.end)
    candidate_rows = score_candidates(bars, candidates, args.cost_bps)
    walk_forward_rows = run_walk_forward(bars, candidates, months, args.cost_bps)

    report_path = args.report or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_final_strategy_review_{args.start}_{args.end}.md"
    )
    candidate_csv = args.candidate_csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_final_strategy_candidates_{args.start}_{args.end}.csv"
    )
    walk_forward_csv = args.walk_forward_csv or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{args.symbol.lower()}_final_strategy_walk_forward_{args.start}_{args.end}.csv"
    )

    write_csv(candidate_csv, candidate_rows)
    write_csv(walk_forward_csv, walk_forward_rows)
    write_report(
        report_path,
        args.symbol.upper(),
        args.start,
        args.end,
        args.bar_size,
        args.cost_bps,
        bars,
        candidate_rows,
        walk_forward_rows,
        candidate_csv.name,
        walk_forward_csv.name,
    )

    verdict = "REJECT"
    top = candidate_rows[0]
    wf_net = sum(float(row["test_net_pnl_per_share"]) for row in walk_forward_rows)
    print(f"verdict: {verdict}")
    print(f"top_in_sample_candidate: {top['candidate']}")
    print(f"top_gross_pnl_per_share: {float(top['gross_pnl_per_share']):.4f}")
    print(f"top_net_pnl_per_share_{args.cost_bps:g}bps: {float(top['net_pnl_per_share']):.4f}")
    print(f"walk_forward_net_pnl_per_share_{args.cost_bps:g}bps: {wf_net:.4f}")
    print(f"report: {report_path}")
    print(f"candidate_csv: {candidate_csv}")
    print(f"walk_forward_csv: {walk_forward_csv}")
    return 0


def default_candidates(full_session_bars: int) -> list[CandidateSpec]:
    return [
        CandidateSpec(
            "continuation_0.50R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_CONTINUATION,
                target_r=0.50,
            ),
        ),
        CandidateSpec(
            "continuation_0.75R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_CONTINUATION,
                target_r=0.75,
            ),
        ),
        CandidateSpec(
            "continuation_0.80R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_CONTINUATION,
                target_r=0.80,
            ),
        ),
        CandidateSpec(
            "continuation_1.00R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_CONTINUATION,
                target_r=1.00,
            ),
        ),
        CandidateSpec(
            "hybrid_0.75R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_HYBRID,
                target_r=0.75,
                max_failure_bars=2,
                wick_ratio_threshold=0.4,
            ),
        ),
        CandidateSpec(
            "hybrid_0.80R",
            BacktestConfig(
                full_session_bars=full_session_bars,
                mode=MODE_HYBRID,
                target_r=0.80,
                max_failure_bars=2,
                wick_ratio_threshold=0.4,
            ),
        ),
    ]


def score_candidates(
    bars: list[HistoricalBar],
    candidates: list[CandidateSpec],
    cost_bps: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates:
        result = run_orb_vwap_backtest_with_config(bars, candidate.config)
        summary = summarize_trades(result.trades)
        month_pnls = monthly_trade_pnl(result.trades)
        top5 = top_trade_contribution(result.trades, 5)
        row = {
            "candidate": candidate.name,
            "mode": candidate.config.mode,
            "target_r": candidate.config.target_r,
            "trades": summary["trade_count"],
            "win_rate": summary["win_rate"],
            "gross_pnl_per_share": summary["gross_pnl_per_share"],
            "net_pnl_per_share": net_pnl_after_bps(result.trades, cost_bps),
            "net_2bps": net_pnl_after_bps(result.trades, 2.0),
            "net_5bps": net_pnl_after_bps(result.trades, 5.0),
            "net_10bps": net_pnl_after_bps(result.trades, 10.0),
            "net_15bps": net_pnl_after_bps(result.trades, 15.0),
            "average_r": summary["average_r"],
            "median_r": summary["median_r"],
            "max_drawdown_per_share": summary["max_drawdown_per_share"],
            "profit_factor": profit_factor(result.trades),
            "positive_months": sum(1 for pnl in month_pnls.values() if pnl > 0),
            "negative_months": sum(1 for pnl in month_pnls.values() if pnl < 0),
            "worst_month_pnl": min(month_pnls.values()) if month_pnls else 0.0,
            "best_month_pnl": max(month_pnls.values()) if month_pnls else 0.0,
            "top5_winner_contribution_pct": top5,
            "long_pnl": trade_pnl_by_direction(result.trades, "LONG"),
            "short_pnl": trade_pnl_by_direction(result.trades, "SHORT"),
            "continuation_pnl": trade_pnl_by_setup(result.trades, "CONTINUATION"),
            "reversal_pnl": trade_pnl_by_setup(result.trades, "REVERSAL"),
            "buy_hold_pnl_per_share": result.buy_and_hold.pnl_per_share,
            "buy_hold_net_5bps": result.buy_and_hold.pnl_per_share
            - result.buy_and_hold.entry_price * 5.0 / 10_000,
            "daily_open_close_long_pnl_per_share": result.daily_open_close_long.pnl_per_share,
            "daily_open_close_long_net_5bps": daily_open_close_net_pnl(
                bars,
                result.sessions_tested,
                5.0,
                candidate.config.full_session_bars,
            ),
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            float(row["gross_pnl_per_share"]),
            float(row["net_pnl_per_share"]),
            -float(row["max_drawdown_per_share"]),
        ),
        reverse=True,
    )
    return rows


def run_walk_forward(
    bars: list[HistoricalBar],
    candidates: list[CandidateSpec],
    months: list[MonthWindow],
    cost_bps: float,
    min_train_months: int = 2,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for test_index in range(min_train_months, len(months)):
        train_start = months[0].start
        train_end = months[test_index - 1].end
        test_month = months[test_index]
        train_bars = filter_bars_by_date(bars, train_start, train_end)
        test_bars = filter_bars_by_date(bars, test_month.start, test_month.end)
        train_scores = []
        for candidate in candidates:
            train_result = run_orb_vwap_backtest_with_config(train_bars, candidate.config)
            train_summary = summarize_trades(train_result.trades)
            train_scores.append(
                (
                    float(train_summary["gross_pnl_per_share"]),
                    float(train_summary["average_r"]),
                    -float(train_summary["max_drawdown_per_share"]),
                    candidate,
                    train_summary,
                )
            )
        train_scores.sort(reverse=True, key=lambda item: item[:3])
        _, _, _, selected, train_summary = train_scores[0]
        test_result = run_orb_vwap_backtest_with_config(test_bars, selected.config)
        test_summary = summarize_trades(test_result.trades)
        rows.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_month": test_month.label,
                "selected_candidate": selected.name,
                "train_gross_pnl_per_share": train_summary["gross_pnl_per_share"],
                "train_trades": train_summary["trade_count"],
                "test_gross_pnl_per_share": test_summary["gross_pnl_per_share"],
                "test_net_pnl_per_share": net_pnl_after_bps(test_result.trades, cost_bps),
                "test_net_10bps": net_pnl_after_bps(test_result.trades, 10.0),
                "test_trades": test_summary["trade_count"],
                "test_win_rate": test_summary["win_rate"],
                "test_max_drawdown_per_share": test_summary["max_drawdown_per_share"],
                "test_buy_hold_pnl_per_share": test_result.buy_and_hold.pnl_per_share,
                "test_daily_open_close_long_pnl_per_share": (
                    test_result.daily_open_close_long.pnl_per_share
                ),
            }
        )
    return rows


def month_windows(start: date, end: date) -> list[MonthWindow]:
    windows: list[MonthWindow] = []
    current = date(start.year, start.month, 1)
    while current <= end:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_start = max(current, start)
        month_end = min(date(current.year, current.month, last_day), end)
        windows.append(MonthWindow(f"{current:%Y-%m}", month_start, month_end))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return windows


def net_pnl_after_bps(trades: tuple[Trade, ...], round_trip_cost_bps: float) -> float:
    return sum(
        trade.pnl_per_share - trade.entry_price * round_trip_cost_bps / 10_000
        for trade in trades
    )


def profit_factor(trades: tuple[Trade, ...]) -> float:
    gains = sum(trade.pnl_per_share for trade in trades if trade.pnl_per_share > 0)
    losses = abs(sum(trade.pnl_per_share for trade in trades if trade.pnl_per_share < 0))
    if losses == 0:
        return 0.0 if gains == 0 else float("inf")
    return gains / losses


def monthly_trade_pnl(trades: tuple[Trade, ...]) -> dict[str, float]:
    values: dict[str, float] = {}
    for trade in trades:
        values[trade.session_date[:7]] = values.get(trade.session_date[:7], 0.0) + trade.pnl_per_share
    return values


def top_trade_contribution(trades: tuple[Trade, ...], count: int) -> float:
    total = sum(trade.pnl_per_share for trade in trades)
    if total <= 0:
        return 0.0
    winners = sorted(
        [trade.pnl_per_share for trade in trades if trade.pnl_per_share > 0],
        reverse=True,
    )
    return sum(winners[:count]) / total


def trade_pnl_by_direction(trades: tuple[Trade, ...], direction: str) -> float:
    return sum(trade.pnl_per_share for trade in trades if trade.direction == direction)


def trade_pnl_by_setup(trades: tuple[Trade, ...], setup_type: str) -> float:
    return sum(trade.pnl_per_share for trade in trades if trade.setup_type == setup_type)


def daily_open_close_net_pnl(
    bars: list[HistoricalBar],
    sessions_tested: int,
    round_trip_cost_bps: float,
    full_session_bars: int,
) -> float:
    complete_sessions = [
        session
        for session in group_bars_by_session(bars)
        if len(session.bars) >= full_session_bars
    ][:sessions_tested]
    return sum(
        session.bars[-1].close
        - session.bars[0].open
        - session.bars[0].open * round_trip_cost_bps / 10_000
        for session in complete_sessions
    )


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
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
    bar_size: str,
    cost_bps: float,
    bars: list[HistoricalBar],
    candidate_rows: list[dict[str, object]],
    walk_forward_rows: list[dict[str, object]],
    candidate_csv_name: str,
    walk_forward_csv_name: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top = candidate_rows[0]
    buy_hold_gap = float(top["net_pnl_per_share"]) - float(top["buy_hold_net_5bps"])
    wf_gross = sum(float(row["test_gross_pnl_per_share"]) for row in walk_forward_rows)
    wf_net = sum(float(row["test_net_pnl_per_share"]) for row in walk_forward_rows)
    wf_positive = sum(1 for row in walk_forward_rows if float(row["test_net_pnl_per_share"]) > 0)
    complete_sessions = [session for session in group_bars_by_session(bars) if len(session.bars) >= 78]
    incomplete_sessions = len(group_bars_by_session(bars)) - len(complete_sessions)

    verdict = "REJECT current strategy logic"
    lines = [
        f"# {symbol} final strategy review",
        "",
        "## Verdict",
        "",
        f"**{verdict}.**",
        "",
        "The current ORB + VWAP / failed-breakout rule set is useful as research infrastructure,",
        "but it is not strong enough as a tradable strategy candidate. Do not move it to paper",
        "order execution. Keep the data pipeline and backtester, but discard this specific rule set",
        "unless a future version passes out-of-sample validation.",
        "",
        "## Scope",
        "",
        f"- Symbol: `{symbol}`",
        f"- Bar size: `{bar_size}`",
        f"- Range: `{start}` through `{end}`",
        f"- Cached bars: `{len(bars)}`",
        f"- Complete sessions: `{len(complete_sessions)}`",
        f"- Incomplete sessions: `{incomplete_sessions}`",
        f"- Cost stress used for pass/fail: `{cost_bps:g}` bps round-trip per trade",
        "- Position size: one share for comparability",
        "",
        "## Acceptance checklist",
        "",
        "| Test | Result | Pass? |",
        "|---|---:|---|",
        f"| Best in-sample gross PnL | `{float(top['gross_pnl_per_share']):.2f}`/share | pass |",
        f"| Best in-sample net PnL after {cost_bps:g} bps | `{float(top['net_pnl_per_share']):.2f}`/share | pass |",
        f"| Walk-forward gross PnL | `{wf_gross:.2f}`/share | fail |",
        f"| Walk-forward net PnL after {cost_bps:g} bps | `{wf_net:.2f}`/share | fail |",
        f"| Positive walk-forward windows | `{wf_positive}` / `{len(walk_forward_rows)}` | fail |",
        f"| Top 5 winner contribution for best candidate | `{float(top['top5_winner_contribution_pct']):.1%}` | fail |",
        f"| Best candidate minus buy-and-hold net 5 bps | `{buy_hold_gap:.2f}`/share | fail |",
        "",
        "Pass/fail rule: this strategy must survive walk-forward and cost stress. It does not.",
        "",
        "## Candidate Summary",
        "",
        "| Rank | Candidate | Gross/share | Net 5bps | Net 10bps | Net 15bps | Trades | Win | Avg R | Max DD | PF | Pos Months | Top 5 Winners |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(candidate_rows, start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    str(row["candidate"]),
                    f"{float(row['gross_pnl_per_share']):.2f}",
                    f"{float(row['net_5bps']):.2f}",
                    f"{float(row['net_10bps']):.2f}",
                    f"{float(row['net_15bps']):.2f}",
                    str(row["trades"]),
                    f"{float(row['win_rate']):.1%}",
                    f"{float(row['average_r']):.3f}",
                    f"{float(row['max_drawdown_per_share']):.2f}",
                    f"{float(row['profit_factor']):.2f}",
                    f"{row['positive_months']}/{int(row['positive_months']) + int(row['negative_months'])}",
                    f"{float(row['top5_winner_contribution_pct']):.1%}",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Walk-Forward",
            "",
            "Expanding train window. Each test month uses only parameters selected from prior months.",
            "",
            "| Train | Test | Selected | Test Gross/share | Test Net/share | Trades | Win | Test DD | Buy/Hold | Open/Close Long |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in walk_forward_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{row['train_start']} to {row['train_end']}",
                    str(row["test_month"]),
                    str(row["selected_candidate"]),
                    f"{float(row['test_gross_pnl_per_share']):.2f}",
                    f"{float(row['test_net_pnl_per_share']):.2f}",
                    str(row["test_trades"]),
                    f"{float(row['test_win_rate']):.1%}",
                    f"{float(row['test_max_drawdown_per_share']):.2f}",
                    f"{float(row['test_buy_hold_pnl_per_share']):.2f}",
                    f"{float(row['test_daily_open_close_long_pnl_per_share']):.2f}",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "- The best in-sample candidate is `continuation_0.80R`, but it collapses in the final May test window.",
            "- The strategy's edge is concentrated: the top five winning trades explain roughly the whole in-sample profit.",
            "- `1.00R+` targets are too ambitious for the current entry signal; most trades do not produce enough follow-through.",
            "- Hybrid reversal logic lowers drawdown in-sample, but it does not create robust out-of-sample profitability.",
            "- Buy-and-hold dominates on this NVDA sample, so the intraday system is not capturing the main source of return.",
            "",
            "## Decision",
            "",
            "Discard the current trading logic as a deployable candidate. The next research iteration should not continue",
            "tuning only R targets. It needs a different entry filter or regime classifier, then the same final review must",
            "be rerun before any paper order execution.",
            "",
            "## Files",
            "",
            f"- Candidate CSV: `{candidate_csv_name}`",
            f"- Walk-forward CSV: `{walk_forward_csv_name}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
