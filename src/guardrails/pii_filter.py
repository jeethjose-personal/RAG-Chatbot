"""PII filter module for Phase 4: Intercepts PAN, Aadhaar, Phone, and Account numbers."""

import re
from dataclasses import dataclass
from typing import Optional

STANDARD_PII_REDACTION_MESSAGE = (
    "For your security, please do not share personal or financial identifiers like PAN, "
    "Aadhaar, phone numbers, or account details. This assistant provides public scheme facts "
    "only and cannot access personal records or accounts."
)


@dataclass
class PIIFilterResult:
    """Outcome of inspecting user input for PII."""
    is_clean: bool
    detected_type: Optional[str] = None
    redaction_message: Optional[str] = None


class PIIFilter:
    """Detects and blocks personal identifiable information with zero data retention."""

    # 1. PAN Pattern: 5 letters, 4 digits, 1 letter (handling spaces and hyphens)
    PAN_PATTERN = re.compile(r'\b[A-Za-z]{5}\s*[-]?\s*[0-9]{4}\s*[-]?\s*[A-Za-z]\b')

    # Spaced PAN pattern (e.g. A B C D E 1 2 3 4 F)
    SPACED_PAN_PATTERN = re.compile(
        r'\b[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\s+[0-9]\s+[0-9]\s+[0-9]\s+[0-9]\s+[A-Za-z]\b',
        re.IGNORECASE,
    )

    # 2. Aadhaar Pattern: 12-digit number (formatted 4-4-4 or raw 12 digits starting with 2-9)
    AADHAAR_PATTERN = re.compile(r'\b[2-9][0-9]{3}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b')

    # 3. Indian Phone Pattern: 10 digits starting with 6-9, optionally prefixed with +91, 91, or 0
    PHONE_PATTERN = re.compile(r'(?:\+?91[\s-]?)?[0]?[6-9][0-9]{4}[\s-]?[0-9]{5}\b')

    # 4. Folio / Account / Bank details
    FOLIO_PATTERN = re.compile(r'(?i)\b(?:folio|account|acct|acc|bank|a\/c)\s*(?:no|num|number)?\s*(?:is|:|#|-|\s)*([0-9]{6,16}(?:[\/][0-9]{1,4})?)\b')

    def inspect(self, text: str) -> PIIFilterResult:
        """Inspects query for PII and immediately returns a blocking response if found."""
        if not text or not isinstance(text, str):
            return PIIFilterResult(is_clean=True)

        clean_text = text.strip()

        # Check Spaced PAN first
        if self.SPACED_PAN_PATTERN.search(clean_text):
            return PIIFilterResult(
                is_clean=False,
                detected_type="PAN (obfuscated)",
                redaction_message=STANDARD_PII_REDACTION_MESSAGE,
            )

        # Check Standard PAN
        if self.PAN_PATTERN.search(clean_text):
            return PIIFilterResult(
                is_clean=False,
                detected_type="PAN",
                redaction_message=STANDARD_PII_REDACTION_MESSAGE,
            )

        # Check Folio Number
        if self.FOLIO_PATTERN.search(clean_text):
            return PIIFilterResult(
                is_clean=False,
                detected_type="Folio/Account Number",
                redaction_message=STANDARD_PII_REDACTION_MESSAGE,
            )

        # Check Aadhaar Number
        if self.AADHAAR_PATTERN.search(clean_text):
            return PIIFilterResult(
                is_clean=False,
                detected_type="Aadhaar",
                redaction_message=STANDARD_PII_REDACTION_MESSAGE,
            )

        # Check Phone Number
        if self.PHONE_PATTERN.search(clean_text):
            return PIIFilterResult(
                is_clean=False,
                detected_type="Phone Number",
                redaction_message=STANDARD_PII_REDACTION_MESSAGE,
            )

        return PIIFilterResult(is_clean=True)
