"""Unit tests for Phase 3: Vector Storage & Context Retrieval."""

import unittest
from pathlib import Path

from src.config import ALLOWED_URLS, CHROMA_DB_DIR
from src.ingestion.indexer import SchemeIndexer
from src.rag.retriever import SchemeRetriever


class TestPhase3Retrieval(unittest.TestCase):
    """Tests Phase 3 vector storage, ChromaDB indexing, and semantic retrieval."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.indexer = SchemeIndexer()
        cls.retriever = SchemeRetriever(indexer=cls.indexer)

    def test_chroma_db_directory_and_index_exist(self) -> None:
        """Verify that vector database storage files exist in data/chroma_db/."""
        self.assertTrue(CHROMA_DB_DIR.exists())
        # Check that either ChromaDB sqlite or local_index exists
        chroma_file = CHROMA_DB_DIR / "chroma.sqlite3"
        local_file = CHROMA_DB_DIR / "local_index.json"
        self.assertTrue(chroma_file.exists() or local_file.exists())

    def test_retrieval_citation_whitelist_invariant(self) -> None:
        """Verify that 100% of retrieved citation URLs are in ALLOWED_URLS verbatim."""
        queries = [
            "HDFC Mid Cap expense ratio",
            "What is the exit load for HDFC Flexi Cap?",
            "Lock in period for HDFC ELSS Tax Saver",
            "Minimum SIP in HDFC Top 100",
            "Who manages HDFC Focused 30?",
        ]
        for q in queries:
            result = self.retriever.retrieve(q)
            self.assertIn(
                result.canonical_citation_url,
                ALLOWED_URLS,
                f"Query '{q}' returned non-whitelisted URL: {result.canonical_citation_url}",
            )
            # Verify exactly 1 citation URL
            self.assertIsInstance(result.canonical_citation_url, str)
            self.assertTrue(result.canonical_citation_url.startswith("https://groww.in/mutual-funds/"))

    def test_semantic_topic_precision(self) -> None:
        """Verify that queries for specific topics retrieve the exact matching topic chunk."""
        topic_tests = [
            ("What is the exit load for HDFC Flexi Cap?", "hdfc_flexi_cap_fund", "exit_load"),
            ("What is the lock in period for HDFC ELSS Tax Saver?", "hdfc_elss_tax_saver_fund", "lock_in_period"),
            ("What is the expense ratio for HDFC Focused 30?", "hdfc_focused_fund", "expense_ratio"),
            ("What is the minimum SIP for HDFC Top 100?", "hdfc_large_cap_fund", "min_investment"),
            ("What is the benchmark index for HDFC Mid Cap?", "hdfc_mid_cap_fund", "benchmark"),
        ]
        for query, expected_scheme_id, expected_topic in topic_tests:
            res = self.retriever.retrieve(query)
            self.assertIsNotNone(res.target_scheme)
            self.assertEqual(res.target_scheme.scheme_id, expected_scheme_id)
            self.assertTrue(len(res.chunks) > 0)
            top_chunk = res.chunks[0]
            self.assertEqual(
                top_chunk.topic,
                expected_topic,
                f"Expected topic '{expected_topic}' for query '{query}', got '{top_chunk.topic}'",
            )
            self.assertGreater(res.confidence_score, 0.50)

    def test_scheme_routing_filters_chunks(self) -> None:
        """Verify that when a scheme is detected, all returned chunks belong to that scheme."""
        res = self.retriever.retrieve("What is the exit load for HDFC Flexi Cap Fund?")
        self.assertEqual(res.target_scheme.scheme_id, "hdfc_flexi_cap_fund")
        for chunk in res.chunks:
            self.assertEqual(chunk.scheme_id, "hdfc_flexi_cap_fund")
            self.assertEqual(
                chunk.source_url,
                "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
            )


if __name__ == "__main__":
    unittest.main()
