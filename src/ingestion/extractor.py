"""Extractor module for Phase 2.2: Parses scheme attributes and creates structured chunks."""

import json
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    ALLOWED_URLS,
    PROCESSED_CHUNKS_DIR,
    RAW_HTML_DIR,
    is_allowed_url,
)
from src.ingestion.registry import CorpusRegistry, SchemeRecord, load_corpus_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SchemeChunk:
    """Structured, metadata-enriched chunk bound strictly to a canonical Groww URL."""
    chunk_id: str
    scheme_id: str
    scheme_name: str
    category: str
    topic: str
    source_url: str
    last_updated: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        """Enforces field validity and URL whitelist invariant."""
        if not self.chunk_id:
            raise ValueError("Chunk must have a valid chunk_id.")
        if not self.content or len(self.content.strip()) < 10:
            raise ValueError(f"Chunk {self.chunk_id} has insufficient content.")
        if not is_allowed_url(self.source_url):
            raise ValueError(
                f"Security violation: Chunk {self.chunk_id} URL '{self.source_url}' "
                "is not in the allowed whitelist!"
            )


class SchemeExtractor:
    """Parses raw HTML and JSON hydration payloads into clean, thematic scheme facts."""

    def __init__(
        self,
        registry: Optional[CorpusRegistry] = None,
        raw_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.registry = registry or load_corpus_registry()
        self.raw_dir = raw_dir or RAW_HTML_DIR
        self.output_dir = output_dir or PROCESSED_CHUNKS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_mf_data_from_html(self, html: str) -> Dict[str, Any]:
        """Extracts mfServerSideData dictionary from HTML __NEXT_DATA__ block."""
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not match:
            raise ValueError("Failed to locate __NEXT_DATA__ payload in HTML snapshot.")
        payload = json.loads(match.group(1))
        page_props = payload.get("props", {}).get("pageProps", {})
        mf_data = page_props.get("mfServerSideData")
        if not mf_data:
            raise ValueError("Missing mfServerSideData in pageProps.")
        return mf_data

    def extract_riskometer_from_html(self, html: str, default: str = "Very High") -> str:
        """Extracts official riskometer classification from metadata or DOM."""
        match = re.search(r'Risk is ([a-zA-Z\s]{3,20})', html, re.I)
        if match:
            return match.group(1).strip()
        match_rated = re.search(r'rated ([a-zA-Z\s]{3,20}) risk', html, re.I)
        if match_rated:
            return match_rated.group(1).strip()
        return default

    def build_chunks_for_scheme(
        self, scheme: SchemeRecord, html_content: str
    ) -> List[SchemeChunk]:
        """Builds cohesive, thematic chunks for a given scheme."""
        mf_data = self.extract_mf_data_from_html(html_content)
        risk_rating = self.extract_riskometer_from_html(html_content, default="Very High")

        scheme_id = scheme.scheme_id
        scheme_name = scheme.scheme_name
        category = scheme.category
        source_url = scheme.source_url
        last_updated = mf_data.get("nav_date") or scheme.last_verified_date or "16-Sep-2026"

        chunks: List[SchemeChunk] = []

        # 1. Expense Ratio (TER)
        expense_ratio = mf_data.get("expense_ratio")
        er_content = (
            f"{scheme_name} Expense Ratio: The Total Expense Ratio (TER) for this direct growth plan is "
            f"{expense_ratio}% (inclusive of GST). As a Direct Plan, it has a lower expense ratio "
            f"compared to regular plans because no distributor commissions are paid."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_expense_ratio_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="expense_ratio",
            source_url=source_url,
            last_updated=last_updated,
            content=er_content,
        ))

        # 2. Exit Load
        raw_exit_load = (mf_data.get("exit_load") or "").strip()
        stamp_duty = (mf_data.get("stamp_duty") or "0.005%").strip()
        if not raw_exit_load or raw_exit_load.lower() == "nil":
            exit_load_desc = "Nil. There is no exit load charged on redemption of units."
        else:
            exit_load_desc = raw_exit_load
        
        el_content = (
            f"{scheme_name} Exit Load: {exit_load_desc} "
            f"Additionally, a mandatory stamp duty of {stamp_duty} applies on purchase of mutual fund units."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_exit_load_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="exit_load",
            source_url=source_url,
            last_updated=last_updated,
            content=el_content,
        ))

        # 3. Minimum Investment & SIP Amount
        min_sip = mf_data.get("min_sip_investment", 100)
        min_inv = mf_data.get("min_investment_amount", 100)
        mini_add = mf_data.get("mini_additional_investment", 100)
        inv_content = (
            f"{scheme_name} Minimum Investment & SIP Amount: The minimum SIP investment amount is ₹{min_sip}. "
            f"The minimum lump-sum investment amount is ₹{min_inv}, and the minimum additional investment is ₹{mini_add}."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_min_investment_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="min_investment",
            source_url=source_url,
            last_updated=last_updated,
            content=inv_content,
        ))

        # 4. Lock-in Period
        lock_in = mf_data.get("lock_in") or {}
        lock_years = lock_in.get("years")
        if lock_years and lock_years > 0:
            lock_content = (
                f"{scheme_name} Lock-in Period: This scheme has a statutory lock-in period of {lock_years} years "
                f"under Section 80C of the Income Tax Act. Investments cannot be redeemed, switched out, or withdrawn "
                f"before the completion of {lock_years} years from the date of unit allotment."
            )
        else:
            lock_content = (
                f"{scheme_name} Lock-in Period: Nil. This is an open-ended mutual fund scheme with no mandatory "
                f"lock-in period, meaning investors can redeem their units at any time subject to applicable exit load."
            )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_lock_in_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="lock_in_period",
            source_url=source_url,
            last_updated=last_updated,
            content=lock_content,
        ))

        # 5. Riskometer Classification
        risk_content = (
            f"{scheme_name} Riskometer Classification: The scheme's risk level is classified as '{risk_rating}' risk. "
            f"Investors should understand that their principal investment will be at very high risk in this equity scheme."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_riskometer_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="riskometer",
            source_url=source_url,
            last_updated=last_updated,
            content=risk_content,
        ))

        # 6. Benchmark Index
        benchmark = mf_data.get("benchmark_name") or mf_data.get("benchmark") or "NIFTY 500 Total Return Index"
        bm_content = (
            f"{scheme_name} Benchmark Index: The scheme is benchmarked against the {benchmark}. "
            f"The fund manager's portfolio composition and performance are measured against this index."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_benchmark_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="benchmark",
            source_url=source_url,
            last_updated=last_updated,
            content=bm_content,
        ))

        # 7. Fund Management
        manager_details = mf_data.get("fund_manager_details", [])
        if manager_details:
            managers_list = [m.get("person_name") for m in manager_details if m.get("person_name")]
            managers_str = ", ".join(managers_list)
            # Add qualification details for primary manager
            primary = manager_details[0]
            bio = primary.get("education") or primary.get("experience") or ""
            mgr_content = (
                f"{scheme_name} Fund Managers: The fund is managed by {managers_str}. "
                f"{primary.get('person_name', 'The manager')} ({bio.strip()}) manages the portfolio."
            )
        else:
            mgr_name = mf_data.get("fund_manager", "Experienced Fund Managers")
            mgr_content = f"{scheme_name} Fund Managers: The scheme portfolio is managed by {mgr_name}."
        
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_fund_managers_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="fund_managers",
            source_url=source_url,
            last_updated=last_updated,
            content=mgr_content,
        ))

        # 8. Fund Overview, AUM & NAV
        aum = mf_data.get("aum")
        nav = mf_data.get("nav")
        nav_date = mf_data.get("nav_date", last_updated)
        sub_cat = mf_data.get("sub_category") or category
        fund_house = mf_data.get("fund_house", "HDFC Mutual Fund")
        overview_content = (
            f"{scheme_name} Scheme Overview: This is a direct growth plan in the {sub_cat} equity category "
            f"offered by {fund_house}. The fund size (AUM) is approximately ₹{aum:,.2f} Cr, and the Net Asset "
            f"Value (NAV) is ₹{nav} as of {nav_date}."
        )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_overview_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="scheme_overview",
            source_url=source_url,
            last_updated=last_updated,
            content=overview_content,
        ))

        # 9. Taxation
        if "elss" in category.lower() or "tax" in scheme_name.lower():
            tax_content = (
                f"{scheme_name} Taxation & Section 80C: Investments up to ₹1.5 lakh per financial year "
                f"are eligible for tax deduction under Section 80C of the Income Tax Act. Long-term capital "
                f"gains exceeding ₹1.25 lakh in a financial year are taxed at 12.5% without indexation."
            )
        else:
            tax_content = (
                f"{scheme_name} Capital Gains Taxation: As an equity-oriented mutual fund, short-term capital "
                f"gains (units held for 1 year or less) are taxed at 20%. Long-term capital gains (units held for "
                f"more than 1 year) exceeding ₹1.25 lakh per financial year are taxed at 12.5% without indexation."
            )
        chunks.append(SchemeChunk(
            chunk_id=f"{scheme_id}_taxation_01",
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            category=category,
            topic="taxation",
            source_url=source_url,
            last_updated=last_updated,
            content=tax_content,
        ))

        # Enforce invariant on every single chunk
        for chunk in chunks:
            chunk.validate()

        return chunks

    def extract_and_save_all(self) -> Dict[str, List[SchemeChunk]]:
        """Extracts chunks for all 5 schemes from raw HTML and saves to processed_chunks."""
        all_chunks: List[SchemeChunk] = []
        result_by_scheme: Dict[str, List[SchemeChunk]] = {}

        for scheme in self.registry.schemes:
            html_path = self.raw_dir / f"{scheme.scheme_id}.html"
            if not html_path.exists():
                raise FileNotFoundError(
                    f"Raw HTML snapshot missing for scheme {scheme.scheme_id} at {html_path}. "
                    "Run Phase 2.1 scraper first."
                )

            html_content = html_path.read_text(encoding="utf-8")
            scheme_chunks = self.build_chunks_for_scheme(scheme, html_content)

            # Save individual scheme chunks JSON
            scheme_out = self.output_dir / f"{scheme.scheme_id}.json"
            scheme_data = [c.to_dict() for c in scheme_chunks]
            scheme_out.write_text(json.dumps(scheme_data, indent=2), encoding="utf-8")

            result_by_scheme[scheme.scheme_id] = scheme_chunks
            all_chunks.extend(scheme_chunks)
            logger.info("Extracted %d chunks for [%s]", len(scheme_chunks), scheme.scheme_id)

        # Save consolidated catalog
        catalog_path = self.output_dir / "all_chunks.json"
        catalog_data = [c.to_dict() for c in all_chunks]
        catalog_path.write_text(json.dumps(catalog_data, indent=2), encoding="utf-8")
        logger.info(
            "Phase 2.2 Complete: Saved total of %d chunks to %s",
            len(all_chunks),
            catalog_path,
        )

        return result_by_scheme


def run_extractor() -> Dict[str, List[SchemeChunk]]:
    """CLI / programmatic entrypoint for Phase 2.2 chunking."""
    logger.info("Starting Phase 2.2 Structured Chunking & Metadata Enrichment...")
    extractor = SchemeExtractor()
    return extractor.extract_and_save_all()


if __name__ == "__main__":
    run_extractor()
