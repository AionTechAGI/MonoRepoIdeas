"""Request a small read-only historical data sample from IBKR."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.config import load_ibkr_settings
from trading_strategy_tester.data.contracts import stock_instrument
from trading_strategy_tester.data.data_cache import latest_cached_timestamp, upsert_bars
from trading_strategy_tester.data.historical_loader import request_historical_bars


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Stock symbol to request.")
    parser.add_argument("--primary-exchange", default="", help="Optional primary exchange.")
    parser.add_argument("--duration", default="1 D", help="IBKR duration string.")
    parser.add_argument(
        "--end-datetime",
        default="",
        help='IBKR endDateTime, for example "20260514 16:00:00 US/Eastern".',
    )
    parser.add_argument("--bar-size", default="1 min", help="IBKR bar size string.")
    parser.add_argument("--what-to-show", default="TRADES", help="IBKR historical data type.")
    parser.add_argument("--outside-rth", action="store_true", help="Include outside RTH bars.")
    parser.add_argument(
        "--market-data-type",
        default=1,
        type=int,
        choices=[1, 2, 3, 4],
        help="1 live, 2 frozen, 3 delayed, 4 delayed-frozen.",
    )
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
    args = parser.parse_args()

    settings = load_ibkr_settings(args.config)
    if settings.trading_enabled:
        print("ERROR: trading_enabled=true is not allowed for historical probe.")
        return 2

    instrument = stock_instrument(args.symbol, primary_exchange=args.primary_exchange)
    cached_latest = latest_cached_timestamp(args.cache, instrument.symbol, args.bar_size)
    print(f"symbol: {instrument.symbol}")
    print(f"bar_size: {args.bar_size}")
    print(f"latest_cached_timestamp: {cached_latest or '(none)'}")
    print("requesting read-only historical bars from IBKR...")

    result = request_historical_bars(
        settings=settings,
        instrument=instrument,
        end_datetime=args.end_datetime,
        duration=args.duration,
        bar_size=args.bar_size,
        what_to_show=args.what_to_show,
        use_rth=not args.outside_rth,
        market_data_type=args.market_data_type,
    )

    print(result.message)
    if result.errors:
        print("ibkr_messages:")
        for item in result.errors:
            print(f"  {item}")

    if not result.ok:
        return 1

    written = upsert_bars(args.cache, instrument.symbol, args.bar_size, result.bars)
    print(f"bars_received: {len(result.bars)}")
    print(f"bars_written_to_cache: {written}")
    print(f"cache: {args.cache}")
    if result.bars:
        print(f"first_bar: {result.bars[0]}")
        print(f"last_bar: {result.bars[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
