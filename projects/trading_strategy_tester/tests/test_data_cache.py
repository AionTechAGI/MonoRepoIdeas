import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.data.data_cache import (
    latest_cached_timestamp,
    upsert_bars,
)
from trading_strategy_tester.data.historical_loader import HistoricalBar


class DataCacheTests(unittest.TestCase):
    def test_upsert_bars_and_latest_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache.sqlite3"
            bars = [
                HistoricalBar(
                    timestamp="20260514 09:30:00",
                    open=100.0,
                    high=101.0,
                    low=99.5,
                    close=100.5,
                    volume=1000,
                    wap=100.25,
                    bar_count=10,
                ),
                HistoricalBar(
                    timestamp="20260514 09:31:00",
                    open=100.5,
                    high=101.5,
                    low=100.0,
                    close=101.0,
                    volume=1100,
                    wap=100.75,
                    bar_count=11,
                ),
            ]

            written = upsert_bars(cache, "SPY", "1 min", bars)

            self.assertEqual(written, 2)
            self.assertEqual(
                latest_cached_timestamp(cache, "SPY", "1 min"),
                "20260514 09:31:00",
            )


if __name__ == "__main__":
    unittest.main()
