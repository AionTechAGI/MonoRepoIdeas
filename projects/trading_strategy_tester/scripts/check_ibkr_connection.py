"""Run a safe IBKR paper connection smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.config import load_ibkr_settings, load_yaml
from trading_strategy_tester.data.ibkr_client import (
    check_paper_connection,
    format_startup_warning,
)


def _load_instrument_symbols(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = load_yaml(path)
    instruments = raw.get("instruments") or []
    symbols: list[str] = []
    for item in instruments:
        if isinstance(item, dict) and item.get("symbol"):
            symbols.append(str(item["symbol"]))
    return symbols


def _load_risk(path: Path) -> tuple[float | None, int | None]:
    if not path.exists():
        return None, None
    raw = load_yaml(path)
    risk = raw.get("risk") or {}
    max_daily_loss = risk.get("max_daily_loss")
    max_position_size = risk.get("max_position_size")
    return (
        float(max_daily_loss) if max_daily_loss is not None else None,
        int(max_position_size) if max_position_size is not None else None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=PROJECT_ROOT / "config" / "ibkr_config.yaml",
        type=Path,
        help="Path to IBKR YAML config.",
    )
    parser.add_argument(
        "--instruments",
        default=PROJECT_ROOT / "config" / "instruments.yaml",
        type=Path,
        help="Path to instruments YAML config.",
    )
    parser.add_argument(
        "--strategy-config",
        default=PROJECT_ROOT / "config" / "strategy_config.yaml",
        type=Path,
        help="Path to strategy YAML config.",
    )
    parser.add_argument("--host", help="Override IBKR host.")
    parser.add_argument("--port", type=int, help="Override IBKR port.")
    parser.add_argument("--client-id", type=int, help="Override IBKR client id.")
    parser.add_argument("--account", help="Override expected paper account.")
    args = parser.parse_args()

    settings = load_ibkr_settings(args.config)
    if args.host or args.port or args.client_id or args.account:
        settings = type(settings)(
            host=args.host or settings.host,
            port=args.port or settings.port,
            client_id=args.client_id or settings.client_id,
            account=args.account if args.account is not None else settings.account,
            paper_trading_only=settings.paper_trading_only,
            trading_enabled=settings.trading_enabled,
            allow_delayed_data_for_testing=settings.allow_delayed_data_for_testing,
            connection_timeout_seconds=settings.connection_timeout_seconds,
            require_du_account=settings.require_du_account,
        )
    symbols = _load_instrument_symbols(args.instruments)
    max_daily_loss, max_position_size = _load_risk(args.strategy_config)

    print(
        format_startup_warning(
            settings,
            instruments=symbols,
            max_daily_loss=max_daily_loss,
            max_position_size=max_position_size,
        )
    )

    if settings.trading_enabled:
        print("ERROR: trading_enabled=true is not allowed for this smoke test.")
        return 2

    result = check_paper_connection(settings)
    print(result.message)
    print(f"managed_accounts: {', '.join(result.managed_accounts) or '(none)'}")
    print(f"selected_account: {result.selected_account or '(none)'}")

    if result.account_summary:
        print("account_summary:")
        for account, values in result.account_summary.items():
            print(f"  {account}:")
            for tag, value in sorted(values.items()):
                print(f"    {tag}: {value}")

    if result.errors:
        print("ibkr_messages:")
        for item in result.errors:
            print(f"  {item}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
