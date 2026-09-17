"""Configuration, project paths, and strict whitelist constants for Mutual Fund FAQ Assistant."""

import os
from pathlib import Path
from typing import Final, FrozenSet, Set

# Base directory paths
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
SRC_DIR: Final[Path] = BASE_DIR / "src"
TESTS_DIR: Final[Path] = BASE_DIR / "tests"

# Subdirectories for data pipeline
REGISTRY_FILE: Final[Path] = DATA_DIR / "corpus_registry.json"
RAW_HTML_DIR: Final[Path] = DATA_DIR / "raw_html"
PROCESSED_CHUNKS_DIR: Final[Path] = DATA_DIR / "processed_chunks"
CHROMA_DB_DIR: Final[Path] = DATA_DIR / "chroma_db"

# Ensure runtime directories exist
RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# Strict Whitelist of 5 Groww URLs (Corpus Boundary)
ALLOWED_URLS: Final[FrozenSet[str]] = frozenset({
    "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth",
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
})

# AMC Specification
TARGET_AMC: Final[str] = "HDFC Mutual Fund"
EXPECTED_SCHEME_COUNT: Final[int] = 5

# Generation & Attribution Constraints
MAX_RESPONSE_SENTENCES: Final[int] = 3
EXACT_CITATION_COUNT: Final[int] = 1
MANDATORY_FOOTER_PREFIX: Final[str] = "Last updated from sources:"
MANDATORY_DISCLAIMER: Final[str] = "Facts-only. No investment advice."

# Try loading .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# LLM Configuration
LLM_PROVIDER: Final[str] = os.getenv("LLM_PROVIDER", "gemini").lower()
LLM_MODEL_NAME: Final[str] = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash")
LLM_TEMPERATURE: Final[float] = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Provider API Keys
OPENAI_API_KEY: Final[str] = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY: Final[str] = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: Final[str] = os.getenv("GROQ_API_KEY", "")


def is_allowed_url(url: str) -> bool:
    """Verifies whether a given URL strictly belongs to the 5 whitelisted Groww URLs.
    
    Trailing whitespace is stripped. Trailing slashes are rejected or must match exactly.
    """
    if not isinstance(url, str):
        return False
    clean_url = url.strip()
    return clean_url in ALLOWED_URLS

