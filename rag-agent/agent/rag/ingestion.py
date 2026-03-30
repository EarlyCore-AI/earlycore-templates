"""Document ingestion: load -> chunk -> embed -> store.

Supports .txt, .md, .pdf (if pypdf installed), .docx (if python-docx installed).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path  # -- used at runtime
from typing import TYPE_CHECKING

from rag.embeddings import get_embeddings

if TYPE_CHECKING:
    from config import AgentConfig

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


async def ingest_file(file_path: Path, config: AgentConfig) -> int:
    """Ingest a single file: load -> chunk -> embed -> store. Returns chunk count."""
    text = _load_file(file_path)
    if not text.strip():
        logger.warning("Empty file skipped: %s", file_path)
        return 0

    chunks = _chunk_text(text, config.chunk_size, config.chunk_overlap)
    source = file_path.name

    for chunk in chunks:
        embedding = get_embeddings(chunk, config)
        await _store_chunk(chunk, embedding, source, config)

    logger.info("Ingested %d chunks from %s", len(chunks), file_path)
    return len(chunks)


async def ingest_directory(dir_path: Path, config: AgentConfig) -> int:
    """Ingest all supported files from a directory. Returns total chunk count."""
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    total = 0
    for file_path in sorted(dir_path.rglob("*")):
        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS and file_path.is_file():
            count = await ingest_file(file_path, config)
            total += count
    return total


# -- File loading -------------------------------------------------------------


def _load_file(path: Path) -> str:
    """Read file contents based on extension."""
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    if ext == ".pdf":
        return _load_pdf(path)
    if ext == ".docx":
        return _load_docx(path)
    raise ValueError(f"Unsupported file type: {ext}")


def _load_pdf(path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError("Install pypdf for PDF support: pip install pypdf") from exc
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _load_docx(path: Path) -> str:
    """Extract text from a DOCX file."""
    try:
        import docx
    except ImportError as exc:
        raise ImportError("Install python-docx for DOCX support: pip install python-docx") from exc
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


# -- Chunking -----------------------------------------------------------------


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks by character count."""
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# -- Storage ------------------------------------------------------------------


async def _store_chunk(
    content: str,
    embedding: list[float],
    source: str,
    config: AgentConfig,
) -> None:
    """Store a chunk + embedding in the configured vector store."""
    provider = config.vectorstore_provider.lower()
    chunk_id = hashlib.sha256(content.encode()).hexdigest()[:16]

    if provider == "pgvector":
        await _store_pgvector(chunk_id, content, embedding, source, config)
    elif provider == "pinecone":
        await _store_pinecone(chunk_id, content, embedding, source, config)
    elif provider == "chromadb":
        _store_chromadb(chunk_id, content, embedding, source, config)
    else:
        raise ValueError(f"Unknown vectorstore_provider: {provider}")


async def _store_pgvector(
    chunk_id: str, content: str, embedding: list[float], source: str, config: AgentConfig
) -> None:
    """Insert a chunk into the pgvector documents table."""
    import psycopg

    vector_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    async with await psycopg.AsyncConnection.connect(config.vectorstore_url) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO documents (id, content, source, embedding)
                VALUES (%s, %s, %s, %s::vector)
                ON CONFLICT (id) DO NOTHING
                """,
                (chunk_id, content, source, vector_literal),
            )
        await conn.commit()


async def _store_pinecone(
    chunk_id: str, content: str, embedding: list[float], source: str, config: AgentConfig
) -> None:
    """Upsert a chunk into Pinecone via REST."""
    import httpx

    url = f"https://{config.pinecone_index}/vectors/upsert"
    headers = {"Api-Key": config.pinecone_api_key, "Content-Type": "application/json"}
    payload = {"vectors": [{"id": chunk_id, "values": embedding, "metadata": {"text": content, "source": source}}]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


def _store_chromadb(chunk_id: str, content: str, embedding: list[float], source: str, config: AgentConfig) -> None:
    """Add a chunk to an embedded ChromaDB collection."""
    import chromadb

    client = chromadb.PersistentClient(path=config.chromadb_path)
    collection = client.get_or_create_collection("documents")
    collection.upsert(ids=[chunk_id], embeddings=[embedding], documents=[content], metadatas=[{"source": source}])
