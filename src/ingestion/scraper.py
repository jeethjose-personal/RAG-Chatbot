"""Scraper module for Phase 2.1: Downloads and caches the 5 Groww scheme HTML pages."""

import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from src.config import (
    ALLOWED_URLS,
    RAW_HTML_DIR,
    is_allowed_url,
)
from src.ingestion.registry import CorpusRegistry, SchemeRecord, load_corpus_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Standard browser User-Agent to avoid Cloudflare bot blocking
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class SchemeScraper:
    """Fetches and stores raw HTML snapshots for the 5 whitelisted Groww scheme pages."""

    def __init__(
        self,
        registry: Optional[CorpusRegistry] = None,
        output_dir: Optional[Path] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.registry = registry or load_corpus_registry()
        self.output_dir = output_dir or RAW_HTML_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent

    def fetch_scheme_html(self, scheme: SchemeRecord) -> str:
        """Fetches raw HTML for a single scheme, enforcing whitelist invariants."""
        if not is_allowed_url(scheme.source_url):
            raise ValueError(
                f"Security violation: Scheme {scheme.scheme_id} URL '{scheme.source_url}' "
                "is not in the allowed whitelist!"
            )

        logger.info("Fetching scheme [%s] from %s", scheme.scheme_id, scheme.source_url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        req = urllib.request.Request(scheme.source_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f"Failed to fetch {scheme.source_url}: HTTP Status {resp.status}"
                    )
                raw_bytes = resp.read()
                html = raw_bytes.decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error fetching {scheme.source_url}: {e}") from e

        # Validate that we got a valid Groww mutual fund page (check for __NEXT_DATA__ or scheme name)
        if "__NEXT_DATA__" not in html and scheme.scheme_name not in html:
            logger.warning(
                "Scheme [%s] HTML did not contain __NEXT_DATA__ payload. Verify content integrity.",
                scheme.scheme_id,
            )

        return html

    def save_snapshot(self, scheme_id: str, html_content: str) -> Path:
        """Saves raw HTML snapshot to local disk."""
        file_path = self.output_dir / f"{scheme_id}.html"
        file_path.write_text(html_content, encoding="utf-8")
        logger.info("Saved snapshot for [%s] to %s (%d bytes)", scheme_id, file_path, len(html_content))
        return file_path

    def fetch_all(self, force_refresh: bool = False) -> Dict[str, Path]:
        """Fetches all 5 scheme pages and caches raw HTML snapshots locally.
        
        Args:
            force_refresh: If True, re-downloads even if cached file exists.
        Returns:
            Dict mapping scheme_id -> Path to local saved HTML snapshot.
        """
        snapshots: Dict[str, Path] = {}

        for scheme in self.registry.schemes:
            snapshot_path = self.output_dir / f"{scheme.scheme_id}.html"

            if snapshot_path.exists() and not force_refresh:
                logger.info("Using existing snapshot for [%s]: %s", scheme.scheme_id, snapshot_path)
                snapshots[scheme.scheme_id] = snapshot_path
                continue

            html = self.fetch_scheme_html(scheme)
            saved_path = self.save_snapshot(scheme.scheme_id, html)
            snapshots[scheme.scheme_id] = saved_path

        return snapshots


def run_scraper() -> Dict[str, Path]:
    """CLI / programmatic entrypoint to execute Phase 2.1 ingestion."""
    logger.info("Starting Phase 2.1 Scheme Scraper...")
    scraper = SchemeScraper()
    results = scraper.fetch_all(force_refresh=True)
    logger.info("Phase 2.1 Complete: Fetched and cached %d snapshots.", len(results))
    return results


if __name__ == "__main__":
    run_scraper()
