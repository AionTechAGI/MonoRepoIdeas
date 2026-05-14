"""Download an IBKR historical bar range into cache and generate an HTML chart."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys
import time as time_module

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.config import load_ibkr_settings
from trading_strategy_tester.data.contracts import stock_instrument
from trading_strategy_tester.data.data_cache import read_bars, upsert_bars
from trading_strategy_tester.data.historical_loader import request_historical_bars
from trading_strategy_tester.data.range_downloader import (
    filter_bars_by_date,
    find_duplicate_timestamps,
    monthly_chunks,
)
from trading_strategy_tester.research.charts import write_candlestick_volume_chart


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Stock symbol to request.")
    parser.add_argument("--primary-exchange", default="", help="Optional primary exchange.")
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="YYYY-MM-DD.")
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="YYYY-MM-DD.")
    parser.add_argument("--bar-size", default="5 mins", help='IBKR bar size, e.g. "5 mins".')
    parser.add_argument("--duration", default="1 M", help='IBKR chunk duration, e.g. "1 M".')
    parser.add_argument("--what-to-show", default="TRADES", help="IBKR historical data type.")
    parser.add_argument("--outside-rth", action="store_true", help="Include outside RTH bars.")
    parser.add_argument(
        "--market-data-type",
        default=1,
        type=int,
        choices=[1, 2, 3, 4],
        help="1 live, 2 frozen, 3 delayed, 4 delayed-frozen.",
    )
    parser.add_argument("--sleep-seconds", default=3.0, type=float, help="Delay between chunks.")
    parser.add_argument(
        "--config",
        default=PROJECT_ROOT / "config" / "ibkr_config.yaml",
        type=Path,
        help="Path to IBKR YAML config.",
    )
    parser.add_argument(
        "--cache",
        default=PROJECT_ROOT / "storage" / "trading_strategy_tester.sqlite3",
        type=Path,
        help="SQLite cache path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="HTML chart path. Defaults to artifacts/reports/<symbol>_<bar_size>_<start>_<end>.html.",
    )
    args = parser.parse_args()

    settings = load_ibkr_settings(args.config)
    if settings.trading_enabled:
        print("ERROR: trading_enabled=true is not allowed for range downloads.")
        return 2

    instrument = stock_instrument(args.symbol, primary_exchange=args.primary_exchange)
    chunks = monthly_chunks(args.start, args.end, duration=args.duration)
    print(f"symbol: {instrument.symbol}")
    print(f"range: {args.start} -> {args.end}")
    print(f"bar_size: {args.bar_size}")
    print(f"chunks: {len(chunks)}")
    print("mode: read-only historical data; no orders are sent")

    total_received = 0
    total_written = 0
    for index, chunk in enumerate(chunks, start=1):
        print(
            f"chunk {index}/{len(chunks)}: {chunk.start} -> {chunk.end}; "
            f"endDateTime={chunk.end_datetime}; duration={chunk.duration}"
        )
        result = request_historical_bars(
            settings=settings,
            instrument=instrument,
            end_datetime=chunk.end_datetime,
            duration=chunk.duration,
            bar_size=args.bar_size,
            what_to_show=args.what_to_show,
            use_rth=not args.outside_rth,
            market_data_type=args.market_data_type,
            timeout_seconds=max(settings.connection_timeout_seconds, 30.0),
        )
        print(result.message)
        if result.errors:
            important = [
                item
                for item in result.errors
                if not item.startswith("-1:2104:")
                and not item.startswith("-1:2106:")
                and not item.startswith("-1:2158:")
            ]
            for item in important:
                print(f"  ibkr: {item}")
        if not result.ok:
            return 1

        filtered_chunk_bars = filter_bars_by_date(result.bars, args.start, args.end)
        written = upsert_bars(args.cache, instrument.symbol, args.bar_size, filtered_chunk_bars)
        total_received += len(filtered_chunk_bars)
        total_written += written
        print(f"  bars_received_in_range: {len(filtered_chunk_bars)}")
        print(f"  cache_rows_written: {written}")

        if index < len(chunks):
            time_module.sleep(args.sleep_seconds)

    cached = filter_bars_by_date(
        read_bars(args.cache, instrument.symbol, args.bar_size),
        args.start,
        args.end,
    )
    duplicates = find_duplicate_timestamps(cached)
    output = args.output or (
        PROJECT_ROOT
        / "artifacts"
        / "reports"
        / f"{instrument.symbol.lower()}_{args.bar_size.replace(' ', '')}_{args.start}_{args.end}.html"
    )
    chart_path = write_candlestick_volume_chart(
        cached,
        output,
        title=f"{instrument.symbol} {args.bar_size} RTH {args.start} to {args.end}",
    )

    print("summary:")
    print(f"  total_bars_received_in_range: {total_received}")
    print(f"  total_cache_rows_written: {total_written}")
    print(f"  cached_bars_in_range: {len(cached)}")
    print(f"  duplicate_timestamps_after_cache: {len(duplicates)}")
    if cached:
        print(f"  first_cached_bar: {cached[0].timestamp}")
        print(f"  last_cached_bar: {cached[-1].timestamp}")
    print(f"  chart: {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
