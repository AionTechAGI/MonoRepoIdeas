"""Intraday VWAP calculations."""

from __future__ import annotations

from trading_strategy_tester.data.historical_loader import HistoricalBar


def typical_price(bar: HistoricalBar) -> float:
    return (bar.high + bar.low + bar.close) / 3


def calculate_vwap_series(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
) -> list[float]:
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    values: list[float] = []

    for bar in bars:
        volume = bar.volume or 0.0
        cumulative_price_volume += typical_price(bar) * volume
        cumulative_volume += volume
        if cumulative_volume <= 0:
            values.append(bar.close)
        else:
            values.append(cumulative_price_volume / cumulative_volume)

    return values
