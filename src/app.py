"""Phase 6 Web Application: Interactive Compliant UI for Groww Mutual Fund FAQ Assistant.

Serves the front-end single page app and connects directly to the end-to-end RAG pipeline
(PIIFilter -> IntentGuard -> SchemeRetriever -> ConstrainedGenerator -> ResponseValidator).
"""

import argparse
import json
import logging
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ALLOWED_URLS, MANDATORY_FOOTER_PREFIX
from src.guardrails.intent_guard import IntentGuard, QueryIntent
from src.guardrails.pii_filter import PIIFilter
from src.ingestion.registry import load_corpus_registry
from src.rag.generator import ConstrainedGenerator
from src.rag.retriever import SchemeRetriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
DEFAULT_FALLBACK_URL = "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"


class MutualFundRAGApp:
    """Singleton service encapsulating all pipeline stages."""

    def __init__(self):
        logger.info("Initializing Mutual Fund RAG Pipeline components...")
        self.registry = load_corpus_registry()
        self.pii_filter = PIIFilter()
        self.intent_guard = IntentGuard()
        self.retriever = SchemeRetriever(registry=self.registry)
        self.generator = ConstrainedGenerator()
        logger.info("Mutual Fund RAG Pipeline ready.")

    def get_supported_funds(self) -> Dict[str, Any]:
        """Returns the 5 supported schemes from the corpus registry."""
        funds = []
        for scheme in self.registry.schemes:
            funds.append({
                "scheme_id": scheme.scheme_id,
                "scheme_name": scheme.scheme_name,
                "category": scheme.category,
                "url": scheme.source_url,
            })
        return {"funds": funds}

    def process_query(self, query: str) -> Dict[str, Any]:
        """Executes the complete 5-stage RAG compliance pipeline."""
        clean_query = (query or "").strip()
        if not clean_query:
            return {
                "answer_text": "Please ask a factual question regarding one of the 5 supported HDFC mutual funds.",
                "sentence_count": 1,
                "citation_url": "",
                "footer_text": f"{MANDATORY_FOOTER_PREFIX} 16-Sep-2026",
                "is_valid": True,
            }

        # 1. PII Guard
        pii_res = self.pii_filter.inspect(clean_query)
        if not pii_res.is_clean:
            return {
                "answer_text": pii_res.redaction_message,
                "sentence_count": 2,
                "citation_url": "",
                "footer_text": f"{MANDATORY_FOOTER_PREFIX} 16-Sep-2026",
                "is_valid": True,
                "rejection_reason": f"PII Blocked: {pii_res.detected_type}",
            }

        # 2. Intent Guard
        intent, refusal = self.intent_guard.classify_intent(clean_query)
        if intent != QueryIntent.FACTUAL and refusal:
            return {
                "answer_text": refusal,
                "sentence_count": 2,
                "citation_url": "",
                "footer_text": f"{MANDATORY_FOOTER_PREFIX} 16-Sep-2026",
                "is_valid": True,
                "rejection_reason": f"Intent Guard Refusal: {intent.value}",
            }

        # 3. Dense Retrieval & Canonical Citation Binding
        context = self.retriever.retrieve(clean_query)

        # 4. Constrained Generation & Output Validation
        generated = self.generator.generate(clean_query, context)

        return {
            "answer_text": generated.answer_text,
            "sentence_count": generated.sentence_count,
            "citation_url": generated.citation_url,
            "footer_text": generated.footer_text,
            "is_valid": generated.is_valid,
            "rejection_reason": generated.rejection_reason,
        }


# Global app pipeline instance
_app_instance: MutualFundRAGApp = None


def get_app_instance() -> MutualFundRAGApp:
    global _app_instance
    if _app_instance is None:
        _app_instance = MutualFundRAGApp()
    return _app_instance


class AssistantRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving frontend assets and JSON API routes."""

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(HTTPStatus.NO_CONTENT)

    def do_GET(self):
        """Route static assets and GET API endpoints."""
        path = self.path.split("?")[0]

        if path == "/api/funds":
            app = get_app_instance()
            data = app.get_supported_funds()
            self._set_headers(HTTPStatus.OK, "application/json")
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        # Static file mapping
        file_map = {
            "/": FRONTEND_DIR / "index.html",
            "/index.html": FRONTEND_DIR / "index.html",
            "/style.css": FRONTEND_DIR / "style.css",
            "/app.js": FRONTEND_DIR / "app.js",
        }

        target_file = file_map.get(path)
        if target_file and target_file.exists():
            content_type = "text/html; charset=utf-8"
            if path.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif path.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"

            self._set_headers(HTTPStatus.OK, content_type)
            with open(target_file, "rb") as f:
                self.wfile.write(f.read())
            return

        self._set_headers(HTTPStatus.NOT_FOUND, "text/plain")
        self.wfile.write(b"404 Not Found")

    def do_POST(self):
        """Handle query submissions and pipeline execution."""
        path = self.path.split("?")[0]

        if path == "/api/query":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(post_data)
                query = payload.get("query", "")
            except Exception:
                query = ""

            app = get_app_instance()
            result = app.process_query(query)

            self._set_headers(HTTPStatus.OK, "application/json")
            self.wfile.write(json.dumps(result).encode("utf-8"))
            return

        self._set_headers(HTTPStatus.NOT_FOUND, "text/plain")
        self.wfile.write(b"404 Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress noisy access logging in standard output."""
        return


# Top-level handler exports for cloud/serverless detectors (e.g. Vercel)
handler = AssistantRequestHandler
app = AssistantRequestHandler
application = AssistantRequestHandler


def run_server(host: str = "0.0.0.0", port: int = 8501) -> None:
    """Starts the HTTP server on specified port."""
    # Eagerly initialize pipeline
    get_app_instance()
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AssistantRequestHandler)
    print(f"\n=======================================================")
    print(f" Groww Mutual Fund FAQ Assistant UI (Phase 6)")
    print(f" Access URL: http://localhost:{port}")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(description="Groww Mutual Fund FAQ Assistant Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8501)), help="Port (default: 8501)")
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
