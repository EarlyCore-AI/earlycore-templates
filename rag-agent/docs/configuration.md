# Configuration Reference

Complete reference for every configurable field in your EarlyCore RAG agent.

______________________________________________________________________

## earlycore.yaml

The sidecar reads this file to configure guardrails, monitoring, and alerting. Changes require a container restart.

### version

| Field     | Type   | Default | Description                        |
| --------- | ------ | ------- | ---------------------------------- |
| `version` | string | `1.0`   | Configuration file schema version. |

### agent

| Field       | Type   | Default    | Description                                                                                                |
| ----------- | ------ | ---------- | ---------------------------------------------------------------------------------------------------------- |
| `name`      | string | *required* | Client identifier. Lowercase alphanumeric and hyphens only. Used in resource naming, log groups, and tags. |
| `type`      | enum   | `rag`      | Agent type. Values: `rag`, `chatbot`, `code-assistant`. Determines which guardrail presets apply.          |
| `framework` | string | `haystack` | RAG framework label. Informational only -- does not change runtime behaviour.                              |

### llm

| Field         | Type   | Default                                     | Description                                                                                        |
| ------------- | ------ | ------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `provider`    | enum   | `bedrock`                                   | LLM provider. Values: `bedrock`, `openai`, `anthropic`.                                            |
| `model`       | string | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Model identifier. Must match the provider's naming convention.                                     |
| `api_key_env` | string | `LLM_API_KEY`                               | Name of the environment variable holding the API key. Not used for Bedrock (uses AWS credentials). |

### vectorstore

| Field            | Type   | Default           | Description                                                       |
| ---------------- | ------ | ----------------- | ----------------------------------------------------------------- |
| `provider`       | enum   | `pgvector`        | Vector store backend. Values: `pgvector`, `pinecone`, `chromadb`. |
| `connection_env` | string | `VECTORSTORE_URL` | Name of the environment variable holding the connection string.   |

### guardrails

| Field                | Type           | Default    | Description                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------------------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `level`              | enum           | `moderate` | Guardrail strictness. `strict`: blocks aggressively, low false-negative rate. `moderate`: balanced. `permissive`: minimal blocking.                                                                                                                                                                                                                                                                                                              |
| `block_injection`    | boolean        | `true`     | Detect and block prompt injection attempts. Blocked requests return HTTP 403 with an explanation.                                                                                                                                                                                                                                                                                                                                                |
| `block_pii`          | boolean        | `true`     | Scan inputs and outputs for personal information (names, emails, phone numbers, addresses, IDs). Detected PII is redacted before processing.                                                                                                                                                                                                                                                                                                     |
| `local_pii`          | boolean        | `true`     | When `true`, the sidecar runs full Presidio NER-based PII detection locally (slower, maximum privacy -- no data leaves the deployment). When `false`, the sidecar uses a lightweight regex scanner for the most common patterns (emails, phone numbers, credit cards, SSNs, IBANs) and defers deep NER analysis to the EarlyCore platform. Set to `false` to reduce sidecar memory usage and startup time, or when Presidio cannot be installed. |
| `check_groundedness` | boolean        | `true`     | Verify that the generated answer is supported by the retrieved documents. Ungrounded answers are flagged in telemetry.                                                                                                                                                                                                                                                                                                                           |
| `topic_restrictions` | list\[string\] | `[]`       | Topics the agent must refuse to discuss. Example: `["medical advice", "legal counsel", "financial recommendations"]`.                                                                                                                                                                                                                                                                                                                            |

### monitoring

| Field                | Type    | Default                     | Description                                                                              |
| -------------------- | ------- | --------------------------- | ---------------------------------------------------------------------------------------- |
| `enabled`            | boolean | `true`                      | Send telemetry to the EarlyCore platform. Set to `false` to disable monitoring entirely. |
| `earlycore_endpoint` | string  | `https://api.earlycore.dev` | EarlyCore API endpoint. Override only if using a self-hosted EarlyCore instance.         |
| `telemetry_mode`     | enum    | `sidecar`                   | Telemetry routing mode. Values: `sidecar`, `bedrock`, `hybrid`.                          |
| `redteam_mode`       | enum    | `api_only`                  | Redteam execution mode. Current supported value: `api_only`.                             |

### alerts

| Field      | Type           | Default | Description                                                                                                     |
| ---------- | -------------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| `channels` | list\[object\] | `[]`    | Alert destinations. Each entry has `type` (slack, email, teams, pagerduty) and `target` (webhook URL or email). |

**Example with alerts configured:**

```yaml
alerts:
  channels:
    - type: slack
      target: https://hooks.slack.com/services/T00/B00/xxxx
    - type: email
      target: ops@yourcompany.com
```

### deployment

| Field    | Type   | Default     | Description                                                                                    |
| -------- | ------ | ----------- | ---------------------------------------------------------------------------------------------- |
| `target` | enum   | `docker`    | Deployment target. Values: `docker`, `aws`. Controls which infrastructure files are generated. |
| `region` | string | `eu-west-2` | AWS region for cloud deployments. Also used for Bedrock API routing.                           |

______________________________________________________________________

## Environment Variables (.env)

All environment variables consumed by the agent container. Set these in `.env` for local development or in AWS Secrets Manager for production.

### EarlyCore Platform

| Variable             | Required | Default                     | Description                                                                                           |
| -------------------- | -------- | --------------------------- | ----------------------------------------------------------------------------------------------------- |
| `EARLYCORE_API_KEY`  | Yes      | -                           | Your EarlyCore API key. Get one at [app.earlycore.dev/settings](https://app.earlycore.dev/settings).  |
| `EARLYCORE_ENDPOINT` | No       | `https://api.earlycore.dev` | Override for self-hosted EarlyCore installations.                                                     |
| `TELEMETRY_ENABLED`  | No       | `true`                      | Sidecar telemetry toggle. In `bedrock` mode this should be `false`; in `sidecar`/`hybrid` use `true`. |

### LLM Provider

| Variable                | Required     | Default                                     | Description                                                           |
| ----------------------- | ------------ | ------------------------------------------- | --------------------------------------------------------------------- |
| `LLM_PROVIDER`          | No           | `bedrock`                                   | Which LLM to use. Values: `bedrock`, `openai`, `anthropic`.           |
| `LLM_MODEL`             | No           | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Model identifier. Must match the chosen provider.                     |
| `LLM_TEMPERATURE`       | No           | `0.3`                                       | Generation temperature. Lower = more deterministic. Range: 0.0 - 1.0. |
| `AWS_ACCESS_KEY_ID`     | If Bedrock   | -                                           | AWS access key for Bedrock API calls.                                 |
| `AWS_SECRET_ACCESS_KEY` | If Bedrock   | -                                           | AWS secret key for Bedrock API calls.                                 |
| `AWS_DEFAULT_REGION`    | If Bedrock   | `eu-west-2`                                 | AWS region where Bedrock models are available.                        |
| `OPENAI_API_KEY`        | If OpenAI    | -                                           | OpenAI API key. Starts with `sk-`.                                    |
| `ANTHROPIC_API_KEY`     | If Anthropic | -                                           | Anthropic API key. Starts with `sk-ant-`.                             |

### Embedding Provider

| Variable              | Required | Default                        | Description                                                                                       |
| --------------------- | -------- | ------------------------------ | ------------------------------------------------------------------------------------------------- |
| `EMBEDDING_PROVIDER`  | No       | `bedrock`                      | Embedding backend. Values: `bedrock`, `openai`, `local`.                                          |
| `EMBEDDING_MODEL`     | No       | `amazon.titan-embed-text-v2:0` | Embedding model name. For local: any HuggingFace SentenceTransformer model name.                  |
| `EMBEDDING_DIMENSION` | No       | `1024`                         | Vector dimension. Must match the chosen model. Titan v2: 1024. OpenAI ada-002: 1536. MiniLM: 384. |

### Vector Store

| Variable               | Required    | Default                                                   | Description                                                       |
| ---------------------- | ----------- | --------------------------------------------------------- | ----------------------------------------------------------------- |
| `VECTORSTORE_PROVIDER` | No          | `pgvector`                                                | Vector store backend. Values: `pgvector`, `pinecone`, `chromadb`. |
| `VECTORSTORE_URL`      | If pgvector | `postgresql://earlycore:changeme@postgres:5432/earlycore` | PostgreSQL connection string with pgvector extension.             |
| `PINECONE_API_KEY`     | If Pinecone | -                                                         | Pinecone API key.                                                 |
| `PINECONE_INDEX`       | If Pinecone | -                                                         | Pinecone index host URL.                                          |
| `CHROMADB_PATH`        | If ChromaDB | `./chromadb_data`                                         | Local directory for ChromaDB persistent storage.                  |

### Bedrock Guardrails (Optional)

| Variable                    | Required | Default | Description                                                          |
| --------------------------- | -------- | ------- | -------------------------------------------------------------------- |
| `BEDROCK_GUARDRAIL_ID`      | No       | `""`    | Bedrock Guardrail identifier. Set after deploying `guardrails.yaml`. |
| `BEDROCK_GUARDRAIL_VERSION` | No       | `""`    | Bedrock Guardrail version.                                           |

### RAG Pipeline

| Variable        | Required | Default | Description                                                                                                 |
| --------------- | -------- | ------- | ----------------------------------------------------------------------------------------------------------- |
| `CHUNK_SIZE`    | No       | `512`   | Number of characters per document chunk. Larger chunks provide more context but increase token usage.       |
| `CHUNK_OVERLAP` | No       | `50`    | Number of overlapping characters between consecutive chunks. Prevents information loss at chunk boundaries. |
| `TOP_K`         | No       | `5`     | Number of document chunks retrieved per query. Higher values increase recall but add latency and cost.      |

### Database (Local Development)

| Variable            | Required | Default     | Description                                                              |
| ------------------- | -------- | ----------- | ------------------------------------------------------------------------ |
| `POSTGRES_DB`       | No       | `earlycore` | PostgreSQL database name.                                                |
| `POSTGRES_USER`     | No       | `earlycore` | PostgreSQL username.                                                     |
| `POSTGRES_PASSWORD` | Yes      | -           | PostgreSQL password. **Generate a random value. Never use the default.** |

### Server

| Variable | Required | Default   | Description                                                      |
| -------- | -------- | --------- | ---------------------------------------------------------------- |
| `HOST`   | No       | `0.0.0.0` | FastAPI bind address.                                            |
| `PORT`   | No       | `8080`    | FastAPI bind port. The sidecar forwards to this port internally. |

______________________________________________________________________

## CloudFormation Parameters

Parameters for the AWS production deployment (`infra/aws/template.yaml`).

### General

| Parameter     | Type   | Default      | Description                                                                                                |
| ------------- | ------ | ------------ | ---------------------------------------------------------------------------------------------------------- |
| `ClientName`  | string | *required*   | Client identifier. 3-30 chars, lowercase alphanumeric + hyphens. Used in all resource names.               |
| `Environment` | enum   | `production` | Values: `production`, `staging`, `development`. Controls Multi-AZ, instance sizes, and retention policies. |
| `AlertEmail`  | string | *required*   | Email for CloudWatch alarm notifications. Must be confirmed via SNS.                                       |

### Networking

| Parameter | Type   | Default       | Description                                                     |
| --------- | ------ | ------------- | --------------------------------------------------------------- |
| `VpcCidr` | string | `10.0.0.0/16` | VPC CIDR block. Must not overlap with existing VPCs if peering. |

### Compute

| Parameter         | Type   | Default                            | Cost Impact                                                                                                       |
| ----------------- | ------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `ContainerCpu`    | number | `512`                              | 256/512/1024/2048/4096 CPU units. Higher = more compute, more cost.                                               |
| `ContainerMemory` | number | `1024`                             | 512-16384 MB. Must be compatible with CPU value (see [Fargate pricing](https://aws.amazon.com/fargate/pricing/)). |
| `DesiredCount`    | number | `2`                                | Number of running tasks. Set to 1 for staging, 2+ for production.                                                 |
| `MaxCount`        | number | `10`                               | Maximum tasks for auto-scaling.                                                                                   |
| `AgentImageUri`   | string | *required*                         | ECR image URI for your agent container.                                                                           |
| `SidecarImageUri` | string | `ghcr.io/earlycore/sidecar:latest` | EarlyCore sidecar image. Override only if using a pinned version.                                                 |

### Database

| Parameter               | Type    | Default        | Cost Impact                                                                                                                                      |
| ----------------------- | ------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `UseManagedDatabase`    | boolean | `true`         | Use RDS PostgreSQL (`true`) or skip (`false`).                                                                                                   |
| `DatabaseInstanceClass` | enum    | `db.t4g.small` | RDS instance size. `db.t4g.micro` (~$12/mo) for staging, `db.t4g.small` (~$29/mo) for production, `db.r6g.large` (~$150/mo) for high throughput. |
| `DatabaseStorageGB`     | number  | `20`           | Allocated storage. 20 GB minimum. GP3 baseline: 3,000 IOPS.                                                                                      |

### Cache

| Parameter         | Type    | Default           | Cost Impact                                                      |
| ----------------- | ------- | ----------------- | ---------------------------------------------------------------- |
| `UseManagedCache` | boolean | `true`            | Use ElastiCache Redis (`true`) or skip (`false`).                |
| `CacheNodeType`   | enum    | `cache.t4g.micro` | Redis node size. `cache.t4g.micro` (~$13/mo) for most workloads. |

### LLM Provider

| Parameter              | Type             | Default   | Description                                                                                                              |
| ---------------------- | ---------------- | --------- | ------------------------------------------------------------------------------------------------------------------------ |
| `LLMProvider`          | enum             | `bedrock` | Values: `bedrock`, `openai`, `anthropic`. Controls IAM permissions -- Bedrock gets `bedrock:InvokeModel`; others don't.  |
| `UseBedrockGuardrails` | boolean (string) | `true`    | Enable Bedrock Guardrails for content safety and prompt injection defence. Only applies when `LLMProvider` is `bedrock`. |
| `UseCMEK`              | boolean (string) | `false`   | Use a customer-managed KMS key for encryption across all resources.                                                      |
| `TemplateBaseUrl`      | string           | `""`      | S3 URL prefix where nested stack templates are stored. Required for deployment.                                          |

### Secrets

| Parameter         | Type   | Default    | Description                                                                                      |
| ----------------- | ------ | ---------- | ------------------------------------------------------------------------------------------------ |
| `EarlycoreApiKey` | string | *required* | EarlyCore API key. Stored in Secrets Manager. Value hidden in CloudFormation console (`NoEcho`). |

______________________________________________________________________

## Provider-Specific Configuration Examples

### AWS Bedrock (Default)

```bash
LLM_PROVIDER=bedrock
LLM_MODEL=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=eu-west-2
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

### OpenAI

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

### Anthropic Direct

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
EMBEDDING_PROVIDER=bedrock
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

### Local Embeddings (No API Key)

```bash
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

> **Note:** Local embeddings require `sentence-transformers` installed. Add it to `agent/requirements.txt`.

______________________________________________________________________

## Changing Configuration

| What Changed               | Action Required                                                                               |
| -------------------------- | --------------------------------------------------------------------------------------------- |
| `.env` values              | Restart containers: `docker compose down && docker compose up -d`                             |
| `earlycore.yaml`           | Restart containers (sidecar reads config at startup)                                          |
| `agent/prompts/system.txt` | Restart containers (loaded at startup)                                                        |
| `agent/rag/*.py`           | Rebuild and restart: `docker compose up --build`                                              |
| CloudFormation parameters  | Update stack: `aws cloudformation update-stack ...`                                           |
| Embedding model            | **Breaking change.** Drop and re-create the vector store table, then re-ingest all documents. |
