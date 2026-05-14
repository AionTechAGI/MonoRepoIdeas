"""Opening range calculations."""

from __future__ import annotations

from dataclasses import dataclass

from trading_strategy_tester.data.historical_loader import HistoricalBar


@dataclass(frozen=True)
class OpeningRange:
    high: float
    low: float
    mid: float
    width: float
    bars_used: int


def calculate_opening_range(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    opening_range_bars: int = 3,
) -> OpeningRange:
    if opening_range_bars <= 0:
        raise ValueError("opening_range_bars must be positive")
    if len(bars) < opening_range_bars:
        raise ValueError("not enough bars to calculate opening range")

    window = bars[:opening_range_bars]
    high = max(bar.high for bar in window)
    low = min(bar.low for bar in window)
    return OpeningRange(
        high=high,
        low=low,
        mid=(high + low) / 2,
        width=high - low,
        bars_used=opening_range_bars,
    )
