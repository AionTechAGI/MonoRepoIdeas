"""Contract and instrument helpers for IBKR requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trading_strategy_tester.config import load_yaml

try:
    from ibapi.contract import Contract
except ImportError as exc:  # pragma: no cover
    Contract = object  # type: ignore[assignment,misc]
    IBAPI_CONTRACT_IMPORT_ERROR = exc
else:
    IBAPI_CONTRACT_IMPORT_ERROR = None


@dataclass(frozen=True)
class Instrument:
    symbol: str
    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"
    primary_exchange: str = ""

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "Instrument":
        return cls(
            symbol=str(raw["symbol"]).upper(),
            sec_type=str(raw.get("sec_type", "STK")),
            exchange=str(raw.get("exchange", "SMART")),
            currency=str(raw.get("currency", "USD")),
            primary_exchange=str(raw.get("primary_exchange", "")),
        )


def load_instruments(path: str | Path) -> list[Instrument]:
    raw = load_yaml(path)
    instruments = raw.get("instruments") or []
    return [
        Instrument.from_mapping(item)
        for item in instruments
        if isinstance(item, dict) and item.get("symbol")
    ]


def stock_instrument(symbol: str, primary_exchange: str = "") -> Instrument:
    return Instrument(symbol=symbol.upper(), primary_exchange=primary_exchange)


def to_ib_contract(instrument: Instrument) -> Contract:
    if IBAPI_CONTRACT_IMPORT_ERROR is not None:
        raise RuntimeError("ibapi is not installed") from IBAPI_CONTRACT_IMPORT_ERROR

    contract = Contract()
    contract.symbol = instrument.symbol
    contract.secType = instrument.sec_type
    contract.exchange = instrument.exchange
    contract.currency = instrument.currency
    if instrument.primary_exchange:
        contract.primaryExchange = instrument.primary_exchange
    return contract
