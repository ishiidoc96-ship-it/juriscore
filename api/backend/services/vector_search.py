"""
Vector Search Service using zvec + sentence-transformers
Provides hybrid semantic + keyword search over KenyaLaw documents.
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Any

import numpy as np

logger = logging.getLogger("juriscore")

VECTOR_DB_DIR = Path(tempfile.gettempdir()) / "juriscore_vectors"
COLLECTION_NAME = "kenyalaw_docs"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast, good for legal text
EMBEDDING_DIM = 384

# Lazy-loaded globals
_model = None
_collection = None
_initialized = False


def _get_model():
    """Lazy-load the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded")
    return _model


def _get_schema():
    """Create the collection schema."""
    from zvec import CollectionSchema, FieldSchema, VectorSchema, DataType
    from zvec.model.param import FtsIndexParam, InvertIndexParam

    return CollectionSchema(
        name=COLLECTION_NAME,
        fields=[
            FieldSchema("id", DataType.STRING),
            FieldSchema("title", DataType.STRING, index_param=FtsIndexParam(tokenizer_name="standard")),
            FieldSchema("full_text", DataType.STRING, index_param=FtsIndexParam(tokenizer_name="standard")),
            FieldSchema("doc_type", DataType.STRING, index_param=InvertIndexParam()),
            FieldSchema("court", DataType.STRING, index_param=InvertIndexParam()),
            FieldSchema("url", DataType.STRING),
            FieldSchema("year", DataType.INT64, index_param=InvertIndexParam()),
        ],
        vectors=[
            VectorSchema("embedding", data_type=DataType.VECTOR_FP32, dimension=EMBEDDING_DIM),
        ],
    )


def _get_collection():
    """Lazy-load or create the zvec collection."""
    global _collection, _initialized
    if _collection is not None:
        return _collection

    import zvec as _zvec
    from zvec import CollectionOption

    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    db_path = (VECTOR_DB_DIR / "legal_docs").as_posix()

    try:
        _collection = _zvec.open(db_path, CollectionOption())
        logger.info(f"Opened existing zvec collection at {db_path}")
    except Exception:
        schema = _get_schema()
        _collection = _zvec.create_and_open(db_path, schema)
        logger.info(f"Created new zvec collection at {db_path}")

    _initialized = True
    return _collection


def _make_doc(doc: Dict[str, Any], embedding: list) -> "zvec.Doc":
    """Create a zvec Doc from a document dict + embedding."""
    import zvec
    doc_id = doc.get("id", "")
    return zvec.Doc(
        id=doc_id,
        vectors={"embedding": embedding},
        fields={
            "id": doc_id,
            "title": (doc.get("title", "") or "")[:2000],
            "full_text": (doc.get("full_text", "") or doc.get("excerpt", "") or "")[:10000],
            "doc_type": doc.get("doc_type", ""),
            "court": doc.get("court", ""),
            "url": doc.get("url", ""),
            "year": doc.get("year", 0) or 0,
        },
    )


def index_document(doc: Dict[str, Any]) -> bool:
    """Index a single document into zvec."""
    try:
        collection = _get_collection()
        model = _get_model()

        title = doc.get("title", "")
        excerpt = doc.get("excerpt", "")
        embed_input = f"{title}\n{excerpt}" if excerpt else title
        if not embed_input.strip():
            return False

        embedding = model.encode(embed_input, normalize_embeddings=True).tolist()
        collection.insert(_make_doc(doc, embedding))
        return True
    except Exception as e:
        logger.warning(f"Failed to index doc {doc.get('id', '?')}: {e}")
        return False


def index_batch(docs: List[Dict[str, Any]], batch_size: int = 100) -> int:
    """Index a batch of documents. Returns count of successfully indexed."""
    try:
        collection = _get_collection()
        model = _get_model()
    except Exception:
        return 0

    indexed = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        valid_docs = []
        texts = []

        for doc in batch:
            title = doc.get("title", "")
            excerpt = doc.get("excerpt", "")
            embed_input = f"{title}\n{excerpt}" if excerpt else title
            if embed_input.strip():
                valid_docs.append(doc)
                texts.append(embed_input)

        if not texts:
            continue

        try:
            emb_array = model.encode(texts, batch_size=min(batch_size, len(texts)),
                                     normalize_embeddings=True)
            zvec_docs = []
            for doc, emb in zip(valid_docs, emb_array):
                zvec_docs.append(_make_doc(doc, emb.tolist()))

            collection.insert(zvec_docs)
            indexed += len(zvec_docs)
            logger.info(f"Indexed batch {i // batch_size + 1}: {len(zvec_docs)} docs (total: {indexed})")
        except Exception as e:
            logger.warning(f"Batch index failed: {e}")

    return indexed


def vector_search(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """Hybrid search: semantic vector + full-text + metadata filters."""
    try:
        collection = _get_collection()
        model = _get_model()
    except Exception as e:
        logger.warning(f"Vector search unavailable: {e}")
        return []

    try:
        import zvec
        from zvec import Fts

        embedding = model.encode(query, normalize_embeddings=True).tolist()

        # Build filter expression
        filter_parts = []
        if doc_type:
            filter_parts.append(f"doc_type == '{doc_type}'")
        if court:
            filter_parts.append(f"court == '{court.upper()}'")
        if year_from:
            filter_parts.append(f"year >= {year_from}")
        if year_to:
            filter_parts.append(f"year <= {year_to}")

        filter_str = " AND ".join(filter_parts) if filter_parts else None

        # Vector query
        vec_query = zvec.Query(field_name="embedding", vector=embedding)

        # FTS query for keyword matching
        fts_query = zvec.Query(
            field_name="title",
            fts=Fts(match_string=query),
        )

        # Combine: vector search with optional FTS re-ranking
        results = collection.query(
            queries=[vec_query],
            topk=top_k,
            filter=filter_str,
        )

        formatted = []
        for r in results:
            fields = r.fields or {}
            doc = {
                "id": r.id,
                "title": fields.get("title", ""),
                "excerpt": fields.get("full_text", "")[:500],
                "doc_type": fields.get("doc_type", ""),
                "court": fields.get("court", ""),
                "year": fields.get("year", 0),
                "url": fields.get("url", ""),
                "score": r.score or 0.0,
                "source": "vector_search",
            }
            formatted.append(doc)

        return formatted
    except Exception as e:
        logger.warning(f"Vector search error: {e}")
        return []


def fts_search(
    query: str,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """Full-text search using zvec FTS."""
    try:
        collection = _get_collection()
    except Exception as e:
        logger.warning(f"FTS search unavailable: {e}")
        return []

    try:
        import zvec
        from zvec import Fts

        fts_query = zvec.Query(
            field_name="full_text",
            fts=Fts(match_string=query),
        )

        results = collection.query(queries=[fts_query], topk=top_k)

        formatted = []
        for r in results:
            fields = r.fields or {}
            doc = {
                "id": r.id,
                "title": fields.get("title", ""),
                "excerpt": fields.get("full_text", "")[:500],
                "doc_type": fields.get("doc_type", ""),
                "court": fields.get("court", ""),
                "year": fields.get("year", 0),
                "url": fields.get("url", ""),
                "score": r.score or 0.0,
                "source": "fts_search",
            }
            formatted.append(doc)

        return formatted
    except Exception as e:
        logger.warning(f"FTS search error: {e}")
        return []


def get_index_stats() -> Dict[str, Any]:
    """Get statistics about the vector index."""
    try:
        collection = _get_collection()
        stats = collection.stats  # property, not method
        return {
            "initialized": _initialized,
            "collection": COLLECTION_NAME,
            "db_path": str(VECTOR_DB_DIR),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "total_docs": getattr(stats, "total_docs", "unknown"),
        }
    except Exception as e:
        return {
            "initialized": False,
            "error": str(e),
        }


async def index_from_database():
    """Index all documents from SQLite into zvec."""
    import sqlite3
    import asyncio

    db_path = os.path.join(tempfile.gettempdir(), "juriscore.db")
    if not os.path.exists(db_path):
        logger.warning(f"Database not found at {db_path}")
        return 0

    def _read_and_index():
        conn = sqlite3.connect(db_path)
        all_docs = []

        # Cases table
        try:
            cursor = conn.execute("SELECT id, title, excerpt, court, year, url, full_text, doc_type FROM kenyalaw_cases")
            for row in cursor.fetchall():
                doc_id, title, excerpt, court, year, url, full_text, doc_type = row
                all_docs.append({
                    "id": doc_id, "title": title or "", "excerpt": excerpt or "",
                    "court": court or "", "year": year or 0, "url": url or "",
                    "full_text": full_text or "", "doc_type": doc_type or "judgment",
                })
        except Exception as e:
            logger.warning(f"Failed to read kenyalaw_cases: {e}")

        # Legislation table - select only columns that exist
        try:
            cursor = conn.execute("SELECT id, title, excerpt, url, full_text, doc_type FROM kenyalaw_legislation")
            for row in cursor.fetchall():
                doc_id, title, excerpt, url, full_text, doc_type = row
                all_docs.append({
                    "id": doc_id, "title": title or "", "excerpt": excerpt or "",
                    "court": "", "year": 0, "url": url or "",
                    "full_text": full_text or "", "doc_type": doc_type or "legislation",
                })
        except Exception as e:
            logger.warning(f"Failed to read kenyalaw_legislation: {e}")

        # Articles table - select only columns that exist
        try:
            cursor = conn.execute("SELECT id, title, excerpt, url, full_text, doc_type FROM kenyalaw_articles")
            for row in cursor.fetchall():
                doc_id, title, excerpt, url, full_text, doc_type = row
                all_docs.append({
                    "id": doc_id, "title": title or "", "excerpt": excerpt or "",
                    "court": "", "year": 0, "url": url or "",
                    "full_text": full_text or "", "doc_type": doc_type or "article",
                })
        except Exception as e:
            logger.warning(f"Failed to read kenyalaw_articles: {e}")

        conn.close()
        logger.info(f"Read {len(all_docs)} documents from database")

        if all_docs:
            return index_batch(all_docs, batch_size=100)
        return 0

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_and_index)
