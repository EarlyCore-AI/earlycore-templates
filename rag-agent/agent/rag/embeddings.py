"""Embedding model factory -- framework-agnostic, uses raw API calls.

Supports AWS Bedrock Titan, OpenAI, and local SentenceTransformers.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from config import AgentConfig

logger = logging.getLogger(__name__)

# Cache the local model so we only load it once per process.
_local_model: object | None = None


def get_embeddings(text: str, config: AgentConfig) -> list[float]:
    """Generate an embedding vector for *text* using the configured provider."""
    provider = config.embedding_provider.lower()
    if provider == "bedrock":
        return _bedrock_embed(text, config)
    if provider == "openai":
        return _openai_embed(text, config)
    return _local_embed(text, config)


# -- Bedrock -----------------------------------------------------------------


def _bedrock_embed(text: str, config: AgentConfig) -> list[float]:
    """Call AWS Bedrock Titan Embeddings via boto3."""
    import boto3  # -- optional dep, imported lazily

    client = boto3.client("bedrock-runtime", region_name=config.aws_region)
    body = json.dumps({"inputText": text})
    response = client.invoke_model(modelId=config.embedding_model, body=body)
    result = json.loads(response["body"].read())
    return result["embedding"]


# -- OpenAI ------------------------------------------------------------------


def _openai_embed(text: str, config: AgentConfig) -> list[float]:
    """Call the OpenAI embeddings API over HTTPS."""
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when embedding_provider=openai")

    resp = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {config.openai_api_key}"},
        json={"input": text, "model": config.embedding_model},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# -- Local SentenceTransformers ----------------------------------------------


def _local_embed(text: str, config: AgentConfig) -> list[float]:
    """Use a local SentenceTransformer model (no API key needed)."""
    global _local_model

    if _local_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "Install sentence-transformers for local embeddings: pip install sentence-transformers"
            ) from exc
        model_name = config.embedding_model or "all-MiniLM-L6-v2"
        logger.info("Loading local embedding model: %s", model_name)
        _local_model = SentenceTransformer(model_name)

    vector = _local_model.encode(text)  # type: ignore[union-attr]
    return vector.tolist()
