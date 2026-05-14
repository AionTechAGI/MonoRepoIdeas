"""Read-only IBKR market data type probe."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any

from trading_strategy_tester.config import IbkrSettings
from trading_strategy_tester.data.contracts import Instrument, to_ib_contract

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
except ImportError as exc:  # pragma: no cover
    EClient = object  # type: ignore[assignment,misc]
    EWrapper = object  # type: ignore[assignment,misc]
    IBAPI_IMPORT_ERROR = exc
else:
    IBAPI_IMPORT_ERROR = None


MARKET_DATA_TYPE_LABELS = {
    1: "live",
    2: "frozen",
    3: "delayed",
    4: "delayed-frozen",
}


@dataclass(frozen=True)
class MarketDataStatusResult:
    ok: bool
    symbol: str
    requested_market_data_type: int
    received_market_data_type: int | None
    received_market_data_label: str
    errors: tuple[str, ...] = ()
    message: str = ""


class MarketDataTypeApp(EWrapper, EClient):  # type: ignore[misc]
    def __init__(self) -> None:
        if IBAPI_IMPORT_ERROR is not None:
            raise RuntimeError("ibapi is not installed") from IBAPI_IMPORT_ERROR
        EClient.__init__(self, self)
        self.next_valid_id_event = threading.Event()
        self.market_data_type_event = threading.Event()
        self.received_market_data_type: int | None = None
        self.error_messages: list[str] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_valid_id_event.set()

    def marketDataType(self, reqId: int, marketDataType: int) -> None:  # noqa: N802,N803
        self.received_market_data_type = int(marketDataType)
        self.market_data_type_event.set()

    def error(self, reqId: int, errorCode: int, errorString: str, *args: Any) -> None:
        self.error_messages.append(f"{reqId}:{errorCode}:{errorString}")


def probe_market_data_type(
    settings: IbkrSettings,
    instrument: Instrument,
    requested_market_data_type: int = 1,
    timeout_seconds: float | None = None,
) -> MarketDataStatusResult:
    if IBAPI_IMPORT_ERROR is not None:
        return MarketDataStatusResult(
            ok=False,
            symbol=instrument.symbol,
            requested_market_data_type=requested_market_data_type,
            received_market_data_type=None,
            received_market_data_label="unknown",
            message=f"ibapi is not installed: {IBAPI_IMPORT_ERROR}",
        )

    timeout = timeout_seconds or settings.connection_timeout_seconds
    app = MarketDataTypeApp()
    reader_thread: threading.Thread | None = None
    req_id = 9201
    try:
        app.connect(settings.host, settings.port, settings.client_id)
        reader_thread = threading.Thread(
            target=app.run,
            name="ibkr-market-data-type-reader",
            daemon=True,
        )
        reader_thread.start()

        if not app.next_valid_id_event.wait(timeout):
            return _market_data_result(
                app,
                instrument.symbol,
                requested_market_data_type,
                ok=False,
                message="Connected socket did not reach nextValidId.",
            )

        app.reqMarketDataType(requested_market_data_type)
        app.reqMktData(req_id, to_ib_contract(instrument), "", False, False, [])
        app.market_data_type_event.wait(timeout)
        app.cancelMktData(req_id)

        if app.received_market_data_type is None:
            return _market_data_result(
                app,
                instrument.symbol,
                requested_market_data_type,
                ok=False,
                message="Timed out waiting for marketDataType callback.",
            )

        label = MARKET_DATA_TYPE_LABELS.get(app.received_market_data_type, "unknown")
        return _market_data_result(
            app,
            instrument.symbol,
            requested_market_data_type,
            ok=True,
            message=f"Received {label} market data type callback.",
        )
    except Exception as exc:  # pragma: no cover - depends on TWS state
        return _market_data_result(
            app,
            instrument.symbol,
            requested_market_data_type,
            ok=False,
            message=f"Market data type probe failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if app.isConnected():
            app.disconnect()
        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=2)


def _market_data_result(
    app: MarketDataTypeApp,
    symbol: str,
    requested_market_data_type: int,
    ok: bool,
    message: str,
) -> MarketDataStatusResult:
    label = MARKET_DATA_TYPE_LABELS.get(app.received_market_data_type or 0, "unknown")
    blocking_errors = tuple(
        item
        for item in app.error_messages
        if not item.startswith("-1:2104:")
        and not item.startswith("-1:2106:")
        and not item.startswith("-1:2158:")
    )
    return MarketDataStatusResult(
        ok=ok and not blocking_errors,
        symbol=symbol,
        requested_market_data_type=requested_market_data_type,
        received_market_data_type=app.received_market_data_type,
        received_market_data_label=label,
        errors=tuple(app.error_messages),
        message=message if not blocking_errors else "; ".join(blocking_errors),
    )
