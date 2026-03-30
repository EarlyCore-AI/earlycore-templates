"""Vector store retriever -- supports pgvector, Pinecone, and ChromaDB.

Each backend returns a list of ``Document`` dicts with ``content``,
``source``, and ``score`` keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A retrieved document chunk with provenance."""

    content: str
    source: str
    score: float


async def retrieve(
    query_embedding: list[float],
    config: AgentConfig,
    top_k: int | None = None,
) -> list[Document]:
    """Retrieve relevant documents from the configured vector store."""
    k = top_k or config.top_k
    provider = config.vectorstore_provider.lower()

    if provider == "pgvector":
        return await _pgvector_retrieve(query_embedding, config, k)
    if provider == "pinecone":
        return await _pinecone_retrieve(query_embedding, config, k)
    if provider == "chromadb":
        return _chromadb_retrieve(query_embedding, config, k)
    raise ValueError(f"Unknown vectorstore_provider: {provider}")


# -- pgvector ----------------------------------------------------------------


async def _pgvector_retrieve(
    embedding: list[float],
    config: AgentConfig,
    top_k: int,
) -> list[Document]:
    """Query pgvector using psycopg (async) with cosine distance."""
    import psycopg

    vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    async with await psycopg.AsyncConnection.connect(config.vectorstore_url) as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT content, source, 1 - (embedding <=> %s::vector) AS score
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
            (vector_literal, vector_literal, top_k),
        )
        rows = await cur.fetchall()

    return [Document(content=r[0], source=r[1], score=float(r[2])) for r in rows]


# -- Pinecone ----------------------------------------------------------------


async def _pinecone_retrieve(
    embedding: list[float],
    config: AgentConfig,
    top_k: int,
) -> list[Document]:
    """Query Pinecone via its REST API (no SDK needed)."""
    import httpx

    if not config.pinecone_api_key or not config.pinecone_index:
        raise ValueError("PINECONE_API_KEY and PINECONE_INDEX are required")

    url = f"https://{config.pinecone_index}/query"
    headers = {"Api-Key": config.pinecone_api_key, "Content-Type": "application/json"}
    payload = {"vector": embedding, "topK": top_k, "includeMetadata": True}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()

    matches = resp.json().get("matches", [])
    return [
        Document(
            content=m.get("metadata", {}).get("text", ""),
            source=m.get("metadata", {}).get("source", "unknown"),
            score=float(m.get("score", 0.0)),
        )
        for m in matches
    ]


# -- ChromaDB ----------------------------------------------------------------


def _chromadb_retrieve(
    embedding: list[float],
    config: AgentConfig,
    top_k: int,
) -> list[Document]:
    """Query an embedded ChromaDB collection."""
    try:
        import chromadb
    except ImportError as exc:
        raise ImportError("Install chromadb: pip install chromadb") from exc

    client = chromadb.PersistentClient(path=config.chromadb_path)
    collection = client.get_or_create_collection("documents")
    results = collection.query(query_embeddings=[embedding], n_results=top_k)

    docs: list[Document] = []
    for i, doc_text in enumerate(results["documents"][0]):  # type: ignore[index]
        meta = (results["metadatas"][0][i]) if results["metadatas"] else {}  # type: ignore[index]
        dist = (results["distances"][0][i]) if results["distances"] else 0.0  # type: ignore[index]
        docs.append(Document(content=doc_text, source=meta.get("source", "unknown"), score=1.0 - dist))
    return docs
