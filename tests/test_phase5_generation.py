"""Unit tests for Phase 5: Constrained Generation Engine & Output Validator."""

import unittest
from src.config import ALLOWED_URLS
from src.rag.generator import ConstrainedGenerator
from src.rag.retriever import SchemeRetriever
from src.rag.validator import ResponseValidator


class TestPhase5Validator(unittest.TestCase):
    """Tests the software output validation guard."""

    def setUp(self) -> None:
        self.validator = ResponseValidator()
        self.valid_url = list(ALLOWED_URLS)[0]

    def test_valid_compliant_response(self) -> None:
        """Verify that a compliant 2-sentence response with 1 citation and footer passes."""
        text = (
            f"The Total Expense Ratio for this fund is 0.76% inclusive of GST. "
            f"For complete details, visit the [Groww Scheme Page]({self.valid_url}).\n\n"
            f"Last updated from sources: 16-Sep-2026"
        )
        report = self.validator.validate(text)
        self.assertTrue(report.is_valid, f"Failed on valid text: {report.rejection_reason}")
        self.assertEqual(report.sentence_count, 2)
        self.assertEqual(report.cited_urls, [self.valid_url])

    def test_rejection_on_sentence_count_exceeded(self) -> None:
        """Verify that responses exceeding 3 sentences are rejected."""
        text = (
            f"Sentence one is here. Sentence two is here. Sentence three is here. Sentence four is here! "
            f"Source: [Groww]({self.valid_url})\n\n"
            f"Last updated from sources: 16-Sep-2026"
        )
        report = self.validator.validate(text)
        self.assertFalse(report.is_valid)
        self.assertIn("exceeds maximum of 3 sentences", report.rejection_reason)

    def test_rejection_on_missing_citation(self) -> None:
        """Verify that responses with 0 citation links are rejected."""
        text = (
            "The exit load is 1% within 1 year.\n\n"
            "Last updated from sources: 16-Sep-2026"
        )
        report = self.validator.validate(text)
        self.assertFalse(report.is_valid)
        self.assertIn("Expected exactly 1 citation link", report.rejection_reason)

    def test_rejection_on_multiple_citations(self) -> None:
        """Verify that responses with 2+ citation links are rejected."""
        text = (
            f"Check [Link 1]({self.valid_url}) and also check [Link 2]({self.valid_url}).\n\n"
            f"Last updated from sources: 16-Sep-2026"
        )
        report = self.validator.validate(text)
        self.assertFalse(report.is_valid)
        self.assertIn("Expected exactly 1 citation link", report.rejection_reason)

    def test_rejection_on_unapproved_citation_url(self) -> None:
        """Verify that citations to non-whitelisted domains are strictly rejected."""
        unapproved_urls = [
            "https://www.amfiindia.com",
            "https://sebi.gov.in/circular.pdf",
            "https://www.hdfcfund.com/factsheet.pdf",
            "https://groww.in/mutual-funds/sbi-small-cap-fund-direct-growth",
        ]
        for bad_url in unapproved_urls:
            text = (
                f"The exit load is 1%. See [Details]({bad_url}).\n\n"
                f"Last updated from sources: 16-Sep-2026"
            )
            report = self.validator.validate(text)
            self.assertFalse(report.is_valid)
            self.assertIn("violates whitelist", report.rejection_reason)

    def test_rejection_on_missing_footer(self) -> None:
        """Verify that responses missing the mandatory footer are rejected."""
        text = f"The exit load is 1%. See [Groww]({self.valid_url})."
        report = self.validator.validate(text)
        self.assertFalse(report.is_valid)
        self.assertIn("Missing mandatory footer prefix", report.rejection_reason)

    def test_repair_or_format_creates_compliant_response(self) -> None:
        """Verify that repair_or_format produces 100% compliant output from raw text."""
        raw_input = "HDFC Flexi Cap is an open-ended equity scheme. The expense ratio is 0.77%. It is managed by experienced professionals. More details below."
        repaired = self.validator.repair_or_format(raw_input, self.valid_url)
        report = self.validator.validate(repaired)
        self.assertTrue(report.is_valid, f"Repaired text was not valid: {report.rejection_reason}")
        self.assertLessEqual(report.sentence_count, 3)


class TestPhase5Generator(unittest.TestCase):
    """Tests end-to-end constrained generation and factual synthesis."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.retriever = SchemeRetriever()
        cls.generator = ConstrainedGenerator()

    def test_factual_generation_end_to_end(self) -> None:
        """Verify that factual queries generate valid, constrained, source-backed answers."""
        factual_prompts = [
            "What is the exit load for HDFC Flexi Cap Fund?",
            "What is the lock in period for HDFC ELSS Tax Saver?",
            "What is the minimum SIP amount for HDFC Top 100 Fund?",
            "What is the benchmark index for HDFC Mid Cap?",
        ]
        for prompt in factual_prompts:
            ctx = self.retriever.retrieve(prompt)
            ans = self.generator.generate(prompt, ctx)

            # Assert complete compliance
            self.assertTrue(ans.is_valid, f"Generated answer is invalid: {ans.rejection_reason}")
            self.assertLessEqual(ans.sentence_count, 3)
            self.assertGreaterEqual(ans.sentence_count, 1)
            self.assertIn(ans.citation_url, ALLOWED_URLS)
            self.assertIn("Last updated from sources:", ans.answer_text)

    def test_ungrounded_query_generation(self) -> None:
        """Verify clean graceful response for queries with no retrieved facts."""
        empty_ctx = self.retriever.retrieve("What was the portfolio turnover in 1995?")
        # Force is_grounded = False
        empty_ctx.is_grounded = False
        empty_ctx.chunks = []
        ans = self.generator.generate("What was the portfolio turnover in 1995?", empty_ctx)

        self.assertTrue(ans.is_valid)
        self.assertIn("I do not have this factual information", ans.answer_text)
        self.assertEqual(ans.citation_url, "")
        self.assertEqual(len(self.generator.validator.extract_links(ans.answer_text)), 0)


if __name__ == "__main__":
    unittest.main()
