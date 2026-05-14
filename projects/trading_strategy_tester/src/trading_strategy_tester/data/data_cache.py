"""SQLite cache for historical and realtime bars."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Iterable

from trading_strategy_tester.data.historical_loader import HistoricalBar


SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    bar_size TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    wap REAL,
    bar_count INTEGER,
    source TEXT NOT NULL,
    created_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, bar_size, timestamp, source)
);

CREATE INDEX IF NOT EXISTS idx_bars_symbol_size_time
ON bars(symbol, bar_size, timestamp);
"""


def initialize_cache(path: str | Path) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cache_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_bars(
    path: str | Path,
    symbol: str,
    bar_size: str,
    bars: Iterable[HistoricalBar],
    source: str = "IBKR",
) -> int:
    initialize_cache(path)
    rows = [
        (
            symbol.upper(),
            bar_size,
            bar.timestamp,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
            bar.wap,
            bar.bar_count,
            source,
        )
        for bar in bars
    ]
    if not rows:
        return 0

    conn = sqlite3.connect(path)
    try:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR REPLACE INTO bars (
                symbol, bar_size, timestamp, open, high, low, close,
                volume, wap, bar_count, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        return conn.total_changes - before
    finally:
        conn.close()


def latest_cached_timestamp(
    path: str | Path,
    symbol: str,
    bar_size: str,
    source: str = "IBKR",
) -> str | None:
    cache_path = Path(path)
    if not cache_path.exists():
        return None
    conn = sqlite3.connect(cache_path)
    try:
        row = conn.execute(
            """
            SELECT MAX(timestamp)
            FROM bars
            WHERE symbol = ? AND bar_size = ? AND source = ?
            """,
            (symbol.upper(), bar_size, source),
        ).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row and row[0] is not None else None


def read_bars(
    path: str | Path,
    symbol: str,
    bar_size: str,
    start_timestamp: str | None = None,
    end_timestamp: str | None = None,
    source: str = "IBKR",
) -> list[HistoricalBar]:
    cache_path = Path(path)
    if not cache_path.exists():
        return []

    predicates = ["symbol = ?", "bar_size = ?", "source = ?"]
    values: list[object] = [symbol.upper(), bar_size, source]
    if start_timestamp is not None:
        predicates.append("timestamp >= ?")
        values.append(start_timestamp)
    if end_timestamp is not None:
        predicates.append("timestamp <= ?")
        values.append(end_timestamp)

    conn = sqlite3.connect(cache_path)
    try:
        rows = conn.execute(
            f"""
            SELECT timestamp, open, high, low, close, volume, wap, bar_count
            FROM bars
            WHERE {' AND '.join(predicates)}
            ORDER BY timestamp
            """,
            tuple(values),
        ).fetchall()
    finally:
        conn.close()

    return [
        HistoricalBar(
            timestamp=str(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]) if row[5] is not None else None,
            wap=float(row[6]) if row[6] is not None else None,
            bar_count=int(row[7]) if row[7] is not None else None,
        )
        for row in rows
    ]


def count_bars(
    path: str | Path,
    symbol: str,
    bar_size: str,
    source: str = "IBKR",
) -> int:
    cache_path = Path(path)
    if not cache_path.exists():
        return 0
    conn = sqlite3.connect(cache_path)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM bars
            WHERE symbol = ? AND bar_size = ? AND source = ?
            """,
            (symbol.upper(), bar_size, source),
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0
