"""Phase 7: Citation Whitelist Invariant & Domain Isolation Verification Suite.

Strictly verifies that:
1. 100% of generated responses cite strictly one URL.
2. That URL belongs to ALLOWED_URLS (the 5 whitelisted Groww URLs).
3. Zero occurrences of external domains (amfiindia.com, sebi.gov.in, hdfcfund.com, .pdf).
4. Missing information / ungrounded queries contain 0 citation links.
"""

import re
import unittest
from src.config import ALLOWED_URLS
from src.rag.generator import ConstrainedGenerator
from src.rag.retriever import SchemeRetriever
from src.rag.validator import ResponseValidator

FORBIDDEN_DOMAINS = [
    "amfiindia.com",
    "sebi.gov.in",
    "hdfcfund.com",
    "moneycontrol.com",
    "valueresearchonline.com",
    ".pdf",
]


class TestCitationWhitelistSuite(unittest.TestCase):
    """Phase 7 Compliance: Citation Whitelist & Domain Leakage Invariant Tests."""

    @classmethod
    def setUpClass(cls):
        cls.retriever = SchemeRetriever()
        cls.generator = ConstrainedGenerator()
        cls.validator = ResponseValidator()

    def test_all_five_schemes_cite_exact_canonical_groww_urls(self):
        """Verify that queries for each of the 5 schemes produce exact canonical citations."""
        queries_and_schemes = [
            ("What is the TER of HDFC Mid Cap Direct Growth?", "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"),
            ("What is the exit load for HDFC Flexi Cap?", "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"),
            ("What is the benchmark of HDFC Focused 30?", "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"),
            ("What is the lock in period of HDFC ELSS Tax Saver?", "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"),
            ("What is the minimum SIP for HDFC Top 100 Fund?", "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"),
        ]

        for query, expected_url in queries_and_schemes:
            with self.subTest(query=query):
                ctx = self.retriever.retrieve(query)
                ans = self.generator.generate(query, ctx)

                self.assertTrue(ans.is_valid)
                self.assertEqual(ans.citation_url, expected_url)
                self.assertIn(ans.citation_url, ALLOWED_URLS)

                # Extract markdown links
                links = self.validator.extract_links(ans.answer_text)
                self.assertEqual(len(links), 1)
                self.assertEqual(links[0][1], expected_url)

    def test_zero_forbidden_domain_leakage(self):
        """Verify that no external financial domains or PDF documents ever appear in answers."""
        sample_queries = [
            "What is the tax implication of HDFC Flexi Cap?",
            "What is the risk level of HDFC Top 100?",
            "Who manages HDFC Mid Cap Fund?",
            "What is the statutory lock-in period for HDFC ELSS?",
            "What is the expense ratio for HDFC Focused Fund?",
        ]

        for query in sample_queries:
            with self.subTest(query=query):
                ctx = self.retriever.retrieve(query)
                ans = self.generator.generate(query, ctx)

                # Check body text against all forbidden domains
                for forbidden in FORBIDDEN_DOMAINS:
                    self.assertNotIn(
                        forbidden,
                        ans.answer_text.lower(),
                        f"Forbidden domain '{forbidden}' leaked in response for: {query}"
                    )

    def test_ungrounded_query_has_zero_citations(self):
        """Verify that when factual information is not available, 0 citations are provided."""
        ungrounded_queries = [
            "What was the portfolio turnover ratio in 1990?",
            "What is the Sharpe ratio of HDFC Mid Cap?",
            "What is the dividend yield of HDFC Top 100?",
        ]

        for query in ungrounded_queries:
            with self.subTest(query=query):
                ctx = self.retriever.retrieve(query)
                ans = self.generator.generate(query, ctx)

                self.assertTrue(ans.is_valid)
                self.assertEqual(ans.citation_url, "")
                links = self.validator.extract_links(ans.answer_text)
                self.assertEqual(len(links), 0)
                self.assertIn("I do not have this factual information", ans.answer_text)


if __name__ == "__main__":
    unittest.main()
