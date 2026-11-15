"""Ingestion pipeline – load, chunk, embed, upsert."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path when running as a module or script
_this_dir = Path(__file__).resolve().parent
_backend_dir = _this_dir.parent.parent
_root_dir = _backend_dir.parent
for d in (str(_backend_dir), str(_root_dir)):
    if d not in sys.path:
        sys.path.insert(0, d)

from app.db import get_pool, init_db
from app.ingest.loaders import load_products, load_markdown, load_policies, load_faqs
from app.ingest.chunker import chunk_product, chunk_policy, chunk_faqs
from app.retrieval.embed import embed_texts

logger = logging.getLogger(__name__)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_data_dir(data_dir: str | Path = "data") -> Path:
    """Resolve data directory path across different execution contexts."""
    path = Path(data_dir)
    if path.is_dir() and any(path.iterdir()):
        return path

    # Check root repository data folder
    root_data = _root_dir / "data"
    if root_data.is_dir() and any(root_data.iterdir()):
        return root_data

    # Check backend/../data
    alt_data = _backend_dir.parent / "data"
    if alt_data.is_dir() and any(alt_data.iterdir()):
        return alt_data

    return path


async def run_ingestion(data_dir: str = "data") -> dict[str, int]:
    """Full ingestion pipeline. Returns stats dict with documents and chunks counts."""
    # Ensure database tables and extensions are created first
    await init_db()

    data_path = _resolve_data_dir(data_dir)
    all_chunks: list[dict[str, Any]] = []
    doc_records: list[dict[str, Any]] = []

    logger.info("Starting ingestion from: %s", data_path)

    # ── Load & chunk products ───────────────────────────────────────────
    products_path = data_path / "products.json"
    if products_path.exists():
        products = load_products(products_path)
        content_for_hash = json.dumps(products, sort_keys=True)
        doc_records.append({
            "name": "products.json",
            "doc_type": "product",
            "content_hash": _hash(content_for_hash),
        })
        for p in products:
            chunk = chunk_product(p)
            chunk["doc_name"] = "products.json"
            all_chunks.append(chunk)
    else:
        logger.warning("products.json not found at %s", products_path)

    # ── Load & chunk policies ───────────────────────────────────────────
    policies_dir = data_path / "policies"
    if policies_dir.exists():
        policies = load_policies(policies_dir)
        for pol in policies:
            doc_name = pol["filename"]
            doc_records.append({
                "name": doc_name,
                "doc_type": "policy",
                "content_hash": _hash(pol["content"]),
            })
            chunks = chunk_policy(pol["content"], pol["title"])
            for c in chunks:
                c["doc_name"] = doc_name
                all_chunks.append(c)
    else:
        logger.warning("Policies directory not found at %s", policies_dir)

    # ── Load & chunk FAQs ───────────────────────────────────────────────
    faqs_path = data_path / "faqs.md"
    if faqs_path.exists():
        faqs_content = load_markdown(faqs_path)
        doc_records.append({
            "name": "faqs.md",
            "doc_type": "faq",
            "content_hash": _hash(faqs_content),
        })
        qa_pairs = load_faqs(faqs_path)
        faq_chunks = chunk_faqs(qa_pairs)
        for c in faq_chunks:
            c["doc_name"] = "faqs.md"
            all_chunks.append(c)
    else:
        logger.warning("faqs.md not found at %s", faqs_path)

    if not all_chunks:
        logger.warning("No chunks generated – nothing to ingest")
        return {"documents": 0, "chunks": 0}

    # ── Embed all chunks ────────────────────────────────────────────────
    logger.info("Embedding %d chunks…", len(all_chunks))
    texts = [c["content"] for c in all_chunks]
    embeddings = embed_texts(texts, batch_size=32)

    # ── Upsert to database ──────────────────────────────────────────────
    pool = await get_pool()

    doc_id_map: dict[str, int] = {}
    docs_inserted = 0
    chunks_inserted = 0

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Upsert documents
            for doc in doc_records:
                existing = await conn.fetchrow(
                    "SELECT id, content_hash FROM documents WHERE name = $1",
                    doc["name"],
                )
                if existing and existing["content_hash"] == doc["content_hash"]:
                    doc_id_map[doc["name"]] = existing["id"]
                    logger.info("Document '%s' unchanged, skipping", doc["name"])
                    continue

                if existing:
                    # Update hash, delete old chunks (cascade will handle)
                    await conn.execute(
                        "UPDATE documents SET content_hash = $1, updated_at = now() WHERE id = $2",
                        doc["content_hash"],
                        existing["id"],
                    )
                    await conn.execute(
                        "DELETE FROM chunks WHERE document_id = $1",
                        existing["id"],
                    )
                    doc_id_map[doc["name"]] = existing["id"]
                else:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO documents (name, doc_type, content_hash)
                        VALUES ($1, $2, $3)
                        RETURNING id
                        """,
                        doc["name"],
                        doc["doc_type"],
                        doc["content_hash"],
                    )
                    doc_id_map[doc["name"]] = row["id"]
                    docs_inserted += 1

            # Insert chunks
            for chunk, emb in zip(all_chunks, embeddings):
                doc_name = chunk["doc_name"]
                doc_id = doc_id_map.get(doc_name)
                if doc_id is None:
                    continue

                content_hash = _hash(chunk["content"])

                # Check for existing chunk with same hash under same document
                exists = await conn.fetchval(
                    "SELECT 1 FROM chunks WHERE document_id = $1 AND content_hash = $2",
                    doc_id,
                    content_hash,
                )
                if exists:
                    continue

                embedding_str = "[" + ",".join(str(v) for v in emb) + "]"

                await conn.execute(
                    """
                    INSERT INTO chunks (document_id, content, section, metadata, doc_type, content_hash, embedding)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::vector)
                    """,
                    doc_id,
                    chunk["content"],
                    chunk.get("section"),
                    json.dumps(chunk.get("metadata", {})),
                    chunk["doc_type"],
                    content_hash,
                    embedding_str,
                )
                chunks_inserted += 1

    logger.info(
        "Ingestion complete: %d documents, %d chunks inserted",
        docs_inserted,
        chunks_inserted,
    )
    return {"documents": docs_inserted, "chunks": chunks_inserted}


if __name__ == "__main__":
    from app.db import close_pool

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

    async def _main():
        data_arg = sys.argv[1] if len(sys.argv) > 1 else "data"
        stats = await run_ingestion(data_arg)
        print(f"✓ Ingestion complete: {stats['documents']} docs, {stats['chunks']} chunks")
        await close_pool()

    asyncio.run(_main())
