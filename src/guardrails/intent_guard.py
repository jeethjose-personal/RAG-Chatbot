"""Intent guard and refusal routing for Phase 4."""

import re
from enum import Enum
from typing import Optional, Tuple


class QueryIntent(Enum):
    FACTUAL = "factual"
    ADVISORY = "advisory"
    COMPARISON = "comparison"
    PERFORMANCE_SPECULATION = "performance_speculation"
    OUT_OF_SCOPE_SCHEME = "out_of_scope_scheme"
    PROMPT_INJECTION = "prompt_injection"
    IRRELEVANT = "irrelevant"


class IntentGuard:
    """Classifies user queries and routes non-factual intents to deterministic, polite refusals."""

    # 1. Advisory & Recommendation keywords
    ADVISORY_PATTERNS = [
        re.compile(r'(?i)\bshould\s+i\s+(?:invest|buy|put\s+money|start|choose)\b'),
        re.compile(r'(?i)\b(?:recommend|suggest|advise|advice)\b'),
        re.compile(r'(?i)\bis\s+.*?\b(?:good|safe|worth|profitable|better|ideal)\b'),
        re.compile(r'(?i)\b(?:good|best)\s+for\s+.*?\b(?:wealth|investment|growth|retirement|investing)\b'),
        re.compile(r'(?i)\bworth\s+(?:investing|buying)\b'),
        re.compile(r'(?i)\bwhere\s+should\s+i\s+invest\b'),
        re.compile(r'(?i)\bhow\s+should\s+i\s+allocate\b'),
        re.compile(r'(?i)\b(?:my\s+age\s+is|i\s+am\s+\d+\s+years\s+old)\b'),
        re.compile(r'(?i)\b(?:portfolio\s+(?:review|suggestion|recommendation))\b'),
    ]

    # 2. Scheme Comparison keywords
    COMPARISON_PATTERNS = [
        re.compile(r'(?i)\bwhich\s+(?:(?:fund|one|scheme)\s+)?is\s+(?:better|best|superior|higher|safer|preferred)\b'),
        re.compile(r'(?i)\bcompare\b'),
        re.compile(r'(?i)\b(?:vs|versus)\b'),
        re.compile(r'(?i)\brank\s+(?:these|the)\s+funds\b'),
        re.compile(r'(?i)\bwhich\s+(?:(?:fund|scheme|one)\s+)?(?:gives|has|delivers|provides)\s+(?:better|higher|more|best)\s+returns?\b'),
        re.compile(r'(?i)\b(?:better|best)\s+between\b'),
        re.compile(r'(?i)\b(?:is\s+.*\s+better\s+than)\b'),
    ]

    # 3. Future Return Speculation
    SPECULATION_PATTERNS = [
        re.compile(r'(?i)\bwill\s+.*\s+(?:give|earn|reach|grow|deliver|make)\s+.*(?:\d+\s*%|returns?)\b'),
        re.compile(r'(?i)\bpredict\b'),
        re.compile(r'(?i)\bhow\s+much\s+(?:profit|money|return)\b'),
        re.compile(r'(?i)\bexpected\s+(?:future\s+)?returns?\s+next\s+year\b'),
    ]

    # 4. Out-of-Scope Schemes (Non-HDFC schemes or non-whitelisted funds)
    NON_WHITELISTED_SCHEMES = [
        re.compile(r'(?i)\b(?:sbi|icici|nippon|axis|mirae|parag\s+parikh|kotak|tata|uti|dsp|quant|motilal)\b'),
        re.compile(r'(?i)\b(?:gold|crypto|bitcoin|real\s+estate|fd|fixed\s+deposit)\b'),
    ]

    # 5. Prompt Injection / Jailbreak keywords
    INJECTION_PATTERNS = [
        re.compile(r'(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b'),
        re.compile(r'(?i)\b(?:system\s+prompt|jailbreak|developer\s+mode|dan\s+mode)\b'),
        re.compile(r'(?i)\bpretend\s+(?:to\s+be|you\s+are)\b'),
        re.compile(r'(?i)\bdisregard\s+rules\b'),
    ]

    # Standard Compliant Refusals (strictly zero external URLs)
    ADVISORY_REFUSAL = (
        "I provide factual scheme information only and cannot offer investment advice, "
        "recommendations, or financial planning opinions. Please consult a SEBI-registered "
        "investment advisor for personalized guidance."
    )

    COMPARISON_REFUSAL = (
        "I cannot compare funds or recommend one scheme over another. "
        "Please review each scheme's factual parameters individually on Groww."
    )

    SPECULATION_REFUSAL = (
        "Mutual fund investments are subject to market risks, and future returns cannot be predicted "
        "or guaranteed. I can only provide historical and factual data from the official scheme documentation."
    )

    OUT_OF_SCOPE_REFUSAL = (
        "This assistant is strictly configured for 5 select HDFC mutual fund schemes on Groww: "
        "HDFC Mid-Cap Opportunities, HDFC Flexi Cap, HDFC Focused 30, HDFC ELSS Tax Saver, and HDFC Top 100."
    )

    INJECTION_REFUSAL = (
        "I operate strictly under compliance guardrails as a facts-only mutual fund FAQ assistant "
        "and cannot alter these operating constraints."
    )

    GENERAL_IRRELEVANT_REFUSAL = (
        "I can only answer objective, factual questions regarding the 5 supported HDFC mutual fund "
        "schemes on Groww."
    )

    def classify_intent(self, query: str) -> Tuple[QueryIntent, Optional[str]]:
        """Classifies query intent and returns refusal text if non-factual."""
        if not query or not isinstance(query, str) or not query.strip():
            return QueryIntent.IRRELEVANT, "Please enter a valid mutual fund question."

        q = query.strip()

        # 1. Check for prompt injection
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(q):
                return QueryIntent.PROMPT_INJECTION, self.INJECTION_REFUSAL

        # 2. Check for comparison / ranking (evaluated before advisory to catch 'which is better')
        for pattern in self.COMPARISON_PATTERNS:
            if pattern.search(q):
                return QueryIntent.COMPARISON, self.COMPARISON_REFUSAL

        # 3. Check for investment advice / recommendation
        for pattern in self.ADVISORY_PATTERNS:
            if pattern.search(q):
                return QueryIntent.ADVISORY, self.ADVISORY_REFUSAL

        # 4. Check for speculative future return queries
        for pattern in self.SPECULATION_PATTERNS:
            if pattern.search(q):
                return QueryIntent.PERFORMANCE_SPECULATION, self.SPECULATION_REFUSAL

        # 5. Check for non-whitelisted AMCs / schemes
        for pattern in self.NON_WHITELISTED_SCHEMES:
            if pattern.search(q):
                return QueryIntent.OUT_OF_SCOPE_SCHEME, self.OUT_OF_SCOPE_REFUSAL

        # If it asks general non-financial questions (e.g. weather, capital of France)
        if re.search(r'(?i)\b(?:capital\s+of|weather\s+in|who\s+won|president\s+of|joke|poem|song)\b', q):
            return QueryIntent.IRRELEVANT, self.GENERAL_IRRELEVANT_REFUSAL

        return QueryIntent.FACTUAL, None

    def classify_and_handle(self, query: str) -> Optional[str]:
        """Convenience method: returns refusal string if non-factual, else None."""
        intent, refusal = self.classify_intent(query)
        if intent != QueryIntent.FACTUAL:
            return refusal
        return None
