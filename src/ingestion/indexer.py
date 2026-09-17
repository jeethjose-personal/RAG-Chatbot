"""Indexer module for Phase 3: Embeds and populates the vector store with scheme chunks."""

import json
import logging
import math
import os
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    ALLOWED_URLS,
    CHROMA_DB_DIR,
    PROCESSED_CHUNKS_DIR,
    is_allowed_url,
)
from src.ingestion.extractor import SchemeChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Check if chromadb is available in environment
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


STOP_WORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "will", "with", "tell", "me"
}


class LocalVectorStore:
    """Self-contained, file-backed vector store implementing cosine similarity search.
    
    Acts as a resilient, zero-dependency storage engine stored in data/chroma_db/local_index.json.
    """

    def __init__(self, persist_dir: Path = CHROMA_DB_DIR):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.persist_dir / "local_index.json"
        self.chunks: List[Dict[str, Any]] = []
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.vectors: List[List[float]] = []
        self._load()

    def _tokenize(self, text: str) -> List[str]:
        """Stop-word filtered financial text tokenizer."""
        clean = re.sub(r'[^a-zA-Z0-9.%₹_]', ' ', text.lower())
        tokens = [
            t.strip() for t in clean.split()
            if len(t.strip()) > 1 and t.strip() not in STOP_WORDS
        ]
        return tokens

    def _load(self) -> None:
        if self.index_file.exists():
            try:
                data = json.loads(self.index_file.read_text(encoding="utf-8"))
                self.chunks = data.get("chunks", [])
                self.vocab = data.get("vocab", {})
                self.idf = data.get("idf", {})
                self.vectors = data.get("vectors", [])
            except Exception as e:
                logger.warning("Could not load existing local vector index: %s", e)

    def _compute_vector(self, tokens: List[str]) -> List[float]:
        counts = Counter(tokens)
        vec = [0.0] * len(self.vocab)
        for token, count in counts.items():
            if token in self.vocab:
                idx = self.vocab[token]
                tf = 1.0 + math.log(count)
                idf = self.idf.get(token, 1.0)
                vec[idx] = tf * idf
        # Normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def upsert(self, chunks: List[SchemeChunk]) -> None:
        """Indexes scheme chunks and saves vector index to disk."""
        self.chunks = [c.to_dict() for c in chunks]
        
        # Build vocabulary with boosted topic tokens
        all_tokens_list = []
        for c in chunks:
            tokens = self._tokenize(c.content)
            # Boost topic tokens (e.g. 'riskometer', 'exit', 'load', 'ter')
            topic_tokens = self._tokenize(c.topic.replace("_", " "))
            tokens.extend(topic_tokens * 3)
            all_tokens_list.append(tokens)

        doc_count = len(chunks)
        df_counts: Counter = Counter()

        for tokens in all_tokens_list:
            unique_tokens = set(tokens)
            for t in unique_tokens:
                df_counts[t] += 1

        self.vocab = {word: idx for idx, (word, _) in enumerate(df_counts.most_common())}
        self.idf = {word: math.log((doc_count + 1) / (df + 1)) + 1.0 for word, df in df_counts.items()}
        self.vectors = [self._compute_vector(tokens) for tokens in all_tokens_list]

        # Persist index
        payload = {
            "chunks": self.chunks,
            "vocab": self.vocab,
            "idf": self.idf,
            "vectors": self.vectors,
        }
        self.index_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved local vector index to %s (%d vectors)", self.index_file, len(self.vectors))

    def query(
        self,
        query_text: str,
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Queries the vector index using cosine similarity with optional metadata filtering."""
        tokens = self._tokenize(query_text)
        query_vec = self._compute_vector(tokens)

        results: List[Tuple[Dict[str, Any], float]] = []

        for idx, (chunk, doc_vec) in enumerate(zip(self.chunks, self.vectors)):
            # Apply metadata filter if provided
            if where:
                match = True
                for k, v in where.items():
                    if chunk.get(k) != v:
                        match = False
                        break
                if not match:
                    continue

            # Compute cosine similarity
            sim = sum(q * d for q, d in zip(query_vec, doc_vec))
            results.append((chunk, float(sim)))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:n_results]


class SchemeIndexer:
    """Populates vector database with scheme chunks, supporting ChromaDB and Local fallback."""

    def __init__(self, persist_dir: Path = CHROMA_DB_DIR):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.has_chromadb = HAS_CHROMADB
        self.local_store = LocalVectorStore(self.persist_dir)
        self.chroma_client = None
        self.collection = None

        if self.has_chromadb:
            try:
                self.chroma_client = chromadb.PersistentClient(path=str(self.persist_dir))
                self.collection = self.chroma_client.get_or_create_collection(
                    name="mutual_fund_schemes",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("Initialized ChromaDB PersistentClient at %s", self.persist_dir)
            except Exception as e:
                logger.warning("Failed to initialize ChromaDB (%s), using local vector store.", e)
                self.has_chromadb = False

    def index_chunks(self, chunks: List[SchemeChunk]) -> None:
        """Indexes chunks into the vector store after verifying whitelist invariants."""
        # 1. Enforce strict whitelist invariant
        for chunk in chunks:
            chunk.validate()
            if not is_allowed_url(chunk.source_url):
                raise ValueError(
                    f"Security violation: Chunk {chunk.chunk_id} with URL '{chunk.source_url}' "
                    "violates whitelist!"
                )

        # 2. Always index to local store for guaranteed zero-dependency offline availability
        self.local_store.upsert(chunks)

        # 3. If ChromaDB is active, index to ChromaDB collection as well
        if self.has_chromadb and self.collection:
            ids = [c.chunk_id for c in chunks]
            documents = [c.content for c in chunks]
            metadatas = [
                {
                    "scheme_id": c.scheme_id,
                    "scheme_name": c.scheme_name,
                    "category": c.category,
                    "topic": c.topic,
                    "source_url": c.source_url,
                    "last_updated": c.last_updated,
                }
                for c in chunks
            ]
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            logger.info("ChromaDB index populated with %d chunks.", len(chunks))

    def index_all_from_processed(self, catalog_path: Optional[Path] = None) -> int:
        """Loads all processed chunks and indexes them into the vector store."""
        target_path = catalog_path or (PROCESSED_CHUNKS_DIR / "all_chunks.json")
        if not target_path.exists():
            raise FileNotFoundError(
                f"Processed chunks catalog not found at {target_path}. Run Phase 2.2 first."
            )

        data = json.loads(target_path.read_text(encoding="utf-8"))
        chunks = [
            SchemeChunk(
                chunk_id=item["chunk_id"],
                scheme_id=item["scheme_id"],
                scheme_name=item["scheme_name"],
                category=item["category"],
                topic=item["topic"],
                source_url=item["source_url"],
                last_updated=item["last_updated"],
                content=item["content"],
            )
            for item in data
        ]
        self.index_chunks(chunks)
        return len(chunks)


def run_indexer() -> int:
    """CLI / programmatic entrypoint for Phase 3 indexing."""
    logger.info("Starting Phase 3 Vector DB Indexer...")
    indexer = SchemeIndexer()
    count = indexer.index_all_from_processed()
    logger.info("Phase 3 Indexing Complete: %d chunks successfully indexed.", count)
    return count


if __name__ == "__main__":
    run_indexer()
