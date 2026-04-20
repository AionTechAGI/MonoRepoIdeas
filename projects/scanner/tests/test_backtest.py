from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from src.backtest import run_undervaluation_backtest


def fake_download(*args, **kwargs):
    dates = pd.date_range("2024-01-02", periods=4, freq="B")
    close = pd.DataFrame(
        {
            "AAA": [100.0, 103.0, 104.0, 106.0],
            "BBB": [100.0, 98.0, 97.0, 96.0],
            "QQQ": [100.0, 101.0, 102.0, 103.0],
            "SPY": [100.0, 100.5, 101.0, 101.5],
        },
        index=dates,
    )
    return pd.concat({"Close": close}, axis=1)


class BacktestCostTests(unittest.TestCase):
    @patch("src.backtest.yf.download", side_effect=fake_download)
    def test_costs_reduce_ending_value(self, _mock_download):
        screen = pd.DataFrame(
            [
                {"ticker": "AAA", "company_name": "AAA Corp", "sector": "Technology", "undervaluation_pct": 20.0, "status": "ok"},
                {"ticker": "BBB", "company_name": "BBB Corp", "sector": "Industrials", "undervaluation_pct": 10.0, "status": "ok"},
            ]
        )
        no_cost = run_undervaluation_backtest(
            screen_df=screen,
            analysis_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10_000.0,
            portfolio_size=2,
            strategy_mode="long_only",
            commission_per_order=0.0,
            slippage_bps=0.0,
            borrow_cost_pct=0.0,
            liquidate_at_end=False,
        )
        with_cost = run_undervaluation_backtest(
            screen_df=screen,
            analysis_date="2024-01-01",
            end_date="2024-01-31",
            initial_capital=10_000.0,
            portfolio_size=2,
            strategy_mode="long_only",
            commission_per_order=2.0,
            slippage_bps=10.0,
            borrow_cost_pct=0.0,
            liquidate_at_end=True,
        )
        self.assertLess(
            with_cost.results[with_cost.portfolio_label].metrics["ending_value"],
            no_cost.results[no_cost.portfolio_label].metrics["ending_value"],
        )


if __name__ == "__main__":
    unittest.main()
