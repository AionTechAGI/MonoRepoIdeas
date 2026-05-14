"""Helpers for historical range downloads and chart preparation."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from trading_strategy_tester.data.historical_loader import HistoricalBar


@dataclass(frozen=True)
class HistoricalChunk:
    start: date
    end: date
    end_datetime: str
    duration: str


def monthly_chunks(
    start: date,
    end: date,
    duration: str = "1 M",
    end_time: time = time(16, 0),
    timezone: str = "US/Eastern",
) -> list[HistoricalChunk]:
    if end < start:
        raise ValueError("end date must be greater than or equal to start date")

    chunks: list[HistoricalChunk] = []
    current = start
    while current <= end:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, last_day)
        chunk_end = min(month_end, end)
        chunks.append(
            HistoricalChunk(
                start=current,
                end=chunk_end,
                end_datetime=format_ibkr_end_datetime(chunk_end, end_time, timezone),
                duration=duration,
            )
        )
        current = chunk_end + timedelta(days=1)
    return chunks


def format_ibkr_end_datetime(
    end_date: date,
    end_time: time = time(16, 0),
    timezone: str = "US/Eastern",
) -> str:
    return f"{end_date:%Y%m%d} {end_time:%H:%M:%S} {timezone}"


def parse_ibkr_bar_timestamp(raw: str) -> datetime:
    normalized = " ".join(raw.split())
    for fmt in ("%Y%m%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported IBKR timestamp: {raw!r}")


def filter_bars_by_date(
    bars: list[HistoricalBar] | tuple[HistoricalBar, ...],
    start: date,
    end: date,
) -> list[HistoricalBar]:
    filtered: list[HistoricalBar] = []
    for bar in bars:
        bar_date = parse_ibkr_bar_timestamp(bar.timestamp).date()
        if start <= bar_date <= end:
            filtered.append(bar)
    return filtered


def find_duplicate_timestamps(bars: list[HistoricalBar] | tuple[HistoricalBar, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for bar in bars:
        normalized = " ".join(bar.timestamp.split())
        if normalized in seen:
            duplicates.append(normalized)
        seen.add(normalized)
    return duplicates
