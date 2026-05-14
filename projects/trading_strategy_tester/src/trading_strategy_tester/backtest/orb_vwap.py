"""Baseline ORB + VWAP continuation backtest."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median

from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import parse_ibkr_bar_timestamp
from trading_strategy_tester.strategy.opening_range import OpeningRange, calculate_opening_range
from trading_strategy_tester.strategy.vwap import calculate_vwap_series


@dataclass(frozen=True)
class SessionData:
    session_date: str
    bars: tuple[HistoricalBar, ...]


@dataclass(frozen=True)
class Trade:
    session_date: str
    direction: str
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    risk_per_share: float
    pnl_per_share: float
    r_multiple: float
    exit_reason: str
    or_high: float
    or_low: float
    vwap_at_signal: float


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    sessions_tested: int
    sessions_skipped: int
    incomplete_sessions_skipped: int
    buy_and_hold: "BuyAndHoldResult"


@dataclass(frozen=True)
class BuyAndHoldResult:
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    pnl_per_share: float
    return_pct: float


def group_bars_by_session(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
) -> list[SessionData]:
    grouped: dict[str, list[HistoricalBar]] = defaultdict(list)
    for bar in bars:
        session_date = parse_ibkr_bar_timestamp(bar.timestamp).date().isoformat()
        grouped[session_date].append(bar)

    return [
        SessionData(session_date=session_date, bars=tuple(day_bars))
        for session_date, day_bars in sorted(grouped.items())
    ]


def run_orb_vwap_backtest(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    opening_range_bars: int = 3,
    full_session_bars: int = 78,
    target_r: float = 1.0,
    include_partial_sessions: bool = False,
) -> BacktestResult:
    sessions = group_bars_by_session(bars)
    test_sessions: list[SessionData] = []
    incomplete_skipped = 0
    for session in sessions:
        if len(session.bars) >= full_session_bars or include_partial_sessions:
            test_sessions.append(session)
        else:
            incomplete_skipped += 1

    trades: list[Trade] = []
    skipped = 0
    for session in test_sessions:
        trade = _first_orb_vwap_trade(
            session,
            opening_range_bars=opening_range_bars,
            target_r=target_r,
        )
        if trade is None:
            skipped += 1
        else:
            trades.append(trade)

    benchmark = calculate_buy_and_hold(
        [bar for session in test_sessions for bar in session.bars]
    )
    return BacktestResult(
        trades=tuple(trades),
        sessions_tested=len(test_sessions),
        sessions_skipped=skipped,
        incomplete_sessions_skipped=incomplete_skipped,
        buy_and_hold=benchmark,
    )


def summarize_trades(trades: tuple[Trade, ...]) -> dict[str, float | int]:
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": 0.0,
            "gross_pnl_per_share": 0.0,
            "average_r": 0.0,
            "median_r": 0.0,
            "max_drawdown_per_share": 0.0,
            "long_count": 0,
            "short_count": 0,
        }

    r_values = [trade.r_multiple for trade in trades]
    pnl_values = [trade.pnl_per_share for trade in trades]
    wins = [trade for trade in trades if trade.pnl_per_share > 0]
    return {
        "trade_count": len(trades),
        "win_rate": len(wins) / len(trades),
        "gross_pnl_per_share": sum(pnl_values),
        "average_r": mean(r_values),
        "median_r": median(r_values),
        "max_drawdown_per_share": max_drawdown(pnl_values),
        "long_count": sum(1 for trade in trades if trade.direction == "LONG"),
        "short_count": sum(1 for trade in trades if trade.direction == "SHORT"),
    }


def calculate_buy_and_hold(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
) -> BuyAndHoldResult:
    if len(bars) < 2:
        raise ValueError("not enough bars to calculate buy-and-hold")
    first = bars[0]
    last = bars[-1]
    entry_price = first.open
    exit_price = last.close
    pnl = exit_price - entry_price
    return BuyAndHoldResult(
        entry_timestamp=first.timestamp,
        exit_timestamp=last.timestamp,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl_per_share=pnl,
        return_pct=pnl / entry_price,
    )


def max_drawdown(pnl_values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in pnl_values:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return abs(worst)


def _first_orb_vwap_trade(
    session: SessionData,
    opening_range_bars: int,
    target_r: float,
) -> Trade | None:
    bars = session.bars
    if len(bars) <= opening_range_bars + 1:
        return None

    opening_range = calculate_opening_range(bars, opening_range_bars)
    if opening_range.width <= 0:
        return None

    vwaps = calculate_vwap_series(bars)
    for signal_index in range(opening_range_bars, len(bars) - 1):
        signal_bar = bars[signal_index]
        vwap = vwaps[signal_index]
        if signal_bar.close > opening_range.high and signal_bar.close > vwap:
            return _simulate_trade(
                session,
                opening_range,
                vwaps,
                signal_index,
                direction="LONG",
                stop_price=opening_range.low,
                target_r=target_r,
            )
        if signal_bar.close < opening_range.low and signal_bar.close < vwap:
            return _simulate_trade(
                session,
                opening_range,
                vwaps,
                signal_index,
                direction="SHORT",
                stop_price=opening_range.high,
                target_r=target_r,
            )
    return None


def _simulate_trade(
    session: SessionData,
    opening_range: OpeningRange,
    vwaps: list[float],
    signal_index: int,
    direction: str,
    stop_price: float,
    target_r: float,
) -> Trade | None:
    bars = session.bars
    entry_index = signal_index + 1
    if entry_index >= len(bars):
        return None

    entry_bar = bars[entry_index]
    entry_price = entry_bar.open
    if direction == "LONG":
        risk = entry_price - stop_price
        if risk <= 0:
            return None
        target = entry_price + risk * target_r
    else:
        risk = stop_price - entry_price
        if risk <= 0:
            return None
        target = entry_price - risk * target_r

    exit_bar = bars[-1]
    exit_price = exit_bar.close
    exit_reason = "SESSION_CLOSE"

    for bar in bars[entry_index:]:
        if direction == "LONG":
            stop_hit = bar.low <= stop_price
            target_hit = bar.high >= target
            if stop_hit:
                exit_bar = bar
                exit_price = stop_price
                exit_reason = "STOP"
                break
            if target_hit:
                exit_bar = bar
                exit_price = target
                exit_reason = "TARGET"
                break
        else:
            stop_hit = bar.high >= stop_price
            target_hit = bar.low <= target
            if stop_hit:
                exit_bar = bar
                exit_price = stop_price
                exit_reason = "STOP"
                break
            if target_hit:
                exit_bar = bar
                exit_price = target
                exit_reason = "TARGET"
                break

    pnl = exit_price - entry_price if direction == "LONG" else entry_price - exit_price
    return Trade(
        session_date=session.session_date,
        direction=direction,
        signal_timestamp=bars[signal_index].timestamp,
        entry_timestamp=entry_bar.timestamp,
        exit_timestamp=exit_bar.timestamp,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_price=stop_price,
        target_price=target,
        risk_per_share=risk,
        pnl_per_share=pnl,
        r_multiple=pnl / risk,
        exit_reason=exit_reason,
        or_high=opening_range.high,
        or_low=opening_range.low,
        vwap_at_signal=vwaps[signal_index],
    )
