"""Render a candlestick/volume HTML chart from cached bars."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.data.data_cache import read_bars
from trading_strategy_tester.data.range_downloader import (
    filter_bars_by_date,
    find_duplicate_timestamps,
)
from trading_strategy_tester.research.charts import write_candlestick_volume_chart


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--bar-size", default="5 mins")
    parser.add_argument(
        "--cache",
        default=PROJECT_ROOT / "storage" / "trading_strategy_tester.sqlite3",
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cached = filter_bars_by_date(
        read_bars(args.cache, args.symbol, args.bar_size),
        args.start,
        args.end,
    )
    if not cached:
        print("ERROR: no cached bars found for requested range")
        return 1

    duplicates = find_duplicate_timestamps(cached)
    chart_path = write_candlestick_volume_chart(
        cached,
        args.output,
        title=f"{args.symbol.upper()} {args.bar_size} RTH {args.start} to {args.end}",
    )
    print(f"cached_bars_in_range: {len(cached)}")
    print(f"duplicate_timestamps_after_cache: {len(duplicates)}")
    print(f"first_cached_bar: {cached[0].timestamp}")
    print(f"last_cached_bar: {cached[-1].timestamp}")
    print(f"chart: {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
