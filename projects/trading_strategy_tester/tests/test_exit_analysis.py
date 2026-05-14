import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.backtest.exit_analysis import (
    ExitPolicy,
    collect_continuation_entries,
    simulate_exit_policy,
    summarize_mfe_mae,
)
from trading_strategy_tester.backtest.orb_vwap import BacktestConfig
from trading_strategy_tester.data.historical_loader import HistoricalBar


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


class ExitAnalysisTests(unittest.TestCase):
    def test_collects_continuation_entry_and_mfe(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 108, 103, 107),
        ]

        entries = collect_continuation_entries(
            bars,
            BacktestConfig(full_session_bars=5),
        )
        summary = summarize_mfe_mae(entries)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].direction, "LONG")
        self.assertGreater(summary["average_mfe_r"], 0)

    def test_fixed_target_policy_exits_at_target(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 110, 103, 107),
        ]
        entry = collect_continuation_entries(bars, BacktestConfig(full_session_bars=5))[0]

        result = simulate_exit_policy(entry, ExitPolicy(name="fixed_1R", fixed_target_r=1.0))

        self.assertEqual(result.exit_reason, "TARGET_1.00R")
        self.assertAlmostEqual(result.r_multiple, 1.0)

    def test_partial_policy_blends_realized_and_runner_pnl(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 110, 103, 109),
        ]
        entry = collect_continuation_entries(bars, BacktestConfig(full_session_bars=5))[0]

        result = simulate_exit_policy(
            entry,
            ExitPolicy(
                name="partial",
                partial_target_r=0.75,
                partial_fraction=0.5,
            ),
        )

        self.assertIn("PARTIAL", result.exit_reason)
        self.assertGreater(result.r_multiple, 0.75)

    def test_session_close_runner_keeps_original_stop(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 106, 98, 99),
        ]
        entry = collect_continuation_entries(bars, BacktestConfig(full_session_bars=5))[0]

        result = simulate_exit_policy(entry, ExitPolicy(name="session_close_runner"))

        self.assertEqual(result.exit_reason, "STOP")
        self.assertAlmostEqual(result.r_multiple, -1.0)

    def test_partial_breakeven_policy_stops_runner_at_entry(self):
        bars = [
            bar("20260102  15:30:00", 100, 101, 99, 100),
            bar("20260102  15:35:00", 100, 102, 100, 101),
            bar("20260102  15:40:00", 101, 103, 100, 102),
            bar("20260102  15:45:00", 102, 105, 102, 104),
            bar("20260102  15:50:00", 104, 110, 104, 109),
            bar("20260102  15:55:00", 109, 109, 103, 104),
        ]
        entry = collect_continuation_entries(bars, BacktestConfig(full_session_bars=6))[0]

        result = simulate_exit_policy(
            entry,
            ExitPolicy(
                name="partial_breakeven",
                partial_target_r=0.75,
                partial_fraction=0.5,
                move_stop_to_breakeven_after_partial=True,
            ),
        )

        self.assertEqual(result.exit_reason, "PARTIAL_STOP")
        self.assertAlmostEqual(result.r_multiple, 0.375)


if __name__ == "__main__":
    unittest.main()
