from __future__ import annotations

VALUATION_MODEL_VERSION = "valuation_v1.0"
DCF_MODEL_VERSION = "dcf_v1.0"
EARNINGS_MODEL_VERSION = "earnings_power_v1.0"
BLEND_MODEL_VERSION = "blend_v1.0"
BACKTEST_ENGINE_VERSION = "backtest_v1.0"

DEFAULT_INITIAL_CAPITAL = 10_000.0
DEFAULT_COMMISSION_PER_ORDER = 0.0
DEFAULT_SLIPPAGE_BPS = 0.0
DEFAULT_BORROW_COST_PCT = 0.0

SUPPORTED_SOURCE_STATUSES = (
    "ok",
    "partial",
    "not_visible",
    "failed",
    "stale",
    "requires_api_key",
    "requires_license",
    "requires_subscription",
    "rate_limited",
)
