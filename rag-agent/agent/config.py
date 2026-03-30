"""Typed configuration loaded from environment variables.

All settings use pydantic-settings so they can be overridden via env vars
or a .env file without touching Python code.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    """Central configuration for the RAG agent.

    Every field maps 1:1 to an environment variable (case-insensitive).
    Example: ``LLM_PROVIDER=openai`` sets ``llm_provider``.
    """

    # -- LLM -----------------------------------------------------------------
    llm_provider: str = "bedrock"
    llm_model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    llm_temperature: float = 0.3
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    aws_region: str = "eu-west-2"

    # -- Vector store ---------------------------------------------------------
    vectorstore_provider: str = "pgvector"
    vectorstore_url: str = "postgresql://earlycore:changeme@postgres:5432/earlycore"
    pinecone_api_key: str = ""
    pinecone_index: str = ""
    chromadb_path: str = "./chromadb_data"

    # -- Embeddings -----------------------------------------------------------
    embedding_provider: str = "bedrock"
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dimension: int = 1024

    # -- Bedrock Guardrails ---------------------------------------------------
    bedrock_guardrail_id: str = ""
    bedrock_guardrail_version: str = ""

    # -- RAG ------------------------------------------------------------------
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5

    # -- Server ---------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8080

    model_config = {"env_prefix": "", "case_sensitive": False}
