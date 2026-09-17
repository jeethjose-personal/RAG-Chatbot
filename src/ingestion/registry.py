"""Corpus registry loader, data models, and whitelist validator for Phase 1."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.config import (
    ALLOWED_URLS,
    EXPECTED_SCHEME_COUNT,
    REGISTRY_FILE,
    TARGET_AMC,
)


@dataclass(frozen=True)
class SchemeRecord:
    """Metadata record for a single mutual fund scheme."""
    scheme_id: str
    scheme_name: str
    display_name: str
    category: str
    source_url: str
    groww_slug: str
    plan_type: str
    option_type: str
    aliases: List[str] = field(default_factory=list)
    status: str = "active"
    last_verified_date: str = ""

    def validate(self) -> None:
        """Enforces field validity and URL whitelist constraint."""
        if not self.scheme_id:
            raise ValueError("Scheme record must have a non-empty scheme_id.")
        if not self.scheme_name:
            raise ValueError(f"Scheme {self.scheme_id} missing scheme_name.")
        if self.source_url not in ALLOWED_URLS:
            raise ValueError(
                f"Scheme {self.scheme_id} URL '{self.source_url}' violates whitelist! "
                f"Must be one of: {sorted(ALLOWED_URLS)}"
            )


@dataclass
class CorpusRegistry:
    """In-memory validated catalog of the 5 allowed schemes."""
    version: str
    amc_name: str
    corpus_description: str
    total_schemes: int
    schemes: List[SchemeRecord]
    _by_id: Dict[str, SchemeRecord] = field(init=False, default_factory=dict)
    _by_url: Dict[str, SchemeRecord] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()
        self._by_id = {s.scheme_id: s for s in self.schemes}
        self._by_url = {s.source_url: s for s in self.schemes}

    def validate(self) -> None:
        """Enforces Phase 1 invariants across the entire registry."""
        if self.amc_name != TARGET_AMC:
            raise ValueError(
                f"Corpus AMC '{self.amc_name}' does not match target AMC '{TARGET_AMC}'."
            )
        if len(self.schemes) != EXPECTED_SCHEME_COUNT:
            raise ValueError(
                f"Registry must contain exactly {EXPECTED_SCHEME_COUNT} schemes, found {len(self.schemes)}."
            )
        
        seen_ids: Set[str] = set()
        seen_urls: Set[str] = set()

        for scheme in self.schemes:
            scheme.validate()
            if scheme.scheme_id in seen_ids:
                raise ValueError(f"Duplicate scheme_id detected: {scheme.scheme_id}")
            seen_ids.add(scheme.scheme_id)

            if scheme.source_url in seen_urls:
                raise ValueError(f"Duplicate source_url detected: {scheme.source_url}")
            seen_urls.add(scheme.source_url)

        # Invariant: Registered URLs must match ALLOWED_URLS exactly
        if seen_urls != set(ALLOWED_URLS):
            missing = set(ALLOWED_URLS) - seen_urls
            unexpected = seen_urls - set(ALLOWED_URLS)
            raise ValueError(
                f"Registry URLs do not match whitelist! Missing: {missing}, Unexpected: {unexpected}"
            )

    def get_by_id(self, scheme_id: str) -> Optional[SchemeRecord]:
        """Lookup scheme by ID."""
        return self._by_id.get(scheme_id)

    def get_by_url(self, url: str) -> Optional[SchemeRecord]:
        """Lookup scheme by canonical URL."""
        return self._by_url.get(url.strip())

    def resolve_scheme_from_text(self, text: str) -> Optional[SchemeRecord]:
        """Resolves scheme from free text query using display name, slug, and aliases, prioritizing longest match."""
        lower_text = text.lower()
        candidates = []
        
        for scheme in self.schemes:
            if scheme.display_name.lower() in lower_text:
                candidates.append((len(scheme.display_name), scheme))
            if scheme.groww_slug.lower() in lower_text:
                candidates.append((len(scheme.groww_slug), scheme))
            for alias in scheme.aliases:
                if alias.lower() in lower_text:
                    candidates.append((len(alias), scheme))
                    
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None

    def get_all_canonical_urls(self) -> List[str]:
        """Returns sorted list of all 5 canonical URLs."""
        return sorted([s.source_url for s in self.schemes])


def load_corpus_registry(registry_path: Optional[Path] = None) -> CorpusRegistry:
    """Loads and validates corpus_registry.json from the given or default path."""
    target_path = registry_path or REGISTRY_FILE
    if not target_path.exists():
        raise FileNotFoundError(f"Corpus registry file not found at {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schemes_data = data.get("schemes", [])
    schemes = [
        SchemeRecord(
            scheme_id=item["scheme_id"],
            scheme_name=item["scheme_name"],
            display_name=item["display_name"],
            category=item["category"],
            source_url=item["source_url"],
            groww_slug=item["groww_slug"],
            plan_type=item["plan_type"],
            option_type=item["option_type"],
            aliases=item.get("aliases", []),
            status=item.get("status", "active"),
            last_verified_date=item.get("last_verified_date", ""),
        )
        for item in schemes_data
    ]

    registry = CorpusRegistry(
        version=data.get("version", "1.0.0"),
        amc_name=data.get("amc_name", ""),
        corpus_description=data.get("corpus_description", ""),
        total_schemes=data.get("total_schemes", len(schemes)),
        schemes=schemes,
    )
    return registry
