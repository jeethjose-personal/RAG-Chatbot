"""Unit tests for Phase 2.1: Scheme HTML Scraping and Snapshot Integrity."""

import json
import re
import unittest
from pathlib import Path

from src.config import EXPECTED_SCHEME_COUNT, RAW_HTML_DIR
from src.ingestion.registry import load_corpus_registry
from src.ingestion.scraper import SchemeScraper


class TestPhase2Scraper(unittest.TestCase):
    """Tests that Phase 2.1 snapshots exist, are valid, and contain required mutual fund data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_corpus_registry()
        cls.scraper = SchemeScraper(registry=cls.registry)
        # Ensure snapshots are fetched
        cls.snapshots = cls.scraper.fetch_all(force_refresh=False)

    def test_all_five_snapshots_exist(self) -> None:
        """Verify that exactly 5 scheme HTML snapshots are present in data/raw_html."""
        html_files = list(RAW_HTML_DIR.glob("*.html"))
        self.assertEqual(len(html_files), EXPECTED_SCHEME_COUNT)

        for scheme in self.registry.schemes:
            expected_file = RAW_HTML_DIR / f"{scheme.scheme_id}.html"
            self.assertTrue(expected_file.exists(), f"Missing snapshot for {scheme.scheme_id}")
            self.assertGreater(
                expected_file.stat().st_size,
                50_000,
                f"Snapshot for {scheme.scheme_id} is suspiciously small",
            )

    def test_next_data_payload_integrity(self) -> None:
        """Verify that every HTML snapshot contains a valid, parseable __NEXT_DATA__ JSON payload."""
        for scheme in self.registry.schemes:
            file_path = RAW_HTML_DIR / f"{scheme.scheme_id}.html"
            content = file_path.read_text(encoding="utf-8")

            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
            self.assertIsNotNone(
                match,
                f"Missing __NEXT_DATA__ script block in {file_path.name}",
            )

            payload = json.loads(match.group(1))
            page_props = payload.get("props", {}).get("pageProps", {})
            mf_data = page_props.get("mfServerSideData")

            self.assertIsNotNone(
                mf_data,
                f"Missing mfServerSideData in pageProps of {file_path.name}",
            )

            # Assert core attributes are present and valid
            self.assertIn("expense_ratio", mf_data)
            self.assertIsNotNone(mf_data.get("expense_ratio"))
            self.assertIn("exit_load", mf_data)
            self.assertIn("min_sip_investment", mf_data)
            self.assertIn("benchmark_name", mf_data)

    def test_specific_scheme_ground_truth_attributes(self) -> None:
        """Verify specific ground truth facts extracted from the saved snapshots."""
        # Check ELSS has lock-in of 3 years
        elss_file = RAW_HTML_DIR / "hdfc_elss_tax_saver_fund.html"
        content = elss_file.read_text(encoding="utf-8")
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL)
        data = json.loads(match.group(1))
        elss_mf = data["props"]["pageProps"]["mfServerSideData"]

        self.assertEqual(elss_mf.get("lock_in", {}).get("years"), 3)
        self.assertEqual(elss_mf.get("exit_load"), "Nil")

        # Check Mid Cap has exit load of 1% within 1 year
        mid_file = RAW_HTML_DIR / "hdfc_mid_cap_fund.html"
        mid_content = mid_file.read_text(encoding="utf-8")
        mid_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', mid_content, re.DOTALL)
        mid_data = json.loads(mid_match.group(1))
        mid_mf = mid_data["props"]["pageProps"]["mfServerSideData"]

        self.assertIn("1%", mid_mf.get("exit_load", ""))
        self.assertEqual(mid_mf.get("min_sip_investment"), 100)


if __name__ == "__main__":
    unittest.main()
