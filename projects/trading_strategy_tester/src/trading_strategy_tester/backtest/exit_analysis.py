"""Exit policy and R-multiple analysis for ORB/VWAP entries."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

from trading_strategy_tester.backtest.orb_vwap import (
    BacktestConfig,
    SessionData,
    Trade,
    group_bars_by_session,
    max_drawdown,
)
from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.data.range_downloader import parse_ibkr_bar_timestamp
from trading_strategy_tester.strategy.opening_range import calculate_opening_range
from trading_strategy_tester.strategy.vwap import calculate_vwap_series


@dataclass(frozen=True)
class EntryCandidate:
    session_date: str
    direction: str
    signal_index: int
    entry_index: int
    entry_price: float
    stop_price: float
    risk_per_share: float
    or_high: float
    or_low: float
    vwap_at_signal: float
    bars: tuple[HistoricalBar, ...]
    vwaps: tuple[float, ...]


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    fixed_target_r: float | None = None
    partial_target_r: float | None = None
    partial_fraction: float = 0.5
    move_stop_to_breakeven_after_partial: bool = False
    runner_exit: str = "SESSION_CLOSE"
    trail_r: float | None = None


@dataclass(frozen=True)
class ExitSimulation:
    policy: str
    session_date: str
    direction: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    risk_per_share: float
    pnl_per_share: float
    r_multiple: float
    exit_reason: str
    mfe_r: float
    mae_r: float


def collect_continuation_entries(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    config: BacktestConfig,
) -> list[EntryCandidate]:
    entries: list[EntryCandidate] = []
    for session in _complete_sessions(bars, config):
        entry = _first_continuation_entry(session, config)
        if entry is not None:
            entries.append(entry)
    return entries


def simulate_exit_policies(
    entries: list[EntryCandidate],
    policies: list[ExitPolicy],
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for policy in policies:
        simulations = [simulate_exit_policy(entry, policy) for entry in entries]
        r_values = [item.r_multiple for item in simulations]
        pnl_values = [item.pnl_per_share for item in simulations]
        wins = [item for item in simulations if item.pnl_per_share > 0]
        target_like = [
            item
            for item in simulations
            if "TARGET" in item.exit_reason or "PARTIAL" in item.exit_reason
        ]
        rows.append(
            {
                "policy": policy.name,
                "trade_count": len(simulations),
                "win_rate": len(wins) / len(simulations) if simulations else 0.0,
                "gross_pnl_per_share": sum(pnl_values),
                "average_r": mean(r_values) if r_values else 0.0,
                "median_r": median(r_values) if r_values else 0.0,
                "max_drawdown_per_share": max_drawdown(pnl_values),
                "target_or_partial_count": len(target_like),
                "stop_count": sum(1 for item in simulations if "STOP" in item.exit_reason),
                "session_close_count": sum(
                    1 for item in simulations if item.exit_reason == "SESSION_CLOSE"
                ),
                "average_mfe_r": mean([item.mfe_r for item in simulations])
                if simulations
                else 0.0,
                "median_mfe_r": median([item.mfe_r for item in simulations])
                if simulations
                else 0.0,
                "average_mae_r": mean([item.mae_r for item in simulations])
                if simulations
                else 0.0,
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
    return rows


def simulate_exit_policy(entry: EntryCandidate, policy: ExitPolicy) -> ExitSimulation:
    if policy.partial_target_r is not None:
        return _simulate_partial_policy(entry, policy)
    if policy.fixed_target_r is not None:
        return _simulate_fixed_policy(entry, policy)
    return _simulate_runner_policy(entry, policy)


def summarize_mfe_mae(entries: list[EntryCandidate]) -> dict[str, float | int]:
    mfe_values: list[float] = []
    mae_values: list[float] = []
    for entry in entries:
        mfe, mae = _mfe_mae_r(entry)
        mfe_values.append(mfe)
        mae_values.append(mae)
    if not entries:
        return {
            "entry_count": 0,
            "average_mfe_r": 0.0,
            "median_mfe_r": 0.0,
            "average_mae_r": 0.0,
            "median_mae_r": 0.0,
            "mfe_ge_0_75r": 0,
            "mfe_ge_1r": 0,
            "mfe_ge_1_5r": 0,
            "mfe_ge_2r": 0,
        }
    return {
        "entry_count": len(entries),
        "average_mfe_r": mean(mfe_values),
        "median_mfe_r": median(mfe_values),
        "average_mae_r": mean(mae_values),
        "median_mae_r": median(mae_values),
        "mfe_ge_0_75r": sum(1 for value in mfe_values if value >= 0.75),
        "mfe_ge_1r": sum(1 for value in mfe_values if value >= 1.0),
        "mfe_ge_1_5r": sum(1 for value in mfe_values if value >= 1.5),
        "mfe_ge_2r": sum(1 for value in mfe_values if value >= 2.0),
    }


def default_exit_policies() -> list[ExitPolicy]:
    return [
        ExitPolicy(name="fixed_0.25R", fixed_target_r=0.25),
        ExitPolicy(name="fixed_0.50R", fixed_target_r=0.5),
        ExitPolicy(name="fixed_0.60R", fixed_target_r=0.6),
        ExitPolicy(name="fixed_0.70R", fixed_target_r=0.7),
        ExitPolicy(name="fixed_0.75R", fixed_target_r=0.75),
        ExitPolicy(name="fixed_0.80R", fixed_target_r=0.8),
        ExitPolicy(name="fixed_0.90R", fixed_target_r=0.9),
        ExitPolicy(name="fixed_1.00R", fixed_target_r=1.0),
        ExitPolicy(name="fixed_1.25R", fixed_target_r=1.25),
        ExitPolicy(name="fixed_1.50R", fixed_target_r=1.5),
        ExitPolicy(name="fixed_2.00R", fixed_target_r=2.0),
        ExitPolicy(name="session_close_runner"),
        ExitPolicy(
            name="partial_50pct_0.75R_then_session_close",
            partial_target_r=0.75,
            partial_fraction=0.5,
        ),
        ExitPolicy(
            name="partial_50pct_0.75R_then_breakeven_session_close",
            partial_target_r=0.75,
            partial_fraction=0.5,
            move_stop_to_breakeven_after_partial=True,
        ),
        ExitPolicy(
            name="partial_50pct_0.75R_then_vwap_trail",
            partial_target_r=0.75,
            partial_fraction=0.5,
            move_stop_to_breakeven_after_partial=True,
            runner_exit="VWAP_TRAIL",
        ),
        ExitPolicy(
            name="partial_70pct_0.75R_then_breakeven_session_close",
            partial_target_r=0.75,
            partial_fraction=0.7,
            move_stop_to_breakeven_after_partial=True,
        ),
        ExitPolicy(
            name="partial_80pct_0.75R_then_breakeven_session_close",
            partial_target_r=0.75,
            partial_fraction=0.8,
            move_stop_to_breakeven_after_partial=True,
        ),
        ExitPolicy(
            name="partial_70pct_0.75R_then_vwap_trail",
            partial_target_r=0.75,
            partial_fraction=0.7,
            move_stop_to_breakeven_after_partial=True,
            runner_exit="VWAP_TRAIL",
        ),
        ExitPolicy(
            name="partial_80pct_0.75R_then_vwap_trail",
            partial_target_r=0.75,
            partial_fraction=0.8,
            move_stop_to_breakeven_after_partial=True,
            runner_exit="VWAP_TRAIL",
        ),
        ExitPolicy(
            name="trail_1.00R_from_high_low",
            runner_exit="R_TRAIL",
            trail_r=1.0,
        ),
        ExitPolicy(
            name="trail_1.50R_from_high_low",
            runner_exit="R_TRAIL",
            trail_r=1.5,
        ),
    ]


def _complete_sessions(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    config: BacktestConfig,
) -> list[SessionData]:
    sessions = group_bars_by_session(bars)
    return [
        session
        for session in sessions
        if len(session.bars) >= config.full_session_bars or config.include_partial_sessions
    ]


def _first_continuation_entry(
    session: SessionData,
    config: BacktestConfig,
) -> EntryCandidate | None:
    bars = session.bars
    if len(bars) <= config.opening_range_bars + 1:
        return None

    opening_range = calculate_opening_range(bars, config.opening_range_bars)
    if opening_range.width <= 0:
        return None
    vwaps = calculate_vwap_series(bars)

    for signal_index in range(config.opening_range_bars, len(bars) - 1):
        signal_bar = bars[signal_index]
        vwap = vwaps[signal_index]
        direction: str | None = None
        stop_price: float | None = None
        if signal_bar.close > opening_range.high and signal_bar.close > vwap:
            direction = "LONG"
            stop_price = opening_range.low
        elif signal_bar.close < opening_range.low and signal_bar.close < vwap:
            direction = "SHORT"
            stop_price = opening_range.high
        if direction is None or stop_price is None:
            continue

        entry_index = signal_index + 1
        entry_price = bars[entry_index].open
        risk = entry_price - stop_price if direction == "LONG" else stop_price - entry_price
        if risk <= 0:
            continue
        return EntryCandidate(
            session_date=session.session_date,
            direction=direction,
            signal_index=signal_index,
            entry_index=entry_index,
            entry_price=entry_price,
            stop_price=stop_price,
            risk_per_share=risk,
            or_high=opening_range.high,
            or_low=opening_range.low,
            vwap_at_signal=vwap,
            bars=bars,
            vwaps=tuple(vwaps),
        )
    return None


def _simulate_fixed_policy(entry: EntryCandidate, policy: ExitPolicy) -> ExitSimulation:
    target_r = policy.fixed_target_r or 1.0
    target = _price_at_r(entry, target_r)
    return _simulate_with_stop_and_target(entry, entry.stop_price, target, f"TARGET_{target_r:.2f}R")


def _simulate_runner_policy(entry: EntryCandidate, policy: ExitPolicy) -> ExitSimulation:
    if policy.runner_exit == "R_TRAIL" and policy.trail_r is not None:
        return _simulate_r_trail(entry, policy.trail_r)
    if policy.runner_exit == "VWAP_TRAIL":
        return _simulate_vwap_trail(entry, entry.stop_price)
    return _simulate_stop_then_session_close(
        entry,
        entry.stop_price,
        entry.entry_index,
        "SESSION_CLOSE",
    )


def _simulate_partial_policy(entry: EntryCandidate, policy: ExitPolicy) -> ExitSimulation:
    target_r = policy.partial_target_r or 0.75
    partial_target = _price_at_r(entry, target_r)
    active_stop = entry.stop_price
    realized_pnl = 0.0
    remaining_fraction = 1.0
    start_index = entry.entry_index
    partial_hit = False

    for index, bar in enumerate(entry.bars[entry.entry_index:], start=entry.entry_index):
        stop_hit = _stop_hit(entry.direction, bar, active_stop)
        target_hit = _target_hit(entry.direction, bar, partial_target)
        if stop_hit:
            pnl = realized_pnl + remaining_fraction * _pnl_for_exit(entry, active_stop)
            mfe, mae = _mfe_mae_r(entry)
            return _exit_simulation(
                entry,
                policy.name,
                bar.timestamp,
                active_stop,
                pnl,
                "STOP",
                mfe,
                mae,
            )
        if target_hit:
            realized_pnl += policy.partial_fraction * _pnl_for_exit(entry, partial_target)
            remaining_fraction -= policy.partial_fraction
            start_index = index
            partial_hit = True
            if policy.move_stop_to_breakeven_after_partial:
                active_stop = entry.entry_price
            break

    if not partial_hit:
        return _session_close_exit(entry, entry.entry_index, 1.0, policy.name)

    runner = _runner_exit_after_index(entry, policy, active_stop, start_index)
    pnl = realized_pnl + remaining_fraction * runner.pnl_per_share
    mfe, mae = _mfe_mae_r(entry)
    return _exit_simulation(
        entry,
        policy.name,
        runner.exit_timestamp,
        runner.exit_price,
        pnl,
        f"PARTIAL_{runner.exit_reason}",
        mfe,
        mae,
    )


def _runner_exit_after_index(
    entry: EntryCandidate,
    policy: ExitPolicy,
    active_stop: float,
    start_index: int,
) -> ExitSimulation:
    if policy.runner_exit == "VWAP_TRAIL":
        return _simulate_vwap_trail(entry, active_stop, start_index=start_index)
    if policy.runner_exit == "R_TRAIL" and policy.trail_r is not None:
        return _simulate_r_trail(entry, policy.trail_r, start_index=start_index)
    return _simulate_stop_then_session_close(entry, active_stop, start_index, "SESSION_CLOSE")


def _simulate_with_stop_and_target(
    entry: EntryCandidate,
    stop_price: float,
    target_price: float,
    target_reason: str,
) -> ExitSimulation:
    for bar in entry.bars[entry.entry_index:]:
        stop_hit = _stop_hit(entry.direction, bar, stop_price)
        target_hit = _target_hit(entry.direction, bar, target_price)
        if stop_hit:
            return _final_exit(entry, stop_price, bar.timestamp, "STOP")
        if target_hit:
            return _final_exit(entry, target_price, bar.timestamp, target_reason)
    return _session_close_exit(entry, entry.entry_index, 1.0, "SESSION_CLOSE")


def _simulate_vwap_trail(
    entry: EntryCandidate,
    active_stop: float,
    start_index: int | None = None,
) -> ExitSimulation:
    start = start_index if start_index is not None else entry.entry_index
    for index, bar in enumerate(entry.bars[start:], start=start):
        if _stop_hit(entry.direction, bar, active_stop):
            return _final_exit(entry, active_stop, bar.timestamp, "STOP")
        vwap = entry.vwaps[index]
        if entry.direction == "LONG" and bar.close < vwap:
            return _final_exit(entry, bar.close, bar.timestamp, "VWAP_TRAIL")
        if entry.direction == "SHORT" and bar.close > vwap:
            return _final_exit(entry, bar.close, bar.timestamp, "VWAP_TRAIL")
    return _session_close_exit(entry, start, 1.0, "SESSION_CLOSE")


def _simulate_stop_then_session_close(
    entry: EntryCandidate,
    active_stop: float,
    start_index: int,
    close_reason: str,
) -> ExitSimulation:
    for bar in entry.bars[start_index:]:
        if _stop_hit(entry.direction, bar, active_stop):
            return _final_exit(entry, active_stop, bar.timestamp, "STOP")
    return _session_close_exit(entry, start_index, 1.0, close_reason)


def _simulate_r_trail(
    entry: EntryCandidate,
    trail_r: float,
    start_index: int | None = None,
) -> ExitSimulation:
    start = start_index if start_index is not None else entry.entry_index
    active_stop = entry.stop_price
    best = entry.entry_price
    for bar in entry.bars[start:]:
        if entry.direction == "LONG":
            best = max(best, bar.high)
            active_stop = max(active_stop, best - entry.risk_per_share * trail_r)
        else:
            best = min(best, bar.low)
            active_stop = min(active_stop, best + entry.risk_per_share * trail_r)
        if _stop_hit(entry.direction, bar, active_stop):
            return _final_exit(entry, active_stop, bar.timestamp, f"TRAIL_{trail_r:.2f}R")
    return _session_close_exit(entry, start, 1.0, "SESSION_CLOSE")


def _session_close_exit(
    entry: EntryCandidate,
    start_index: int,
    fraction: float,
    reason: str,
) -> ExitSimulation:
    bar = entry.bars[-1]
    pnl = _pnl_for_exit(entry, bar.close) * fraction
    mfe, mae = _mfe_mae_r(entry, start_index=start_index)
    return _exit_simulation(entry, reason, bar.timestamp, bar.close, pnl, reason, mfe, mae)


def _final_exit(
    entry: EntryCandidate,
    exit_price: float,
    exit_timestamp: str,
    reason: str,
) -> ExitSimulation:
    pnl = _pnl_for_exit(entry, exit_price)
    mfe, mae = _mfe_mae_r(entry)
    return _exit_simulation(entry, reason, exit_timestamp, exit_price, pnl, reason, mfe, mae)


def _exit_simulation(
    entry: EntryCandidate,
    policy_name: str,
    exit_timestamp: str,
    exit_price: float,
    pnl: float,
    reason: str,
    mfe: float,
    mae: float,
) -> ExitSimulation:
    return ExitSimulation(
        policy=policy_name,
        session_date=entry.session_date,
        direction=entry.direction,
        entry_timestamp=entry.bars[entry.entry_index].timestamp,
        exit_timestamp=exit_timestamp,
        entry_price=entry.entry_price,
        exit_price=exit_price,
        risk_per_share=entry.risk_per_share,
        pnl_per_share=pnl,
        r_multiple=pnl / entry.risk_per_share,
        exit_reason=reason,
        mfe_r=mfe,
        mae_r=mae,
    )


def _mfe_mae_r(entry: EntryCandidate, start_index: int | None = None) -> tuple[float, float]:
    start = start_index if start_index is not None else entry.entry_index
    max_favorable = 0.0
    max_adverse = 0.0
    for bar in entry.bars[start:]:
        if entry.direction == "LONG":
            favorable = bar.high - entry.entry_price
            adverse = entry.entry_price - bar.low
        else:
            favorable = entry.entry_price - bar.low
            adverse = bar.high - entry.entry_price
        max_favorable = max(max_favorable, favorable)
        max_adverse = max(max_adverse, adverse)
    return max_favorable / entry.risk_per_share, max_adverse / entry.risk_per_share


def _price_at_r(entry: EntryCandidate, r_multiple: float) -> float:
    if entry.direction == "LONG":
        return entry.entry_price + entry.risk_per_share * r_multiple
    return entry.entry_price - entry.risk_per_share * r_multiple


def _stop_hit(direction: str, bar: HistoricalBar, stop_price: float) -> bool:
    return bar.low <= stop_price if direction == "LONG" else bar.high >= stop_price


def _target_hit(direction: str, bar: HistoricalBar, target_price: float) -> bool:
    return bar.high >= target_price if direction == "LONG" else bar.low <= target_price


def _pnl_for_exit(entry: EntryCandidate, exit_price: float) -> float:
    if entry.direction == "LONG":
        return exit_price - entry.entry_price
    return entry.entry_price - exit_price
