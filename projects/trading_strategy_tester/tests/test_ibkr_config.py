import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.config import IbkrSettings, load_ibkr_settings
from trading_strategy_tester.data.ibkr_client import format_startup_warning


class IbkrConfigTests(unittest.TestCase):
    def test_default_config_is_paper_only_and_trading_disabled(self):
        settings = load_ibkr_settings(PROJECT_ROOT / "config" / "ibkr_config.yaml")

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 7497)
        self.assertTrue(settings.paper_trading_only)
        self.assertFalse(settings.trading_enabled)
        self.assertTrue(settings.require_du_account)

    def test_startup_warning_shows_safety_fields(self):
        settings = IbkrSettings(account="DU1234567", trading_enabled=False)

        warning = format_startup_warning(
            settings,
            instruments=["SPY"],
            max_daily_loss=500.0,
            max_position_size=100,
        )

        self.assertIn("DU1234567", warning)
        self.assertIn("paper_only=True", warning)
        self.assertIn("trading_enabled=False", warning)
        self.assertIn("No orders are sent", warning)
        self.assertIn("SPY", warning)


if __name__ == "__main__":
    unittest.main()
