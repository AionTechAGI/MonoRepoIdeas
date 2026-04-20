from __future__ import annotations

import unittest
from datetime import UTC, datetime

import pandas as pd

from src.data_sources import StockSnapshot
from src.valuation import compute_house_valuation


def make_snapshot(**overrides) -> StockSnapshot:
    base = dict(
        ticker="TEST",
        company_name="Test Co",
        sector="Technology",
        industry="Software",
        exchange="NASDAQ",
        website="https://example.com",
        currency="USD",
        current_price=100.0,
        market_cap=10_000_000_000.0,
        shares_outstanding=100_000_000.0,
        book_value_per_share=20.0,
        beta=1.2,
        revenue_growth=0.12,
        earnings_growth=0.15,
        trailing_eps=4.0,
        forward_eps=5.0,
        total_cash=2_000_000_000.0,
        total_debt=500_000_000.0,
        profit_margin=0.20,
        operating_margin=0.25,
        return_on_equity=0.22,
        annual_free_cash_flow=[900_000_000.0, 850_000_000.0, 800_000_000.0],
        annual_revenue=[10_000_000_000.0, 9_200_000_000.0, 8_600_000_000.0],
        annual_net_income=[2_000_000_000.0, 1_700_000_000.0, 1_500_000_000.0],
        annual_dates=["2025-12-31", "2024-12-31", "2023-12-31"],
        price_history=pd.DataFrame({"Close": [90.0, 95.0, 100.0]}, index=pd.date_range("2026-01-01", periods=3)),
        as_of=datetime(2026, 4, 19, tzinfo=UTC),
        fundamentals_as_of="2025-12-31",
        is_historical=False,
    )
    base.update(overrides)
    return StockSnapshot(**base)


class ValuationGuardrailTests(unittest.TestCase):
    def test_technology_guardrails_cap_extreme_upside(self):
        snapshot = make_snapshot()
        valuation = compute_house_valuation(snapshot, risk_free_rate=0.04)
        self.assertIsNotNone(valuation.blended_fair_value)
        self.assertLessEqual(valuation.blended_fair_value, snapshot.current_price * 1.80 + 1e-6)
        self.assertGreaterEqual(valuation.data_quality_score, 80)

    def test_financial_guardrails_cap_extreme_upside(self):
        snapshot = make_snapshot(
            sector="Financial Services",
            industry="Banks - Diversified",
            current_price=100.0,
            trailing_eps=9.0,
            forward_eps=10.0,
            book_value_per_share=70.0,
            annual_free_cash_flow=[],
        )
        valuation = compute_house_valuation(snapshot, risk_free_rate=0.04)
        self.assertIsNotNone(valuation.blended_fair_value)
        self.assertLessEqual(valuation.blended_fair_value, snapshot.current_price * 1.45 + 1e-6)


if __name__ == "__main__":
    unittest.main()
