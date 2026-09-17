"""Unit tests for Phase 2.2: Scheme Fact Extraction & Structured Chunking."""

import json
import unittest
from pathlib import Path

from src.config import ALLOWED_URLS, EXPECTED_SCHEME_COUNT, PROCESSED_CHUNKS_DIR
from src.ingestion.extractor import SchemeExtractor
from src.ingestion.registry import load_corpus_registry


class TestPhase2Extractor(unittest.TestCase):
    """Tests the structured chunks extracted in Phase 2.2."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_corpus_registry()
        cls.extractor = SchemeExtractor(registry=cls.registry)
        cls.results = cls.extractor.extract_and_save_all()
        cls.catalog_file = PROCESSED_CHUNKS_DIR / "all_chunks.json"
        with open(cls.catalog_file, "r", encoding="utf-8") as f:
            cls.all_chunks = json.load(f)

    def test_all_scheme_json_files_exist(self) -> None:
        """Verify that an individual JSON chunk file exists for each of the 5 schemes."""
        for scheme in self.registry.schemes:
            expected_file = PROCESSED_CHUNKS_DIR / f"{scheme.scheme_id}.json"
            self.assertTrue(expected_file.exists(), f"Missing chunk file: {expected_file}")

    def test_total_chunk_count_and_diversity(self) -> None:
        """Verify total chunks and that each scheme has exactly 9 thematic chunks."""
        self.assertEqual(len(self.all_chunks), EXPECTED_SCHEME_COUNT * 9)
        expected_topics = {
            "expense_ratio",
            "exit_load",
            "min_investment",
            "lock_in_period",
            "riskometer",
            "benchmark",
            "fund_managers",
            "scheme_overview",
            "taxation",
        }
        for scheme in self.registry.schemes:
            scheme_chunks = [c for c in self.all_chunks if c["scheme_id"] == scheme.scheme_id]
            self.assertEqual(len(scheme_chunks), 9)
            topics = {c["topic"] for c in scheme_chunks}
            self.assertEqual(topics, expected_topics)

    def test_every_chunk_strictly_cites_whitelisted_url(self) -> None:
        """Verify the crucial invariant: 100% of chunks cite an allowed Groww URL verbatim."""
        for chunk in self.all_chunks:
            source_url = chunk["source_url"]
            self.assertIn(
                source_url,
                ALLOWED_URLS,
                f"Chunk {chunk['chunk_id']} has unapproved source URL: {source_url}",
            )
            # Ensure no tracking params, anchors or external domains
            self.assertTrue(source_url.startswith("https://groww.in/mutual-funds/"))
            self.assertNotIn("?", source_url)
            self.assertNotIn("#", source_url)

    def test_ground_truth_extracted_facts(self) -> None:
        """Verify factual correctness of key extracted chunks against verified source data."""
        # 1. ELSS Lock-in
        elss_lockin = next(
            c for c in self.all_chunks
            if c["scheme_id"] == "hdfc_elss_tax_saver_fund" and c["topic"] == "lock_in_period"
        )
        self.assertIn("3 years", elss_lockin["content"])
        self.assertIn("Section 80C", elss_lockin["content"])

        # 2. ELSS Exit Load (Nil)
        elss_exit = next(
            c for c in self.all_chunks
            if c["scheme_id"] == "hdfc_elss_tax_saver_fund" and c["topic"] == "exit_load"
        )
        self.assertIn("Nil", elss_exit["content"])

        # 3. Mid Cap Exit Load (1% within 1 year)
        mid_exit = next(
            c for c in self.all_chunks
            if c["scheme_id"] == "hdfc_mid_cap_fund" and c["topic"] == "exit_load"
        )
        self.assertIn("1%", mid_exit["content"])
        self.assertIn("1 year", mid_exit["content"])

        # 4. Large Cap Benchmark
        large_bm = next(
            c for c in self.all_chunks
            if c["scheme_id"] == "hdfc_large_cap_fund" and c["topic"] == "benchmark"
        )
        self.assertIn("NIFTY 100 Total Return Index", large_bm["content"])

        # 5. Focused 30 Expense Ratio
        focused_er = next(
            c for c in self.all_chunks
            if c["scheme_id"] == "hdfc_focused_fund" and c["topic"] == "expense_ratio"
        )
        self.assertIn("0.82%", focused_er["content"])

    def test_no_empty_fields_in_any_chunk(self) -> None:
        """Ensure no chunk contains empty or null strings for required fields."""
        required_fields = [
            "chunk_id",
            "scheme_id",
            "scheme_name",
            "category",
            "topic",
            "source_url",
            "last_updated",
            "content",
        ]
        for chunk in self.all_chunks:
            for field in required_fields:
                val = chunk.get(field)
                self.assertIsNotNone(val, f"Chunk {chunk.get('chunk_id')} has None for field {field}")
                self.assertTrue(bool(str(val).strip()), f"Chunk {chunk.get('chunk_id')} has empty field {field}")


if __name__ == "__main__":
    unittest.main()
