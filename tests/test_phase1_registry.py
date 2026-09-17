"""Unit tests for Phase 1: Corpus Definition and Whitelist Lock."""

import unittest
from pathlib import Path

from src.config import (
    ALLOWED_URLS,
    EXPECTED_SCHEME_COUNT,
    REGISTRY_FILE,
    TARGET_AMC,
    is_allowed_url,
)
from src.ingestion.registry import CorpusRegistry, SchemeRecord, load_corpus_registry


class TestPhase1CorpusRegistry(unittest.TestCase):
    """Tests Phase 1 corpus registry invariants and URL whitelist enforcement."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_corpus_registry()

    def test_expected_scheme_count(self) -> None:
        """Verify that the registry contains exactly 5 schemes."""
        self.assertEqual(len(self.registry.schemes), EXPECTED_SCHEME_COUNT)
        self.assertEqual(self.registry.total_schemes, EXPECTED_SCHEME_COUNT)

    def test_target_amc(self) -> None:
        """Verify that the AMC is strictly HDFC Mutual Fund."""
        self.assertEqual(self.registry.amc_name, TARGET_AMC)

    def test_url_whitelist_exact_match(self) -> None:
        """Verify that every scheme's source URL matches ALLOWED_URLS exactly."""
        registered_urls = set(self.registry.get_all_canonical_urls())
        self.assertEqual(registered_urls, set(ALLOWED_URLS))

    def test_no_external_domains(self) -> None:
        """Verify that zero external domains (e.g. sebi, amfi, hdfcfund pdfs) exist in registry."""
        forbidden_substrings = ["sebi.gov.in", "amfiindia.com", "hdfcfund.com", ".pdf"]
        for scheme in self.registry.schemes:
            for forbidden in forbidden_substrings:
                self.assertNotIn(
                    forbidden,
                    scheme.source_url.lower(),
                    f"Forbidden domain/token '{forbidden}' found in URL: {scheme.source_url}",
                )

    def test_unique_scheme_ids(self) -> None:
        """Verify that all scheme IDs are unique and well-formed."""
        ids = [s.scheme_id for s in self.registry.schemes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_category_diversity(self) -> None:
        """Verify category diversity across the 5 schemes."""
        categories = {s.category for s in self.registry.schemes}
        self.assertEqual(len(categories), 5)
        expected_categories = {
            "Mid Cap Fund",
            "Flexi Cap Fund",
            "Focused Fund",
            "ELSS (Equity Linked Savings Scheme)",
            "Large Cap Fund",
        }
        self.assertEqual(categories, expected_categories)

    def test_scheme_resolution_from_aliases(self) -> None:
        """Verify alias resolution for ambiguous or colloquial user inputs."""
        test_cases = [
            ("What is the exit load for HDFC Flexi Cap?", "hdfc_flexi_cap_fund"),
            ("Tell me about HDFC Top 100", "hdfc_large_cap_fund"),
            ("Lock in period for tax saver fund", "hdfc_elss_tax_saver_fund"),
            ("HDFC Mid Cap opportunities min sip", "hdfc_mid_cap_fund"),
            ("HDFC Focused 30 fund details", "hdfc_focused_fund"),
        ]
        for query, expected_id in test_cases:
            scheme = self.registry.resolve_scheme_from_text(query)
            self.assertIsNotNone(scheme, f"Failed to resolve scheme for query: '{query}'")
            self.assertEqual(scheme.scheme_id, expected_id)

    def test_is_allowed_url_helper(self) -> None:
        """Verify that is_allowed_url returns True only for whitelisted URLs."""
        for url in ALLOWED_URLS:
            self.assertTrue(is_allowed_url(url))

        # Test rejected URLs
        invalid_urls = [
            "https://groww.in/mutual-funds/category/best-elss-funds",
            "https://groww.in/mutual-funds/sbi-small-cap-fund-direct-growth",
            "https://www.hdfcfund.com/content/factsheet.pdf",
            "https://www.amfiindia.com",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth/",  # Trailing slash
            "",
            None,
        ]
        for bad_url in invalid_urls:
            self.assertFalse(is_allowed_url(bad_url), f"Should reject invalid URL: {bad_url}")

    def test_unapproved_url_injection_raises_error(self) -> None:
        """Verify that injecting an unapproved URL raises a ValueError during validation."""
        bad_scheme = SchemeRecord(
            scheme_id="unapproved_fund",
            scheme_name="Unapproved Fund",
            display_name="Unapproved Fund",
            category="Small Cap",
            source_url="https://groww.in/mutual-funds/unapproved-fund",
            groww_slug="unapproved-fund",
            plan_type="Direct",
            option_type="Growth",
        )
        with self.assertRaises(ValueError) as ctx:
            bad_scheme.validate()
        self.assertIn("violates whitelist", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
