"""Generator module for Phase 5: Constrained LLM response synthesizer and validator."""

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from src.config import (
    GEMINI_API_KEY,
    LLM_MODEL_NAME,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    MANDATORY_FOOTER_PREFIX,
    MAX_RESPONSE_SENTENCES,
    OPENAI_API_KEY,
)
from src.rag.retriever import RetrievalResult
from src.rag.validator import ResponseValidator, ValidationReport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class GeneratedAnswer:
    """Final, validated response from the assistant."""
    answer_text: str
    sentence_count: int
    citation_url: str
    footer_text: str
    is_valid: bool
    rejection_reason: Optional[str] = None


class ConstrainedGenerator:
    """Generates strictly grounded, facts-only responses complying with all attribution rules."""

    SYSTEM_PROMPT_TEMPLATE = """You are the Mutual Fund FAQ Assistant for Groww. Your sole function is to provide direct, concise, factual answers strictly based on the provided context extracted from official Groww mutual fund scheme pages.

STRICT CONSTRAINTS:
1. Answer to the point: Answer ONLY the specific fact or metric requested in 1 to 2 concise sentences. Do NOT include introductory prefixes (e.g., 'Scheme Overview:'), generic fund category descriptions, or unrequested metrics (e.g., do not include NAV if only AUM was asked).
2. If factual information is missing: If the fact is not in the context, state: "I do not have this factual information in the official scheme documentation." Do NOT include any citation links when factual information is not available.
3. Investment Advice: STRICTLY FORBIDDEN. Never use words like 'good', 'recommended', 'attractive', 'ideal', or suggest buying/selling.
4. Maximum length: EXACTLY 1 to 2 sentences (maximum 3). No bullet points, no numbered lists.
5. Exactly one citation link when factual information is present: You can review the scheme details directly using the below link: [Official Scheme Page on Groww]({canonical_url})
6. Footer: On a new line at the very end, append:
   Last updated from sources: {source_date}
"""

    def __init__(self, validator: Optional[ResponseValidator] = None):
        self.validator = validator or ResponseValidator()
        self.provider = LLM_PROVIDER
        self.model_name = LLM_MODEL_NAME
        self.temperature = LLM_TEMPERATURE

    def _call_gemini_api(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Calls Google Gemini API using urllib if key is present."""
        api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={api_key}"
        )
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 300,
            },
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
        except Exception as e:
            logger.warning("Gemini API call failed (%s). Falling back to deterministic synthesizer.", e)
            return None
        return None

    def _call_openai_api(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Calls OpenAI API using urllib if key is present."""
        api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            return None

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": self.model_name if "gpt" in self.model_name else "gpt-4o-mini",
            "temperature": self.temperature,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning("OpenAI API call failed (%s). Falling back to deterministic synthesizer.", e)
            return None
        return None

    def _extract_target_metric(self, query: str, raw_content: str, scheme_name: str) -> str:
        """Extracts the exact requested factual metric without unnecessary preamble or other metrics."""
        import re
        # Strip scheme and topic header prefixes
        cleaned = re.sub(r'^[^:]+:\s*', '', raw_content).strip()
        sentences = self.validator.split_sentences(cleaned)
        query_lower = query.lower()

        # 1. Targeted extraction for AUM / Fund Size
        if any(k in query_lower for k in ("aum", "fund size", "asset size", "corpus")):
            for s in sentences:
                if any(k in s.lower() for k in ("fund size", "aum")):
                    # Isolate AUM clause from comma-joined NAV clause
                    parts = re.split(r',\s+and\s+', s)
                    for p in parts:
                        if any(k in p.lower() for k in ("fund size", "aum")):
                            core = re.sub(r'^[Tt]he fund size \(AUM\) is\s*', '', p).strip()
                            return f"The fund size (AUM) of {scheme_name} is {core}."

        # 2. Targeted extraction for NAV
        if any(k in query_lower for k in ("nav", "net asset value")):
            for s in sentences:
                if any(k in s.lower() for k in ("net asset value", "nav")):
                    parts = re.split(r',\s+and\s+', s)
                    for p in parts:
                        if "nav" in p.lower() or "net asset value" in p.lower():
                            core = re.sub(r'^[Tt]he [Nn]et [Aa]sset [Vv]alue \(NAV\) is\s*', '', p).strip()
                            return f"The Net Asset Value (NAV) of {scheme_name} is {core}."

        # 3. Default to the primary topical sentence with clean phrasing
        if sentences:
            primary = sentences[0].strip()
            # Remove any secondary commentary starting with 'Additionally'
            primary = re.split(r'\s+Additionally\b', primary, flags=re.I)[0].strip()
            
            # Contextual phrasing helpers for mutual fund parameters
            if primary.lower().startswith("exit load"):
                return f"The exit load for {scheme_name} is " + re.sub(r'^[Ee]xit load (?:of )?', '', primary).rstrip(".") + "."
            if "total expense ratio" in primary.lower():
                return f"The Total Expense Ratio (TER) for {scheme_name} is " + re.sub(r'^[Tt]he [Tt]otal [Ee]xpense [Rr]atio \(TER\) for this direct growth plan is\s*', '', primary).rstrip(".") + "."
            if "statutory lock-in" in primary.lower():
                return f"{scheme_name} has a statutory lock-in period of 3 years under Section 80C."
            if primary.lower().startswith("nil"):
                return f"{scheme_name} has no mandatory lock-in period (Nil) as it is an open-ended fund."
            if "risk level" in primary.lower():
                return f"The risk level of {scheme_name} is " + re.sub(r'^[Tt]he scheme\'s risk level is\s*', '', primary).rstrip(".") + "."
            if "fund is managed by" in primary.lower():
                return f"{scheme_name} is managed by " + re.sub(r'^[Tt]he fund is managed by\s*', '', primary).rstrip(".") + "."

            if scheme_name.lower() not in primary.lower():
                return f"For {scheme_name}, {primary[0].lower() + primary[1:]}."
            return primary if primary.endswith(".") else f"{primary}."

        return cleaned

    def _deterministic_synthesis(
        self,
        query: str,
        context: RetrievalResult,
        source_date: str,
    ) -> str:
        """High-precision, concise deterministic synthesizer directly answering to the point."""
        top_chunk = context.chunks[0]
        scheme_name = top_chunk.scheme_name
        base_fact = self._extract_target_metric(query, top_chunk.content, scheme_name)
        if base_fact and not base_fact.endswith("."):
            base_fact += "."

        citation_link = f"[Official Scheme Page on Groww]({context.canonical_citation_url})"
        answer = f"{base_fact} You can review the scheme details directly using the below link: {citation_link}."
        footer = f"\n\n{MANDATORY_FOOTER_PREFIX} {source_date}"
        return f"{answer}{footer}"

    def _is_query_grounded_in_chunks(self, query: str, chunks: list) -> bool:
        """Verifies if the query's requested metric or subject is actually present in retrieved chunks."""
        if not chunks:
            return False

        q_lower = query.lower()

        # Unsupported metrics that don't exist in the 5 Groww pages
        unsupported = (
            "turnover", "sharpe", "alpha", "beta", "dividend", "yield",
            "volatility", "standard deviation", "pe ratio", "pb ratio", "credit quality"
        )
        if any(m in q_lower for m in unsupported):
            return False

        topic_kw = {
            "aum": ("aum", "fund size", "asset size", "corpus"),
            "nav": ("nav", "net asset value"),
            "expense_ratio": ("expense ratio", "ter", "expense"),
            "exit_load": ("exit load", "redeem", "redemption", "stamp duty"),
            "lock_in": ("lock-in", "lock in", "lockin"),
            "riskometer": ("riskometer", "risk level", "risk rating", "how risky"),
            "benchmark": ("benchmark", "index"),
            "fund_managers": ("fund manager", "fund managers", "manager", "managed by", "who manages"),
            "taxation": ("tax", "taxation", "capital gains", "stcg", "ltcg"),
            "min_investment": ("minimum investment", "sip", "lump sum", "lumpsum"),
        }

        for topic, kws in topic_kw.items():
            if any(k in q_lower for k in kws):
                for c in chunks:
                    if getattr(c, "topic", "") == topic or any(k in getattr(c, "content", "").lower() for k in kws):
                        return True
                return False

        return True

    def generate(self, query: str, context: RetrievalResult) -> GeneratedAnswer:
        """Synthesizes constrained answer, applying deterministic post-generation validation."""
        canonical_url = context.canonical_citation_url
        source_date = (
            context.chunks[0].last_updated
            if context.chunks
            else "16-Sep-2026"
        )

        # 1. Handle ungrounded / missing information (do NOT provide CTA Link)
        if not context.is_grounded or not context.chunks or not self._is_query_grounded_in_chunks(query, context.chunks):
            raw_text = (
                f"I do not have this factual information in the official scheme documentation."
                f"\n\n{MANDATORY_FOOTER_PREFIX} {source_date}"
            )
            report = self.validator.validate(raw_text)
            return GeneratedAnswer(
                answer_text=raw_text,
                sentence_count=report.sentence_count,
                citation_url="",
                footer_text=f"{MANDATORY_FOOTER_PREFIX} {source_date}",
                is_valid=report.is_valid,
                rejection_reason=report.rejection_reason,
            )

        # 2. Build Context String for LLM
        context_str = "\n\n".join([f"- {c.content}" for c in context.chunks])
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            canonical_url=canonical_url,
            source_date=source_date,
        )
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}\nAnswer:"

        raw_response: Optional[str] = None

        # 3. Attempt LLM API call based on configured provider
        if self.provider == "gemini":
            raw_response = self._call_gemini_api(user_prompt, system_prompt)
        elif self.provider == "openai":
            raw_response = self._call_openai_api(user_prompt, system_prompt)

        # 4. Fallback to deterministic synthesis if API was unavailable or not configured
        if not raw_response:
            raw_response = self._deterministic_synthesis(query, context, source_date)

        # 5. Programmatic Validation & Auto-Repair
        report = self.validator.validate(raw_response)
        if not report.is_valid:
            logger.info("Draft response failed validation (%s). Applying auto-repair.", report.rejection_reason)
            raw_response = self.validator.repair_or_format(
                raw_body=raw_response,
                canonical_url=canonical_url,
                source_date=source_date,
            )
            report = self.validator.validate(raw_response)

        return GeneratedAnswer(
            answer_text=raw_response,
            sentence_count=report.sentence_count,
            citation_url=canonical_url,
            footer_text=f"{MANDATORY_FOOTER_PREFIX} {source_date}",
            is_valid=report.is_valid,
            rejection_reason=report.rejection_reason,
        )
