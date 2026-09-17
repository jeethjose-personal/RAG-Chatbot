"""Unit tests for Phase 6: Web UI server, endpoints, and pipeline integration."""

import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from src.app import AssistantRequestHandler, MutualFundRAGApp
from src.config import ALLOWED_URLS


class TestPhase6PipelineService(unittest.TestCase):
    """Tests the MutualFundRAGApp service logic."""

    @classmethod
    def setUpClass(cls):
        cls.app = MutualFundRAGApp()

    def test_get_supported_funds(self):
        """Verify that exactly the 5 whitelisted schemes are returned."""
        funds_data = self.app.get_supported_funds()
        funds = funds_data.get("funds", [])
        self.assertEqual(len(funds), 5)
        for f in funds:
            self.assertIn("scheme_id", f)
            self.assertIn("scheme_name", f)
            self.assertIn("category", f)
            self.assertIn("url", f)
            self.assertIn(f["url"], ALLOWED_URLS)

    def test_process_factual_query(self):
        """Verify factual query processing returns valid compliant card."""
        res = self.app.process_query("What is the AUM of HDFC Mid Cap Fund Direct Growth?")
        self.assertTrue(res["is_valid"])
        self.assertLessEqual(res["sentence_count"], 3)
        self.assertIn("108,324.55", res["answer_text"])
        self.assertIn(res["citation_url"], ALLOWED_URLS)
        self.assertIn("Last updated from sources:", res["footer_text"])

    def test_process_pii_query(self):
        """Verify query containing PII is intercepted and sanitized."""
        res = self.app.process_query("My PAN is ABCDE1234F, what is the exit load for HDFC Flexi Cap?")
        self.assertTrue(res["is_valid"])
        self.assertIn("do not share personal", res["answer_text"].lower())
        self.assertIn("PII Blocked", res.get("rejection_reason", ""))

    def test_process_advisory_refusal(self):
        """Verify advisory inquiry receives strict polite refusal."""
        res = self.app.process_query("Should I invest in HDFC Focused 30 Fund?")
        self.assertTrue(res["is_valid"])
        self.assertIn("cannot offer investment advice", res["answer_text"].lower())
        self.assertIn("Intent Guard Refusal", res.get("rejection_reason", ""))
        self.assertEqual(res.get("citation_url"), "")

    def test_process_ungrounded_query_has_no_cta(self):
        """Verify ungrounded query returns no CTA link when info is unavailable."""
        res = self.app.process_query("What was the portfolio turnover ratio in 1990?")
        self.assertTrue(res["is_valid"])
        self.assertIn("I do not have this factual information", res["answer_text"])
        self.assertEqual(res.get("citation_url"), "")


class TestPhase6HTTPServer(unittest.TestCase):
    """Tests the HTTP server endpoints over local socket."""

    @classmethod
    def setUpClass(cls):
        cls.port = 8599
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), AssistantRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_get_index_html(self):
        """Verify GET / returns 200 OK and HTML document."""
        url = f"http://127.0.0.1:{self.port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Groww Mutual Fund FAQ Assistant", content)
            self.assertIn('id="sidebar"', content)
            self.assertIn('id="quick-prompts-container"', content)

    def test_get_funds_api(self):
        """Verify GET /api/funds returns JSON with 5 schemes."""
        url = f"http://127.0.0.1:{self.port}/api/funds"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("funds", data)
            self.assertEqual(len(data["funds"]), 5)

    def test_post_query_api(self):
        """Verify POST /api/query returns JSON response."""
        url = f"http://127.0.0.1:{self.port}/api/query"
        payload = json.dumps({"query": "What is the lock-in period for HDFC ELSS?"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("is_valid"))
            self.assertIn("3 years", data.get("answer_text", ""))
            self.assertIn(data.get("citation_url"), ALLOWED_URLS)


if __name__ == "__main__":
    unittest.main()
