"""EarlyCore RAG Agent -- Production-ready FastAPI application.

Provides document ingestion, RAG querying, health checks, and agent
discovery endpoints.  All configuration comes from environment variables
(see ``config.py``).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from config import AgentConfig
from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel
from rag.ingestion import SUPPORTED_EXTENSIONS, ingest_directory, ingest_file
from rag.pipeline import Answer, run_rag

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="EarlyCore RAG Agent", version="1.0.0")
config = AgentConfig()

# Security constants
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_INGEST_ROOTS: list[str] = ["/data", "/tmp/earlycore"]


# -- Request / response models -----------------------------------------------


class Query(BaseModel):
    """Incoming question payload."""

    question: str


class IngestDirRequest(BaseModel):
    """Request to ingest a directory of documents."""

    directory: str


class IngestResult(BaseModel):
    """Result of an ingestion operation."""

    chunks_ingested: int
    message: str


class HealthStatus(BaseModel):
    """Health check response."""

    status: str
    vectorstore: str
    llm: str


class AgentInfo(BaseModel):
    """Metadata for a discovered AI agent."""

    name: str
    version: str
    capabilities: list[str]


# -- Endpoints ---------------------------------------------------------------


@app.post("/query", response_model=Answer)
async def query(q: Query) -> Answer:
    """Process a RAG query through the full pipeline."""
    logger.info("Query received: %s", q.question[:80])
    return await run_rag(q.question, config)


@app.post("/ingest", response_model=IngestResult)
async def ingest(file: UploadFile) -> IngestResult:
    """Ingest an uploaded document into the vector store."""
    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()

    # Validate file extension against the allow-list
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: '{suffix}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Read and enforce upload size limit
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Maximum allowed: {MAX_UPLOAD_SIZE} bytes.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        count = await ingest_file(tmp_path, config)
    finally:
        tmp_path.unlink(missing_ok=True)

    return IngestResult(chunks_ingested=count, message=f"Ingested {filename} ({count} chunks)")


@app.post("/ingest/directory", response_model=IngestResult)
async def ingest_dir(request: IngestDirRequest) -> IngestResult:
    """Ingest all documents from a directory on the server filesystem."""
    dir_path = Path(request.directory).resolve()

    # Prevent path traversal: the resolved path must be under an allowed root
    if not any(dir_path.is_relative_to(root) for root in ALLOWED_INGEST_ROOTS):
        raise HTTPException(
            status_code=403,
            detail="Directory is outside the allowed ingestion paths.",
        )

    # Reject symlinks to prevent symlink-based escapes
    if dir_path.is_symlink():
        raise HTTPException(status_code=403, detail="Symlinked directories are not allowed.")

    count = await ingest_directory(dir_path, config)
    return IngestResult(chunks_ingested=count, message=f"Ingested {count} chunks from {dir_path}")


@app.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """Health check including configuration summary."""
    return HealthStatus(
        status="ok",
        vectorstore=config.vectorstore_provider,
        llm=f"{config.llm_provider}/{config.llm_model}",
    )


@app.get("/agents", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """List discovered AI agents (for EarlyCore monitoring)."""
    return [
        AgentInfo(
            name="rag-agent",
            version="1.0.0",
            capabilities=["query", "ingest", "ingest-directory"],
        ),
    ]
