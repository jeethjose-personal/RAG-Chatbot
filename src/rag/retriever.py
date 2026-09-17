"""Retriever module for Phase 3.2: Metadata-aware semantic search over the 5 schemes."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import ALLOWED_URLS, CHROMA_DB_DIR, is_allowed_url
from src.ingestion.extractor import SchemeChunk
from src.ingestion.indexer import SchemeIndexer
from src.ingestion.registry import CorpusRegistry, SchemeRecord, load_corpus_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Encapsulates context chunks, confidence score, and the single canonical citation URL."""
    chunks: List[SchemeChunk]
    canonical_citation_url: str
    confidence_score: float
    target_scheme: Optional[SchemeRecord] = None
    is_grounded: bool = True

    def validate(self) -> None:
        """Enforces that the canonical citation URL is strictly in ALLOWED_URLS."""
        if not is_allowed_url(self.canonical_citation_url):
            raise ValueError(
                f"Attribution violation: Citation URL '{self.canonical_citation_url}' "
                "is not in the allowed whitelist!"
            )


class SchemeRetriever:
    """Retrieves top-k context chunks and binds the single canonical citation URL."""

    def __init__(
        self,
        indexer: Optional[SchemeIndexer] = None,
        registry: Optional[CorpusRegistry] = None,
        similarity_threshold: float = 0.15,
    ):
        self.indexer = indexer or SchemeIndexer()
        self.registry = registry or load_corpus_registry()
        self.similarity_threshold = similarity_threshold

    def retrieve(self, query: str, top_k: int = 3) -> RetrievalResult:
        """Executes metadata-routed semantic search over the 5 scheme documents."""
        # 1. Scheme Routing via Alias Resolver
        target_scheme = self.registry.resolve_scheme_from_text(query)
        where_filter: Optional[Dict[str, Any]] = None

        if target_scheme:
            logger.info("Routed query to scheme: [%s]", target_scheme.scheme_id)
            where_filter = {"scheme_id": target_scheme.scheme_id}

        chunks: List[SchemeChunk] = []
        canonical_url: str = ""
        top_score: float = 0.0

        # 2. Try ChromaDB Native Retrieval First
        if self.indexer.has_chromadb and self.indexer.collection:
            try:
                chroma_res = self.indexer.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter,
                )
                if (
                    chroma_res
                    and chroma_res.get("ids")
                    and chroma_res["ids"][0]
                ):
                    for cid, doc, meta, dist in zip(
                        chroma_res["ids"][0],
                        chroma_res["documents"][0],
                        chroma_res["metadatas"][0],
                        chroma_res["distances"][0],
                    ):
                        chunks.append(SchemeChunk(
                            chunk_id=cid,
                            scheme_id=meta["scheme_id"],
                            scheme_name=meta["scheme_name"],
                            category=meta["category"],
                            topic=meta["topic"],
                            source_url=meta["source_url"],
                            last_updated=meta["last_updated"],
                            content=doc,
                        ))
                    canonical_url = chunks[0].source_url
                    top_score = max(0.0, 1.0 - float(chroma_res["distances"][0][0]))
            except Exception as e:
                logger.warning("ChromaDB query encountered error (%s), using local vector store.", e)
                chunks = []

        # 3. Fallback to Local Vector Store if ChromaDB didn't return chunks
        if not chunks:
            raw_results = self.indexer.local_store.query(
                query_text=query,
                n_results=top_k,
                where=where_filter,
            )
            if raw_results:
                for chunk_dict, score in raw_results:
                    chunks.append(SchemeChunk(
                        chunk_id=chunk_dict["chunk_id"],
                        scheme_id=chunk_dict["scheme_id"],
                        scheme_name=chunk_dict["scheme_name"],
                        category=chunk_dict["category"],
                        topic=chunk_dict["topic"],
                        source_url=chunk_dict["source_url"],
                        last_updated=chunk_dict["last_updated"],
                        content=chunk_dict["content"],
                    ))
                canonical_url = chunks[0].source_url
                top_score = raw_results[0][1]

        # 4. Handle completely empty retrieval
        if not chunks:
            fallback_url = (
                target_scheme.source_url
                if target_scheme
                else self.registry.schemes[0].source_url
            )
            return RetrievalResult(
                chunks=[],
                canonical_citation_url=fallback_url,
                confidence_score=0.0,
                target_scheme=target_scheme,
                is_grounded=False,
            )

        is_grounded = top_score >= self.similarity_threshold

        result = RetrievalResult(
            chunks=chunks,
            canonical_citation_url=canonical_url,
            confidence_score=top_score,
            target_scheme=target_scheme,
            is_grounded=is_grounded,
        )
        result.validate()
        return result

