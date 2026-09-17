"""Output validator for Phase 5: Enforces sentence count <= 3, 1 whitelisted URL, and footer."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.config import (
    ALLOWED_URLS,
    EXACT_CITATION_COUNT,
    MANDATORY_FOOTER_PREFIX,
    MAX_RESPONSE_SENTENCES,
    is_allowed_url,
)

# Common abbreviations that should NOT trigger a sentence split
ABBREVIATIONS = (
    r'\b(?:Rs|Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e|p\.a|approx|vol|no)\.'
)


@dataclass
class ValidationReport:
    """Validation audit for a generated assistant response."""
    is_valid: bool
    sentence_count: int
    cited_urls: List[str]
    has_footer: bool
    rejection_reason: Optional[str] = None


class ResponseValidator:
    """Validates final generated responses against strict attribution and compliance rules."""

    def split_sentences(self, text: str) -> List[str]:
        """Splits body text into sentences while protecting currency, numbers, and abbreviations."""
        # 1. Strip markdown links and footer before sentence counting
        body_text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\1', text)
        body_text = re.sub(rf'{MANDATORY_FOOTER_PREFIX}.*$', '', body_text, flags=re.MULTILINE)

        # 2. Protect abbreviations and decimals temporarily
        protected = body_text
        protected = re.sub(r'(\d+)\.(\d+)', r'\1<DECIMAL>\2', protected)
        protected = re.sub(ABBREVIATIONS, lambda m: m.group(0).replace('.', '<DOT>'), protected, flags=re.IGNORECASE)

        # 3. Split by sentence terminators (. ! ?)
        raw_sentences = re.split(r'[.!?]+(?:\s+|$)', protected)

        # 4. Restore protected markers
        sentences: List[str] = []
        for s in raw_sentences:
            s_clean = s.replace('<DECIMAL>', '.').replace('<DOT>', '.').strip()
            # Filter out empty or whitespace-only artifacts
            if len(s_clean) > 2:
                sentences.append(s_clean)

        return sentences

    def extract_links(self, text: str) -> List[Tuple[str, str]]:
        """Extracts markdown links from text as (anchor_text, url)."""
        return re.findall(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text)

    def validate(self, response_text: str) -> ValidationReport:
        """Validates output according to Phase 5 constraints."""
        if not response_text or not isinstance(response_text, str) or not response_text.strip():
            return ValidationReport(
                is_valid=False,
                sentence_count=0,
                cited_urls=[],
                has_footer=False,
                rejection_reason="Empty response text.",
            )

        text = response_text.strip()

        # 1. Verify Mandatory Footer Presence
        has_footer = MANDATORY_FOOTER_PREFIX in text
        if not has_footer:
            return ValidationReport(
                is_valid=False,
                sentence_count=0,
                cited_urls=[],
                has_footer=False,
                rejection_reason=f"Missing mandatory footer prefix '{MANDATORY_FOOTER_PREFIX}'",
            )

        # 2. Verify Citation Count
        links = self.extract_links(text)
        cited_urls = [url for _, url in links]

        is_missing_info = "I do not have this factual information" in text

        if is_missing_info:
            # When factual information is not available, do not provide the CTA link (0 citations allowed)
            if len(links) > 0:
                return ValidationReport(
                    is_valid=False,
                    sentence_count=0,
                    cited_urls=cited_urls,
                    has_footer=has_footer,
                    rejection_reason="Ungrounded response must not contain citation links.",
                )
        else:
            if len(links) != EXACT_CITATION_COUNT:
                return ValidationReport(
                    is_valid=False,
                    sentence_count=0,
                    cited_urls=cited_urls,
                    has_footer=has_footer,
                    rejection_reason=(
                        f"Expected exactly {EXACT_CITATION_COUNT} citation link, found {len(links)}."
                    ),
                )

            # 3. Whitelist Invariant Check
            cited_url = cited_urls[0]
            if not is_allowed_url(cited_url):
                return ValidationReport(
                    is_valid=False,
                    sentence_count=0,
                    cited_urls=cited_urls,
                    has_footer=has_footer,
                    rejection_reason=(
                        f"Cited URL '{cited_url}' violates whitelist! Must be in ALLOWED_URLS."
                    ),
                )

        # 4. Sentence Count Invariant Check (1 to 3 sentences)
        sentences = self.split_sentences(text)
        sentence_count = len(sentences)

        if sentence_count < 1 or sentence_count > MAX_RESPONSE_SENTENCES:
            return ValidationReport(
                is_valid=False,
                sentence_count=sentence_count,
                cited_urls=cited_urls,
                has_footer=has_footer,
                rejection_reason=(
                    f"Sentence count {sentence_count} exceeds maximum of {MAX_RESPONSE_SENTENCES} sentences."
                ),
            )

        return ValidationReport(
            is_valid=True,
            sentence_count=sentence_count,
            cited_urls=cited_urls,
            has_footer=has_footer,
            rejection_reason=None,
        )

    def repair_or_format(
        self,
        raw_body: str,
        canonical_url: str,
        source_date: str = "16-Sep-2026",
    ) -> str:
        """Deterministically formats and repairs a response to guarantee 100% compliance."""
        # 1. Clean and clamp base content to at most 2 sentences
        sentences = self.split_sentences(raw_body)
        clamped_sentences = sentences[:2]
        body = ". ".join(clamped_sentences).strip()
        if body and not body.endswith("."):
            body += "."

        # 2. Append exactly one canonical citation link sentence (making total <= 3)
        citation_link = f"[Official Scheme Factsheet on Groww]({canonical_url})"
        if body:
            formatted_body = f"{body} You can review the scheme details directly using the below link: {citation_link}."
        else:
            formatted_body = f"You can review the scheme details directly using the below link: {citation_link}."

        # 3. Append mandatory footer
        footer = f"\n\n{MANDATORY_FOOTER_PREFIX} {source_date}"
        return f"{formatted_body}{footer}"
