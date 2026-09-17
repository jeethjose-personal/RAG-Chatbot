"""Phase 7: End-to-End Factual Grounding & Accuracy Verification Benchmark.

Tests 25 factual queries across 5 core attributes (Expense Ratio, Exit Load,
Minimum SIP, Lock-in Period, Benchmark Index) across all 5 supported schemes.

Asserts:
1. is_valid == True
2. sentence_count <= 3
3. Ground-truth verified metric values match the official Groww HTML data
4. Exact 1 citation matching the specific scheme's canonical Groww URL verbatim
5. Mandatory footer presence
"""

import unittest
from src.config import ALLOWED_URLS
from src.rag.generator import ConstrainedGenerator
from src.rag.retriever import SchemeRetriever
from src.rag.validator import ResponseValidator


class TestFactualAccuracyBenchmark(unittest.TestCase):
    """Phase 7 Compliance: 25 Factual Queries Grounding Benchmark."""

    @classmethod
    def setUpClass(cls):
        cls.retriever = SchemeRetriever()
        cls.generator = ConstrainedGenerator()
        cls.validator = ResponseValidator()

    def _verify_factual_query(self, query: str, expected_metric: str, expected_url: str):
        """Helper to assert compliance on each factual query."""
        ctx = self.retriever.retrieve(query)
        ans = self.generator.generate(query, ctx)

        # 1. Output Validator Check
        report = self.validator.validate(ans.answer_text)
        self.assertTrue(report.is_valid, f"Validation failed: {report.rejection_reason}")
        self.assertLessEqual(ans.sentence_count, 3)
        self.assertGreaterEqual(ans.sentence_count, 1)

        # 2. Canonical Citation Whitelist Check
        self.assertEqual(ans.citation_url, expected_url)
        self.assertIn(ans.citation_url, ALLOWED_URLS)

        # 3. Ground-Truth Match
        self.assertIn(
            expected_metric.lower(),
            ans.answer_text.lower(),
            f"Expected metric '{expected_metric}' not found in answer for query: '{query}'. Answer: '{ans.answer_text}'"
        )

        # 4. Mandatory Footer Check
        self.assertIn("Last updated from sources:", ans.answer_text)

    # -------------------------------------------------------------
    # 1. HDFC Mid-Cap Opportunities Fund Direct Growth (5 Queries)
    # -------------------------------------------------------------
    def test_01_hdfc_mid_cap_expense_ratio(self):
        self._verify_factual_query(
            "What is the expense ratio for HDFC Mid Cap Direct Growth?",
            "0.76%",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

    def test_02_hdfc_mid_cap_exit_load(self):
        self._verify_factual_query(
            "What is the exit load of HDFC Mid Cap?",
            "1%",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

    def test_03_hdfc_mid_cap_lock_in(self):
        self._verify_factual_query(
            "What is the lock-in period for HDFC Mid Cap?",
            "no mandatory lock-in",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

    def test_04_hdfc_mid_cap_benchmark(self):
        self._verify_factual_query(
            "What is the benchmark of HDFC Mid Cap?",
            "NIFTY Midcap 150",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

    def test_05_hdfc_mid_cap_min_sip(self):
        self._verify_factual_query(
            "What is the minimum SIP for HDFC Mid Cap?",
            "100",
            "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
        )

    # -------------------------------------------------------------
    # 2. HDFC Flexi Cap Fund Direct Growth (5 Queries)
    # -------------------------------------------------------------
    def test_06_hdfc_flexi_cap_expense_ratio(self):
        self._verify_factual_query(
            "What is the expense ratio for HDFC Flexi Cap?",
            "0.77%",
            "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        )

    def test_07_hdfc_flexi_cap_exit_load(self):
        self._verify_factual_query(
            "What is the exit load for HDFC Flexi Cap Fund?",
            "1%",
            "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        )

    def test_08_hdfc_flexi_cap_lock_in(self):
        self._verify_factual_query(
            "What is the lock-in period for HDFC Flexi Cap?",
            "no mandatory lock-in",
            "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        )

    def test_09_hdfc_flexi_cap_benchmark(self):
        self._verify_factual_query(
            "What is the benchmark index for HDFC Flexi Cap?",
            "NIFTY 500",
            "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        )

    def test_10_hdfc_flexi_cap_min_sip(self):
        self._verify_factual_query(
            "What is the minimum SIP amount for HDFC Flexi Cap?",
            "100",
            "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth"
        )

    # -------------------------------------------------------------
    # 3. HDFC Focused 30 Fund Direct Growth (5 Queries)
    # -------------------------------------------------------------
    def test_11_hdfc_focused_expense_ratio(self):
        self._verify_factual_query(
            "What is the expense ratio for HDFC Focused 30?",
            "0.82%",
            "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"
        )

    def test_12_hdfc_focused_exit_load(self):
        self._verify_factual_query(
            "What is the exit load of HDFC Focused 30?",
            "1%",
            "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"
        )

    def test_13_hdfc_focused_lock_in(self):
        self._verify_factual_query(
            "What is the lock in period of HDFC Focused 30?",
            "no mandatory lock-in",
            "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"
        )

    def test_14_hdfc_focused_benchmark(self):
        self._verify_factual_query(
            "What is the benchmark index for HDFC Focused Fund?",
            "NIFTY 500",
            "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"
        )

    def test_15_hdfc_focused_min_sip(self):
        self._verify_factual_query(
            "What is the minimum SIP investment for HDFC Focused 30?",
            "100",
            "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth"
        )

    # -------------------------------------------------------------
    # 4. HDFC ELSS Tax Saver Fund Direct Plan Growth (5 Queries)
    # -------------------------------------------------------------
    def test_16_hdfc_elss_expense_ratio(self):
        self._verify_factual_query(
            "What is the expense ratio for HDFC ELSS Tax Saver?",
            "1.21%",
            "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
        )

    def test_17_hdfc_elss_exit_load(self):
        self._verify_factual_query(
            "What is the exit load for HDFC ELSS Tax Saver?",
            "Nil",
            "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
        )

    def test_18_hdfc_elss_lock_in(self):
        self._verify_factual_query(
            "What is the lock in period of HDFC ELSS Tax Saver?",
            "3 years",
            "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
        )

    def test_19_hdfc_elss_benchmark(self):
        self._verify_factual_query(
            "What is the benchmark for HDFC ELSS Tax Saver?",
            "NIFTY 500",
            "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
        )

    def test_20_hdfc_elss_min_sip(self):
        self._verify_factual_query(
            "What is the minimum SIP for HDFC ELSS Tax Saver?",
            "500",
            "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth"
        )

    # -------------------------------------------------------------
    # 5. HDFC Top 100 Fund Direct Growth (5 Queries)
    # -------------------------------------------------------------
    def test_21_hdfc_top_100_expense_ratio(self):
        self._verify_factual_query(
            "What is the expense ratio for HDFC Top 100?",
            "1.03%",
            "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
        )

    def test_22_hdfc_top_100_exit_load(self):
        self._verify_factual_query(
            "What is the exit load for HDFC Top 100 Fund?",
            "1%",
            "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
        )

    def test_23_hdfc_top_100_lock_in(self):
        self._verify_factual_query(
            "What is the lock-in period for HDFC Top 100?",
            "no mandatory lock-in",
            "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
        )

    def test_24_hdfc_top_100_benchmark(self):
        self._verify_factual_query(
            "What is the benchmark for HDFC Top 100?",
            "NIFTY 100",
            "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
        )

    def test_25_hdfc_top_100_min_sip(self):
        self._verify_factual_query(
            "What is the minimum SIP for HDFC Top 100?",
            "100",
            "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
        )


if __name__ == "__main__":
    unittest.main()
