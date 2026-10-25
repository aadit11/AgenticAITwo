"""Chroma retrieval over the corpus collection. Research is the only caller."""

from __future__ import annotations

import os
import re
from pathlib import Path

from chromadb import PersistentClient
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
COLLECTION_NAME = "corpus"


def _persist_dir() -> Path:
    configured = Path(os.environ.get("CHROMA_PERSIST_DIR", "./chroma_index"))
    if not configured.is_absolute():
        configured = ROOT / configured
    return configured


def _named_pep_ids(query: str) -> list[str]:
    found = []
    for match in re.finditer(r"\bpep[-\s]?(\d+)\b", query, re.IGNORECASE):
        doc_id = f"pep-{int(match.group(1)):04d}"
        if doc_id not in found:
            found.append(doc_id)
    return found


def _query(embedding: list[float], k: int, where: dict | None = None) -> list[dict]:
    collection = PersistentClient(path=str(_persist_dir())).get_collection(COLLECTION_NAME)
    kwargs = {
        "query_embeddings": [embedding],
        "n_results": k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    found = collection.query(**kwargs)
    if not found["ids"] or not found["ids"][0]:
        return []
    citations = []
    for distance, metadata, document in zip(found["distances"][0], found["metadatas"][0], found["documents"][0]):
        citations.append(
            {
                "chunk_id": metadata["chunk_id"],
                "source": metadata.get("source_url", ""),
                "title": metadata.get("title", ""),
                "section": metadata.get("section", ""),
                "score": round(1 - float(distance), 4),
                "excerpt": (document or "")[:500],
            }
        )
    return citations


def retrieve(query: str, k: int = 5) -> list[dict]:
    """Return the top-k passages with chunk ids and source URLs.

    When the question names a PEP, also search inside that PEP and prefer those passages.
    """
    client = OpenAI(timeout=60)
    embedding = client.embeddings.create(
        model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        input=query,
    ).data[0].embedding
    merged: dict[str, dict] = {}
    for doc_id in _named_pep_ids(query):
        for item in _query(embedding, k, where={"doc_id": doc_id}):
            merged[item["chunk_id"]] = item
    if len(merged) < k:
        for item in _query(embedding, k):
            merged.setdefault(item["chunk_id"], item)
    ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    named = [item for item in ranked if any(item["chunk_id"].startswith(f"{doc_id}/") for doc_id in _named_pep_ids(query))]
    if named:
        rest = [item for item in ranked if item not in named]
        return (named + rest)[:k]
    return ranked[:k]


def corpus_count() -> int:
    try:
        return PersistentClient(path=str(_persist_dir())).get_collection(COLLECTION_NAME).count()
    except Exception:
        return 0
