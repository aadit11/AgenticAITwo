"""Chunk corpus/ and write the persistent Chroma collection named corpus.

Re-running replaces the collection. Chunk ids are deterministic, so the same
passage keeps the same id instead of being appended again.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from chromadb import PersistentClient
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CORPUS = ROOT / "corpus"
COLLECTION_NAME = "corpus"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_BATCH = 128
UPSERT_BATCH = 200

DOC_PREFIXES = ("library/", "tutorial/", "reference/", "howto/", "faq/", "whatsnew/", "glossary.txt")
SKIP_NAMES = {"index.txt", "genindex.txt", "search.txt", "py-modindex.txt", "contents.txt"}

UNDERLINE = re.compile(r"^([=#*\-^~])\1{3,}\s*$")
ROLE = re.compile(r":(?:pep|ref|mod|func|class|meth|attr|exc|data|const|envvar|term|doc|file|abbr|rfc|issue|gh):`([^`<]+)(?:\s*<[^`]+>)?`")
DIRECTIVE = re.compile(r"^\s*\.\.\s+")

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (cleaned or "section")[:48]


def clean_text(text: str) -> str:
    text = ROLE.sub(lambda match: match.group(1).strip(), text)
    text = text.replace("\\", "")
    lines = []
    for line in text.splitlines():
        if DIRECTIVE.match(line) or UNDERLINE.match(line) or re.match(r"^\s*:[A-Za-z0-9_-]+:", line):
            continue
        lines.append(line.rstrip())
    compact = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return compact.strip()


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return the document title and (section name, body) pairs."""
    lines = text.splitlines()
    title = ""
    sections: list[tuple[str, list[str]]] = []
    current_name = "Introduction"
    buffer: list[str] = []

    def flush() -> None:
        body = clean_text("\n".join(buffer))
        if body:
            sections.append((current_name, body))

    index = 0
    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        previous = lines[index - 1] if index > 0 else ""
        if line.strip() and UNDERLINE.match(next_line) and not UNDERLINE.match(line):
            flush()
            buffer = []
            heading = line.strip()
            if not title:
                title = heading
            current_name = heading
            index += 2
            continue
        if UNDERLINE.match(line) and previous.strip() and UNDERLINE.match(previous):
            index += 1
            continue
        buffer.append(line)
        index += 1
    flush()
    if not title:
        title = sections[0][0] if sections else "Untitled"
    return title, [(name, body) for name, body in sections]


def iter_documents() -> list[dict]:
    documents: list[dict] = []
    docs_root = next(CORPUS.glob("python-docs/python-*-docs-text"), None)
    if docs_root is None:
        raise FileNotFoundError("Python docs text archive was not extracted. Run ingest/download_corpus.py.")
    for path in sorted(docs_root.rglob("*.txt")):
        relative = path.relative_to(docs_root).as_posix()
        if path.name in SKIP_NAMES or not relative.startswith(DOC_PREFIXES):
            continue
        title, sections = split_sections(path.read_text(encoding="utf-8", errors="replace"))
        doc_id = relative[: -len(".txt")]
        source_url = f"https://docs.python.org/3/{doc_id}.html"
        documents.append(
            {
                "doc_id": doc_id,
                "title": title,
                "source_url": source_url,
                "kind": "python-docs",
                "sections": sections,
            }
        )

    pep_files = sorted((CORPUS / "peps-src").glob("peps-main/peps/pep-*.rst"))
    if not pep_files:
        raise FileNotFoundError("PEP sources were not extracted. Run ingest/download_corpus.py.")
    for path in pep_files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        title, sections = split_sections(raw)
        header_title = re.search(r"^Title:\s*(.+)$", raw, re.MULTILINE)
        if header_title:
            title = header_title.group(1).strip()
        number = path.stem.split("-", 1)[1]
        doc_id = f"pep-{number}"
        documents.append(
            {
                "doc_id": doc_id,
                "title": title or f"PEP {int(number)}",
                "source_url": f"https://peps.python.org/{doc_id}/",
                "kind": "pep",
                "sections": sections,
            }
        )
    return documents


def build_chunks(documents: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    seen: set[str] = set()
    for document in documents:
        for section_index, (section, body) in enumerate(document["sections"]):
            pieces = SPLITTER.split_text(body)
            kept = [piece.strip() for piece in pieces if len(piece.strip()) >= 120]
            if not kept and body.strip():
                kept = [body.strip()[:CHUNK_SIZE]]
            if document["kind"] == "pep":
                number = document["doc_id"].split("-", 1)[1].lstrip("0") or "0"
                label = f"PEP {number}: {document['title']}. Section: {section}."
            else:
                label = f"Python documentation: {document['title']}. Section: {section}."
            section_slug = slug(section)
            for piece_index, piece in enumerate(kept):
                piece = f"{label}\n{piece}"
                chunk_id = f"{document['doc_id']}/{section_index:02d}-{section_slug}/{piece_index}"
                if chunk_id in seen:
                    chunk_id = f"{chunk_id}-{piece_index}"
                seen.add(chunk_id)
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": piece,
                        "metadata": {
                            "chunk_id": chunk_id,
                            "doc_id": document["doc_id"],
                            "title": document["title"][:300],
                            "section": section[:300],
                            "source_url": document["source_url"],
                            "kind": document["kind"],
                        },
                    }
                )
    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    model = os.environ["OPENAI_EMBEDDING_MODEL"]
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        for attempt in range(5):
            try:
                response = client.embeddings.create(model=model, input=batch)
                break
            except Exception as exc:
                if attempt == 4:
                    raise
                wait = 2 ** attempt
                print(f"embedding batch {start} failed ({exc}); retrying in {wait}s")
                time.sleep(wait)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)
        print(f"embedded {min(start + EMBED_BATCH, len(texts))}/{len(texts)}", flush=True)
    return vectors


def write_collection(chunks: list[dict], vectors: list[list[float]]) -> int:
    persist_dir = Path(os.environ.get("CHROMA_PERSIST_DIR", "./chroma_index"))
    if not persist_dir.is_absolute():
        persist_dir = ROOT / persist_dir
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = PersistentClient(path=str(persist_dir))
    existing = {collection.name for collection in client.list_collections()}
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    for start in range(0, len(chunks), UPSERT_BATCH):
        batch = chunks[start : start + UPSERT_BATCH]
        collection.upsert(
            ids=[item["id"] for item in batch],
            documents=[item["text"] for item in batch],
            metadatas=[item["metadata"] for item in batch],
            embeddings=vectors[start : start + len(batch)],
        )
    return collection.count()


def smoke(client: OpenAI) -> None:
    persist_dir = Path(os.environ.get("CHROMA_PERSIST_DIR", "./chroma_index"))
    if not persist_dir.is_absolute():
        persist_dir = ROOT / persist_dir
    collection = PersistentClient(path=str(persist_dir)).get_collection(COLLECTION_NAME)
    model = os.environ["OPENAI_EMBEDDING_MODEL"]
    questions = [
        (
            "definition",
            "According to the Python style guide, imports should usually be on separate lines.",
        ),
        ("two-chunks", "How do absolute imports and relative imports work in the Python import system?"),
        ("miss", "Who won the 2026 FIFA World Cup final?"),
    ]
    report = []
    for name, question in questions:
        vector = client.embeddings.create(model=model, input=question).data[0].embedding
        found = collection.query(query_embeddings=[vector], n_results=5, include=["documents", "metadatas", "distances"])
        hits = []
        for distance, metadata, document in zip(found["distances"][0], found["metadatas"][0], found["documents"][0]):
            hits.append(
                {
                    "distance": round(float(distance), 4),
                    "chunk_id": metadata["chunk_id"],
                    "doc_id": metadata["doc_id"],
                    "section": metadata["section"],
                    "source_url": metadata["source_url"],
                    "excerpt": document[:180].replace("\n", " "),
                }
            )
        report.append({"name": name, "question": question, "hits": hits})

    definition_distance = report[0]["hits"][0]["distance"]
    definition_ok = report[0]["hits"][0]["chunk_id"].startswith("pep-0008/09-imports/")
    two_ids = {hit["chunk_id"] for hit in report[1]["hits"]}
    import_hits = [hit for hit in report[1]["hits"] if "import" in hit["excerpt"].lower() or "import" in hit["section"].lower() or "import" in hit["doc_id"]]
    two_ok = len(two_ids) >= 2 and len(import_hits) >= 2
    miss_distance = report[2]["hits"][0]["distance"]
    miss_ok = miss_distance > definition_distance and all("world cup" not in hit["excerpt"].lower() for hit in report[2]["hits"])
    print(json.dumps({"definition_ok": definition_ok, "two_chunks_ok": two_ok, "miss_ok": miss_ok, "queries": report}, indent=2))
    if not (definition_ok and two_ok and miss_ok):
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Query the existing index and skip embedding.")
    parser.add_argument("--dry-run", action="store_true", help="Chunk only. Do not call the embedding API.")
    args = parser.parse_args()
    if args.dry_run:
        documents = iter_documents()
        chunks = build_chunks(documents)
        sample = next(chunk for chunk in chunks if chunk["metadata"]["doc_id"] == "pep-0008" and "import" in chunk["metadata"]["section"].lower())
        print(f"documents={len(documents)} chunks={len(chunks)}")
        print(json.dumps({"chunk_id": sample["id"], "title": sample["metadata"]["title"], "section": sample["metadata"]["section"], "source_url": sample["metadata"]["source_url"], "excerpt": sample["text"][:240]}, indent=2))
        return
    client = OpenAI()
    if args.smoke:
        smoke(client)
        return
    documents = iter_documents()
    chunks = build_chunks(documents)
    kinds: dict[str, int] = {}
    for document in documents:
        kinds[document["kind"]] = kinds.get(document["kind"], 0) + 1
    print(f"documents={len(documents)} by_kind={kinds} chunks={len(chunks)}")
    if len(chunks) < 1000:
        raise SystemExit(f"expected thousands of chunks, got {len(chunks)}")
    vectors = embed_texts(client, [chunk["text"] for chunk in chunks])
    count = write_collection(chunks, vectors)
    print(f"collection count={count}")
    smoke(client)


if __name__ == "__main__":
    main()
