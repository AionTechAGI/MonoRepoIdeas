"""ORB + VWAP continuation, reversal, and hybrid backtests."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean, median

from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import parse_ibkr_bar_timestamp
from trading_strategy_tester.strategy.opening_range import OpeningRange, calculate_opening_range
from trading_strategy_tester.strategy.vwap import calculate_vwap_series


CONTINUATION = "CONTINUATION"
REVERSAL = "REVERSAL"
MODE_CONTINUATION = "continuation"
MODE_REVERSAL = "reversal"
MODE_HYBRID = "hybrid"


@dataclass(frozen=True)
class BacktestConfig:
    opening_range_bars: int = 3
    full_session_bars: int = 78
    target_r: float = 1.0
    include_partial_sessions: bool = False
    mode: str = MODE_CONTINUATION
    hold_bars: int = 1
    vwap_slope_lookback: int = 0
    vwap_slope_min: float = 0.0
    max_vwap_distance_or_width: float | None = None
    min_or_width_bps: float = 0.0
    max_or_width_bps: float | None = None
    max_failure_bars: int = 3
    wick_ratio_threshold: float = 0.0
    reversal_target_mode: str = "OR_MID"
    allow_long: bool = True
    allow_short: bool = True


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
    setup_type: str = CONTINUATION


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    sessions_tested: int
    sessions_skipped: int
    incomplete_sessions_skipped: int
    buy_and_hold: "BuyAndHoldResult"
    daily_open_close_long: "IntradayBenchmarkResult"
    daily_after_or_long: "IntradayBenchmarkResult"


@dataclass(frozen=True)
class BuyAndHoldResult:
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    pnl_per_share: float
    return_pct: float


@dataclass(frozen=True)
class IntradayBenchmarkResult:
    name: str
    sessions: int
    pnl_per_share: float
    win_rate: float
    average_pnl_per_session: float


@dataclass
class BreakoutCandidate:
    direction: str
    index: int
    extreme: float


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
    mode: str = MODE_CONTINUATION,
    hold_bars: int = 1,
    vwap_slope_lookback: int = 0,
    vwap_slope_min: float = 0.0,
    max_vwap_distance_or_width: float | None = None,
    min_or_width_bps: float = 0.0,
    max_or_width_bps: float | None = None,
    max_failure_bars: int = 3,
    wick_ratio_threshold: float = 0.0,
    reversal_target_mode: str = "OR_MID",
    allow_long: bool = True,
    allow_short: bool = True,
) -> BacktestResult:
    config = BacktestConfig(
        opening_range_bars=opening_range_bars,
        full_session_bars=full_session_bars,
        target_r=target_r,
        include_partial_sessions=include_partial_sessions,
        mode=mode,
        hold_bars=hold_bars,
        vwap_slope_lookback=vwap_slope_lookback,
        vwap_slope_min=vwap_slope_min,
        max_vwap_distance_or_width=max_vwap_distance_or_width,
        min_or_width_bps=min_or_width_bps,
        max_or_width_bps=max_or_width_bps,
        max_failure_bars=max_failure_bars,
        wick_ratio_threshold=wick_ratio_threshold,
        reversal_target_mode=reversal_target_mode,
        allow_long=allow_long,
        allow_short=allow_short,
    )
    return run_orb_vwap_backtest_with_config(bars, config)


def run_orb_vwap_backtest_with_config(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    config: BacktestConfig,
) -> BacktestResult:
    if config.mode not in {MODE_CONTINUATION, MODE_REVERSAL, MODE_HYBRID}:
        raise ValueError(f"unsupported backtest mode: {config.mode}")

    sessions = group_bars_by_session(bars)
    test_sessions: list[SessionData] = []
    incomplete_skipped = 0
    for session in sessions:
        if len(session.bars) >= config.full_session_bars or config.include_partial_sessions:
            test_sessions.append(session)
        else:
            incomplete_skipped += 1

    trades: list[Trade] = []
    skipped = 0
    for session in test_sessions:
        trade = _first_orb_vwap_trade(session, config)
        if trade is None:
            skipped += 1
        else:
            trades.append(trade)

    benchmark_bars = [bar for session in test_sessions for bar in session.bars]
    benchmark = calculate_buy_and_hold(benchmark_bars)
    return BacktestResult(
        trades=tuple(trades),
        sessions_tested=len(test_sessions),
        sessions_skipped=skipped,
        incomplete_sessions_skipped=incomplete_skipped,
        buy_and_hold=benchmark,
        daily_open_close_long=calculate_daily_open_close_long(test_sessions),
        daily_after_or_long=calculate_daily_after_or_long(
            test_sessions, config.opening_range_bars
        ),
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
            "continuation_count": 0,
            "reversal_count": 0,
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
        "continuation_count": sum(1 for trade in trades if trade.setup_type == CONTINUATION),
        "reversal_count": sum(1 for trade in trades if trade.setup_type == REVERSAL),
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


def calculate_daily_open_close_long(
    sessions: list[SessionData],
) -> IntradayBenchmarkResult:
    pnl_values = [session.bars[-1].close - session.bars[0].open for session in sessions]
    return _intraday_benchmark("daily_open_close_long", pnl_values)


def calculate_daily_after_or_long(
    sessions: list[SessionData],
    opening_range_bars: int,
) -> IntradayBenchmarkResult:
    pnl_values = []
    for session in sessions:
        if len(session.bars) > opening_range_bars:
            pnl_values.append(session.bars[-1].close - session.bars[opening_range_bars].open)
    return _intraday_benchmark("daily_after_or_long", pnl_values)


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
    config: BacktestConfig,
) -> Trade | None:
    bars = session.bars
    if len(bars) <= config.opening_range_bars + 1:
        return None

    opening_range = calculate_opening_range(bars, config.opening_range_bars)
    if opening_range.width <= 0 or not _opening_range_width_ok(opening_range, config):
        return None

    vwaps = calculate_vwap_series(bars)
    candidates: dict[str, BreakoutCandidate | None] = {"UP": None, "DOWN": None}
    for signal_index in range(config.opening_range_bars, len(bars) - 1):
        bar = bars[signal_index]
        _update_breakout_candidates(candidates, bar, signal_index, opening_range)

        if config.mode in {MODE_CONTINUATION, MODE_HYBRID}:
            continuation = _continuation_direction(
                bars, vwaps, signal_index, opening_range, config
            )
            if continuation is not None:
                stop_price = opening_range.low if continuation == "LONG" else opening_range.high
                return _simulate_trade(
                    session=session,
                    opening_range=opening_range,
                    vwaps=vwaps,
                    signal_index=signal_index,
                    direction=continuation,
                    stop_price=stop_price,
                    target_r=config.target_r,
                    setup_type=CONTINUATION,
                )

        if config.mode in {MODE_REVERSAL, MODE_HYBRID}:
            reversal = _reversal_direction(
                candidates, bars, vwaps, signal_index, opening_range, config
            )
            if reversal is not None:
                direction, stop_price, target_price = reversal
                return _simulate_trade(
                    session=session,
                    opening_range=opening_range,
                    vwaps=vwaps,
                    signal_index=signal_index,
                    direction=direction,
                    stop_price=stop_price,
                    target_r=config.target_r,
                    target_price=target_price,
                    setup_type=REVERSAL,
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
    target_price: float | None = None,
    setup_type: str = CONTINUATION,
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
        target = target_price if target_price is not None else entry_price + risk * target_r
        if target <= entry_price:
            target = entry_price + risk * target_r
    else:
        risk = stop_price - entry_price
        if risk <= 0:
            return None
        target = target_price if target_price is not None else entry_price - risk * target_r
        if target >= entry_price:
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
        setup_type=setup_type,
    )


def _opening_range_width_ok(opening_range: OpeningRange, config: BacktestConfig) -> bool:
    width_bps = opening_range.width / opening_range.mid * 10_000
    if width_bps < config.min_or_width_bps:
        return False
    if config.max_or_width_bps is not None and width_bps > config.max_or_width_bps:
        return False
    return True


def _continuation_direction(
    bars: tuple[HistoricalBar, ...],
    vwaps: list[float],
    signal_index: int,
    opening_range: OpeningRange,
    config: BacktestConfig,
) -> str | None:
    if not _hold_confirmed(bars, signal_index, opening_range, config):
        return None

    signal_bar = bars[signal_index]
    vwap = vwaps[signal_index]
    if not _vwap_distance_ok(signal_bar.close, vwap, opening_range, config):
        return None

    slope = _vwap_slope(vwaps, signal_index, config.vwap_slope_lookback)
    if (
        config.allow_long
        and signal_bar.close > opening_range.high
        and signal_bar.close > vwap
        and slope >= config.vwap_slope_min
    ):
        return "LONG"
    if (
        config.allow_short
        and signal_bar.close < opening_range.low
        and signal_bar.close < vwap
        and slope <= -config.vwap_slope_min
    ):
        return "SHORT"
    return None


def _hold_confirmed(
    bars: tuple[HistoricalBar, ...],
    signal_index: int,
    opening_range: OpeningRange,
    config: BacktestConfig,
) -> bool:
    hold_bars = max(1, config.hold_bars)
    start = signal_index - hold_bars + 1
    if start < config.opening_range_bars:
        return False
    window = bars[start : signal_index + 1]
    return (
        all(bar.close > opening_range.high for bar in window)
        or all(bar.close < opening_range.low for bar in window)
    )


def _update_breakout_candidates(
    candidates: dict[str, BreakoutCandidate | None],
    bar: HistoricalBar,
    signal_index: int,
    opening_range: OpeningRange,
) -> None:
    if bar.high > opening_range.high:
        existing = candidates["UP"]
        extreme = max(existing.extreme, bar.high) if existing else bar.high
        index = existing.index if existing else signal_index
        candidates["UP"] = BreakoutCandidate("UP", index, extreme)
    if bar.low < opening_range.low:
        existing = candidates["DOWN"]
        extreme = min(existing.extreme, bar.low) if existing else bar.low
        index = existing.index if existing else signal_index
        candidates["DOWN"] = BreakoutCandidate("DOWN", index, extreme)


def _reversal_direction(
    candidates: dict[str, BreakoutCandidate | None],
    bars: tuple[HistoricalBar, ...],
    vwaps: list[float],
    signal_index: int,
    opening_range: OpeningRange,
    config: BacktestConfig,
) -> tuple[str, float, float] | None:
    bar = bars[signal_index]
    upside = candidates["UP"]
    if (
        upside
        and config.allow_short
        and signal_index - upside.index <= config.max_failure_bars
        and opening_range.low < bar.close < opening_range.high
        and _upper_wick_ratio(bar) >= config.wick_ratio_threshold
    ):
        target = _reversal_target("SHORT", opening_range, vwaps[signal_index], config)
        return "SHORT", max(upside.extreme, opening_range.high), target

    downside = candidates["DOWN"]
    if (
        downside
        and config.allow_long
        and signal_index - downside.index <= config.max_failure_bars
        and opening_range.low < bar.close < opening_range.high
        and _lower_wick_ratio(bar) >= config.wick_ratio_threshold
    ):
        target = _reversal_target("LONG", opening_range, vwaps[signal_index], config)
        return "LONG", min(downside.extreme, opening_range.low), target
    return None


def _reversal_target(
    direction: str,
    opening_range: OpeningRange,
    vwap: float,
    config: BacktestConfig,
) -> float:
    mode = config.reversal_target_mode.upper()
    if mode == "VWAP":
        return vwap
    if mode == "OPPOSITE_OR":
        return opening_range.low if direction == "SHORT" else opening_range.high
    return opening_range.mid


def _upper_wick_ratio(bar: HistoricalBar) -> float:
    spread = bar.high - bar.low
    if spread <= 0:
        return 0.0
    return (bar.high - max(bar.open, bar.close)) / spread


def _lower_wick_ratio(bar: HistoricalBar) -> float:
    spread = bar.high - bar.low
    if spread <= 0:
        return 0.0
    return (min(bar.open, bar.close) - bar.low) / spread


def _vwap_slope(vwaps: list[float], signal_index: int, lookback: int) -> float:
    if lookback <= 0:
        return 0.0
    start = signal_index - lookback
    if start < 0:
        return 0.0
    return vwaps[signal_index] - vwaps[start]


def _vwap_distance_ok(
    price: float,
    vwap: float,
    opening_range: OpeningRange,
    config: BacktestConfig,
) -> bool:
    if config.max_vwap_distance_or_width is None:
        return True
    return abs(price - vwap) <= opening_range.width * config.max_vwap_distance_or_width


def _intraday_benchmark(
    name: str,
    pnl_values: list[float],
) -> IntradayBenchmarkResult:
    if not pnl_values:
        return IntradayBenchmarkResult(
            name=name,
            sessions=0,
            pnl_per_share=0.0,
            win_rate=0.0,
            average_pnl_per_session=0.0,
        )
    wins = [pnl for pnl in pnl_values if pnl > 0]
    return IntradayBenchmarkResult(
        name=name,
        sessions=len(pnl_values),
        pnl_per_share=sum(pnl_values),
        win_rate=len(wins) / len(pnl_values),
        average_pnl_per_session=mean(pnl_values),
    )
