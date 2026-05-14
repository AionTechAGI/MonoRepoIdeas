"""Read-only IBKR historical bar loader."""

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


@dataclass(frozen=True)
class HistoricalBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    wap: float | None
    bar_count: int | None


@dataclass(frozen=True)
class HistoricalDataResult:
    ok: bool
    symbol: str
    bars: tuple[HistoricalBar, ...]
    errors: tuple[str, ...] = ()
    message: str = ""


class HistoricalDataApp(EWrapper, EClient):  # type: ignore[misc]
    def __init__(self) -> None:
        if IBAPI_IMPORT_ERROR is not None:
            raise RuntimeError("ibapi is not installed") from IBAPI_IMPORT_ERROR
        EClient.__init__(self, self)
        self.next_valid_id_event = threading.Event()
        self.historical_data_end_event = threading.Event()
        self.bars: list[HistoricalBar] = []
        self.error_messages: list[str] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802
        self.next_valid_id_event.set()

    def historicalData(self, reqId: int, bar: Any) -> None:  # noqa: N802
        self.bars.append(
            HistoricalBar(
                timestamp=str(bar.date),
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=_optional_float(getattr(bar, "volume", None)),
                wap=_optional_float(getattr(bar, "average", None)),
                bar_count=_optional_int(getattr(bar, "barCount", None)),
            )
        )

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
        self.historical_data_end_event.set()

    def error(self, reqId: int, errorCode: int, errorString: str, *args: Any) -> None:
        self.error_messages.append(f"{reqId}:{errorCode}:{errorString}")


def request_historical_bars(
    settings: IbkrSettings,
    instrument: Instrument,
    duration: str = "1 D",
    bar_size: str = "1 min",
    what_to_show: str = "TRADES",
    use_rth: bool = True,
    market_data_type: int = 1,
    timeout_seconds: float | None = None,
) -> HistoricalDataResult:
    """Request a historical bar sample from IBKR.

    This is read-only and does not place orders.
    """

    if IBAPI_IMPORT_ERROR is not None:
        return HistoricalDataResult(
            ok=False,
            symbol=instrument.symbol,
            bars=(),
            message=f"ibapi is not installed: {IBAPI_IMPORT_ERROR}",
        )

    timeout = timeout_seconds or settings.connection_timeout_seconds
    app = HistoricalDataApp()
    reader_thread: threading.Thread | None = None
    try:
        app.connect(settings.host, settings.port, settings.client_id)
        reader_thread = threading.Thread(
            target=app.run,
            name="ibkr-historical-reader",
            daemon=True,
        )
        reader_thread.start()

        if not app.next_valid_id_event.wait(timeout):
            return _historical_result(
                app,
                instrument.symbol,
                ok=False,
                message="Connected socket did not reach nextValidId.",
            )

        app.reqMarketDataType(market_data_type)
        app.reqHistoricalData(
            9101,
            to_ib_contract(instrument),
            "",
            duration,
            bar_size,
            what_to_show,
            1 if use_rth else 0,
            1,
            False,
            [],
        )

        if not app.historical_data_end_event.wait(timeout):
            return _historical_result(
                app,
                instrument.symbol,
                ok=False,
                message="Timed out waiting for historicalDataEnd.",
            )

        return _historical_result(
            app,
            instrument.symbol,
            ok=True,
            message=f"Received {len(app.bars)} historical bars.",
        )
    except Exception as exc:  # pragma: no cover - depends on TWS state
        return _historical_result(
            app,
            instrument.symbol,
            ok=False,
            message=f"Historical request failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if app.isConnected():
            app.disconnect()
        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=2)


def _historical_result(
    app: HistoricalDataApp,
    symbol: str,
    ok: bool,
    message: str,
) -> HistoricalDataResult:
    blocking_errors = tuple(
        item
        for item in app.error_messages
        if not item.startswith("-1:2104:")
        and not item.startswith("-1:2106:")
        and not item.startswith("-1:2158:")
    )
    return HistoricalDataResult(
        ok=ok and not blocking_errors,
        symbol=symbol,
        bars=tuple(app.bars),
        errors=tuple(app.error_messages),
        message=message if not blocking_errors else "; ".join(blocking_errors),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
