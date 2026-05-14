"""Configuration loading helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class IbkrSettings:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 3101
    account: str = ""
    paper_trading_only: bool = True
    trading_enabled: bool = False
    allow_delayed_data_for_testing: bool = False
    connection_timeout_seconds: float = 15.0
    require_du_account: bool = True

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "IbkrSettings":
        startup_warning = raw.get("startup_warning") or {}
        return cls(
            host=str(raw.get("host", cls.host)),
            port=int(raw.get("port", cls.port)),
            client_id=int(raw.get("client_id", cls.client_id)),
            account=str(raw.get("account", cls.account) or ""),
            paper_trading_only=bool(raw.get("paper_trading_only", cls.paper_trading_only)),
            trading_enabled=bool(raw.get("trading_enabled", cls.trading_enabled)),
            allow_delayed_data_for_testing=bool(
                raw.get(
                    "allow_delayed_data_for_testing",
                    cls.allow_delayed_data_for_testing,
                )
            ),
            connection_timeout_seconds=float(
                raw.get("connection_timeout_seconds", cls.connection_timeout_seconds)
            ),
            require_du_account=bool(
                startup_warning.get("require_du_account", cls.require_du_account)
            ),
        )


def load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping in YAML config: {config_path}")
    return loaded


def load_ibkr_settings(path: str | Path) -> IbkrSettings:
    return IbkrSettings.from_mapping(load_yaml(path))
