"""Core RAG pipeline: embed -> retrieve -> prompt -> generate.

No framework dependency -- uses raw API calls to LLM providers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from rag.embeddings import get_embeddings
from rag.retriever import Document, retrieve

if TYPE_CHECKING:
    from config import AgentConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.txt"


@dataclass
class Answer:
    """Response payload returned by the RAG pipeline."""

    answer: str
    sources: list[str] = field(default_factory=list)


async def run_rag(question: str, config: AgentConfig) -> Answer:
    """Execute the full RAG pipeline and return an answer with sources."""
    # 1. Embed the question
    query_embedding = get_embeddings(question, config)

    # 2. Retrieve relevant documents
    docs = await retrieve(query_embedding, config, top_k=config.top_k)

    # 3. Build the prompt
    system_prompt = _load_system_prompt()
    prompt = _build_prompt(question, docs, system_prompt)

    # 4. Generate answer
    answer_text = await _generate(prompt, system_prompt, config)

    # 5. Return with sources
    sources = list({d.source for d in docs if d.source != "unknown"})
    return Answer(answer=answer_text, sources=sources)


def _load_system_prompt() -> str:
    """Load the system prompt from the prompts directory."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text().strip()
    return "You are a helpful assistant. Answer based only on the provided context."


def _build_prompt(question: str, docs: list[Document], system_prompt: str) -> str:
    """Assemble the user prompt with retrieved context."""
    context_parts = [f"[{i + 1}] ({d.source})\n{d.content}" for i, d in enumerate(docs)]
    context_block = "\n\n".join(context_parts) if context_parts else "(No relevant documents found.)"

    return (
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer the question based only on the context above. "
        "Cite sources using [n] notation where applicable."
    )


# -- LLM generation ----------------------------------------------------------


async def _generate(prompt: str, system_prompt: str, config: AgentConfig) -> str:
    """Route to the correct LLM provider and return generated text."""
    provider = config.llm_provider.lower()
    if provider == "bedrock":
        return await _bedrock_generate(prompt, system_prompt, config)
    if provider == "openai":
        return await _openai_generate(prompt, system_prompt, config)
    if provider == "anthropic":
        return await _anthropic_generate(prompt, system_prompt, config)
    raise ValueError(f"Unknown llm_provider: {provider}")


class GuardrailBlockedError(Exception):
    """Raised when Bedrock Guardrails blocks the request or response."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


async def _bedrock_generate(prompt: str, system_prompt: str, config: AgentConfig) -> str:
    """Invoke a Bedrock model (Claude) via boto3 with optional guardrail."""
    import boto3

    client = boto3.client("bedrock-runtime", region_name=config.aws_region)
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "temperature": config.llm_temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    invoke_kwargs: dict[str, str] = {"modelId": config.llm_model, "body": body}

    # Attach Bedrock Guardrails when configured
    if config.bedrock_guardrail_id:
        invoke_kwargs["guardrailIdentifier"] = config.bedrock_guardrail_id
        invoke_kwargs["guardrailVersion"] = config.bedrock_guardrail_version or "DRAFT"

    response = client.invoke_model(**invoke_kwargs)

    # Check for guardrail intervention
    guardrail_action = (
        response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get("x-amzn-bedrock-guardrail-action")
    )
    if guardrail_action == "BLOCKED":
        logger.warning("Bedrock guardrail blocked the request/response")
        raise GuardrailBlockedError(
            "Your request was blocked by the content safety policy. Please rephrase and try again."
        )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


async def _openai_generate(prompt: str, system_prompt: str, config: AgentConfig) -> str:
    """Call the OpenAI Chat Completions API."""
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when llm_provider=openai")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.openai_api_key}"},
            json={
                "model": config.llm_model,
                "temperature": config.llm_temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _anthropic_generate(prompt: str, system_prompt: str, config: AgentConfig) -> str:
    """Call the Anthropic Messages API."""
    if not config.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": config.llm_model,
                "max_tokens": 2048,
                "temperature": config.llm_temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
    return resp.json()["content"][0]["text"]
