import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.backtest.orb_vwap import (
    calculate_buy_and_hold,
    run_orb_vwap_backtest,
    summarize_trades,
)
from trading_strategy_tester.data.historical_loader import HistoricalBar
from trading_strategy_tester.strategy.opening_range import calculate_opening_range
from trading_strategy_tester.strategy.vwap import calculate_vwap_series


def bar(
    timestamp: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
) -> HistoricalBar:
    return HistoricalBar(
        timestamp=timestamp,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        wap=None,
        bar_count=None,
    )


class OrbVwapBacktestTests(unittest.TestCase):
    def test_opening_range_uses_first_three_bars(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
        ]

        opening_range = calculate_opening_range(bars, opening_range_bars=3)

        self.assertEqual(opening_range.high, 103)
        self.assertEqual(opening_range.low, 99)
        self.assertEqual(opening_range.mid, 101)
        self.assertEqual(opening_range.width, 4)

    def test_vwap_series_is_cumulative_intraday(self):
        bars = [
            bar("20260102  15:30:00", 100, 103, 99, 101, volume=100),
            bar("20260102  15:35:00", 101, 104, 100, 103, volume=300),
        ]

        vwaps = calculate_vwap_series(bars)

        first_typical = (103 + 99 + 101) / 3
        second_typical = (104 + 100 + 103) / 3
        expected_second = (first_typical * 100 + second_typical * 300) / 400
        self.assertAlmostEqual(vwaps[0], first_typical)
        self.assertAlmostEqual(vwaps[1], expected_second)

    def test_backtest_enters_long_on_or_breakout_above_vwap(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 110, 103, 107),
        ]

        result = run_orb_vwap_backtest(
            bars,
            opening_range_bars=3,
            full_session_bars=5,
            target_r=1.0,
        )

        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.direction, "LONG")
        self.assertEqual(trade.entry_timestamp, "20260102  15:50:00")
        self.assertEqual(trade.exit_reason, "TARGET")
        self.assertGreater(trade.r_multiple, 0)

    def test_buy_and_hold_uses_first_open_and_last_close(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260105  21:55:00", 110, 111, 109, 112),
        ]

        result = calculate_buy_and_hold(bars)

        self.assertEqual(result.entry_price, 100)
        self.assertEqual(result.exit_price, 112)
        self.assertEqual(result.pnl_per_share, 12)
        self.assertAlmostEqual(result.return_pct, 0.12)

    def test_summarize_empty_trades(self):
        summary = summarize_trades(())

        self.assertEqual(summary["trade_count"], 0)
        self.assertEqual(summary["gross_pnl_per_share"], 0.0)


if __name__ == "__main__":
    unittest.main()
