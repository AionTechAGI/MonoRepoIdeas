import sys
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from trading_strategy_tester.data.range_downloader import (
    format_ibkr_end_datetime,
    monthly_chunks,
    parse_ibkr_bar_timestamp,
)


class RangeDownloaderTests(unittest.TestCase):
    def test_monthly_chunks_cover_requested_range(self):
        chunks = monthly_chunks(date(2026, 1, 1), date(2026, 5, 14))

        self.assertEqual(len(chunks), 5)
        self.assertEqual(chunks[0].start, date(2026, 1, 1))
        self.assertEqual(chunks[0].end, date(2026, 1, 31))
        self.assertEqual(chunks[-1].start, date(2026, 5, 1))
        self.assertEqual(chunks[-1].end, date(2026, 5, 14))

    def test_format_ibkr_end_datetime(self):
        self.assertEqual(
            format_ibkr_end_datetime(date(2026, 5, 14)),
            "20260514 16:00:00 US/Eastern",
        )

    def test_parse_ibkr_bar_timestamp_handles_extra_spaces(self):
        parsed = parse_ibkr_bar_timestamp("20260514  15:30:00")

        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.hour, 15)
        self.assertEqual(parsed.minute, 30)


if __name__ == "__main__":
    unittest.main()
