"""Probe IBKR market data type for a symbol without placing orders."""

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
from trading_strategy_tester.data.market_data_probe import (
    MARKET_DATA_TYPE_LABELS,
    probe_market_data_type,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Stock symbol to request.")
    parser.add_argument("--primary-exchange", default="", help="Optional primary exchange.")
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
    args = parser.parse_args()

    settings = load_ibkr_settings(args.config)
    if settings.trading_enabled:
        print("ERROR: trading_enabled=true is not allowed for market data probe.")
        return 2

    instrument = stock_instrument(args.symbol, primary_exchange=args.primary_exchange)
    print(f"symbol: {instrument.symbol}")
    print(
        "requested_market_data_type: "
        f"{args.market_data_type} ({MARKET_DATA_TYPE_LABELS[args.market_data_type]})"
    )

    result = probe_market_data_type(
        settings=settings,
        instrument=instrument,
        requested_market_data_type=args.market_data_type,
    )
    print(result.message)
    print(
        "received_market_data_type: "
        f"{result.received_market_data_type or '(none)'} "
        f"({result.received_market_data_label})"
    )
    if result.errors:
        print("ibkr_messages:")
        for item in result.errors:
            print(f"  {item}")

    if result.received_market_data_type in (3, 4) and not settings.allow_delayed_data_for_testing:
        print("execution_block: delayed data is not allowed by config")
        return 1

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
