"""Interactive Brokers paper connection smoke-test client.

This module intentionally does not place orders. It verifies that TWS or
IB Gateway is reachable, that account data can be read, and that the selected
account is a paper account when paper-only mode is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any

from trading_strategy_tester.config import IbkrSettings

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
except ImportError as exc:  # pragma: no cover - covered by environment setup
    EClient = object  # type: ignore[assignment,misc]
    EWrapper = object  # type: ignore[assignment,misc]
    IBAPI_IMPORT_ERROR = exc
else:
    IBAPI_IMPORT_ERROR = None


@dataclass(frozen=True)
class IbkrConnectionResult:
    ok: bool
    host: str
    port: int
    client_id: int
    selected_account: str
    managed_accounts: tuple[str, ...] = ()
    account_summary: dict[str, dict[str, str]] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    message: str = ""


class PaperConnectionApp(EWrapper, EClient):  # type: ignore[misc]
    """Small IBKR app that reads connection/account state only."""

    def __init__(self) -> None:
        if IBAPI_IMPORT_ERROR is not None:
            raise RuntimeError("ibapi is not installed") from IBAPI_IMPORT_ERROR
        EClient.__init__(self, self)
        self.next_valid_id_event = threading.Event()
        self.managed_accounts_event = threading.Event()
        self.account_summary_end_event = threading.Event()
        self.current_time_event = threading.Event()
        self.next_order_id: int | None = None
        self.current_time: int | None = None
        self.managed_accounts_list: list[str] = []
        self.account_summary_values: dict[str, dict[str, str]] = {}
        self.error_messages: list[str] = []

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBKR callback name
        self.next_order_id = orderId
        self.next_valid_id_event.set()

    def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
        self.managed_accounts_list = [
            account.strip()
            for account in accountsList.split(",")
            if account.strip()
        ]
        self.managed_accounts_event.set()

    def accountSummary(  # noqa: N802
        self,
        reqId: int,
        account: str,
        tag: str,
        value: str,
        currency: str,
    ) -> None:
        account_values = self.account_summary_values.setdefault(account, {})
        account_values[tag] = f"{value} {currency}".strip()

    def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802
        self.account_summary_end_event.set()

    def currentTime(self, time: int) -> None:  # noqa: N802,A002
        self.current_time = time
        self.current_time_event.set()

    def error(self, reqId: int, errorCode: int, errorString: str, *args: Any) -> None:
        self.error_messages.append(f"{reqId}:{errorCode}:{errorString}")


def format_startup_warning(
    settings: IbkrSettings,
    instruments: list[str] | None = None,
    max_daily_loss: float | None = None,
    max_position_size: int | None = None,
) -> str:
    instrument_text = ", ".join(instruments or []) or "(none configured)"
    return "\n".join(
        [
            "=" * 78,
            "IBKR PAPER CONNECTION STARTUP CHECK",
            f"account: {settings.account or '(auto-detect)'}",
            f"mode: paper_only={settings.paper_trading_only}, trading_enabled={settings.trading_enabled}",
            f"host: {settings.host}",
            f"port: {settings.port}",
            f"client_id: {settings.client_id}",
            f"instruments: {instrument_text}",
            f"max_daily_loss: {max_daily_loss if max_daily_loss is not None else '(not loaded)'}",
            f"max_position_size: {max_position_size if max_position_size is not None else '(not loaded)'}",
            "No orders are sent by this smoke test.",
            "=" * 78,
        ]
    )


def check_paper_connection(settings: IbkrSettings) -> IbkrConnectionResult:
    """Connect to IBKR and verify paper account visibility."""

    if IBAPI_IMPORT_ERROR is not None:
        return IbkrConnectionResult(
            ok=False,
            host=settings.host,
            port=settings.port,
            client_id=settings.client_id,
            selected_account=settings.account,
            message=f"ibapi is not installed: {IBAPI_IMPORT_ERROR}",
        )

    app = PaperConnectionApp()
    reader_thread: threading.Thread | None = None
    try:
        app.connect(settings.host, settings.port, settings.client_id)
        reader_thread = threading.Thread(
            target=app.run,
            name="ibkr-paper-connection-reader",
            daemon=True,
        )
        reader_thread.start()

        if not app.next_valid_id_event.wait(settings.connection_timeout_seconds):
            return _result_from_app(
                app,
                settings,
                ok=False,
                selected_account=settings.account,
                message=(
                    "Connected socket did not receive nextValidId. "
                    "Confirm TWS/IB Gateway API is enabled and the port is paper mode."
                ),
            )

        app.reqCurrentTime()
        if not app.current_time_event.wait(settings.connection_timeout_seconds):
            return _result_from_app(
                app,
                settings,
                ok=False,
                selected_account=settings.account,
                message=(
                    "Connection reached nextValidId, but reqCurrentTime did not respond. "
                    "Do not continue until the API request/response path is stable."
                ),
            )

        app.reqManagedAccts()
        app.managed_accounts_event.wait(settings.connection_timeout_seconds)
        accounts = tuple(app.managed_accounts_list)
        selected_account = settings.account or (accounts[0] if accounts else "")

        if not selected_account:
            return _result_from_app(
                app,
                settings,
                ok=False,
                selected_account="",
                message="Connected, but no managed account was reported by IBKR.",
            )

        if selected_account not in accounts:
            return _result_from_app(
                app,
                settings,
                ok=False,
                selected_account=selected_account,
                message=(
                    f"Configured account {selected_account!r} is not in managed accounts: "
                    f"{', '.join(accounts) or '(none)'}"
                ),
            )

        if settings.paper_trading_only and settings.require_du_account:
            if not selected_account.upper().startswith("DU"):
                return _result_from_app(
                    app,
                    settings,
                    ok=False,
                    selected_account=selected_account,
                    message=(
                        f"Refusing non-paper account {selected_account!r}; "
                        "paper accounts normally start with DU."
                    ),
                )

        req_id = 9001
        app.reqAccountSummary(
            req_id,
            "All",
            "NetLiquidation,TotalCashValue,BuyingPower,AccountType",
        )
        app.account_summary_end_event.wait(settings.connection_timeout_seconds)
        app.cancelAccountSummary(req_id)

        return _result_from_app(
            app,
            settings,
            ok=True,
            selected_account=selected_account,
            message="IBKR paper connection check passed.",
        )
    except Exception as exc:  # pragma: no cover - depends on local TWS state
        return _result_from_app(
            app,
            settings,
            ok=False,
            selected_account=settings.account,
            message=f"IBKR connection check failed: {type(exc).__name__}: {exc}",
        )
    finally:
        if app.isConnected():
            app.disconnect()
        if reader_thread and reader_thread.is_alive():
            reader_thread.join(timeout=2)


def _result_from_app(
    app: PaperConnectionApp,
    settings: IbkrSettings,
    ok: bool,
    selected_account: str,
    message: str,
) -> IbkrConnectionResult:
    return IbkrConnectionResult(
        ok=ok,
        host=settings.host,
        port=settings.port,
        client_id=settings.client_id,
        selected_account=selected_account,
        managed_accounts=tuple(app.managed_accounts_list),
        account_summary=dict(app.account_summary_values),
        errors=tuple(app.error_messages),
        message=message,
    )
