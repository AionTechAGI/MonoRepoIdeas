from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceAccessRule:
    source: str
    access_mode: str
    app_status: str
    legal_path: str
    app_support: str
    official_reference: str
    note: str


@dataclass(frozen=True)
class BacktestAssumptions:
    strategy_mode: str
    portfolio_size: int
    initial_capital: float
    commission_per_order: float
    slippage_bps: float
    borrow_cost_pct: float
    liquidate_at_end: bool
    benchmark: str
