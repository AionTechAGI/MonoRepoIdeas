import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.data.market_data_probe import MARKET_DATA_TYPE_LABELS


class MarketDataProbeTests(unittest.TestCase):
    def test_market_data_type_labels_cover_ibkr_values(self):
        self.assertEqual(MARKET_DATA_TYPE_LABELS[1], "live")
        self.assertEqual(MARKET_DATA_TYPE_LABELS[2], "frozen")
        self.assertEqual(MARKET_DATA_TYPE_LABELS[3], "delayed")
        self.assertEqual(MARKET_DATA_TYPE_LABELS[4], "delayed-frozen")


if __name__ == "__main__":
    unittest.main()
