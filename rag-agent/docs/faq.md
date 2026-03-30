# Frequently Asked Questions

______________________________________________________________________

## General

### Can I use my own LLM?

Yes. Set `LLM_PROVIDER` and `LLM_MODEL` in your `.env` file. Supported providers out of the box:

- **AWS Bedrock** (Claude, Titan, Llama) -- default
- **OpenAI** (GPT-4o, GPT-4o mini)
- **Anthropic** (Claude via direct API)

To add another provider, implement a new `_generate` function in `agent/rag/pipeline.py`. The sidecar is provider-agnostic.

______________________________________________________________________

### Can I use LangChain instead of the built-in pipeline?

Yes. Replace the contents of `agent/rag/` with your LangChain pipeline code. The sidecar is framework-agnostic -- it only cares about the HTTP request and response. Your agent just needs to expose `/health` and `/query` endpoints.

______________________________________________________________________

### Can I deploy without the EarlyCore sidecar?

Yes, but you lose guardrails and monitoring. To run the agent standalone:

1. Change the port mapping in `docker-compose.yml` to expose the agent directly:
   ```yaml
   agent:
     ports:
       - "8443:8080"
   ```
1. Comment out the `earlycore-sidecar` service.

______________________________________________________________________

### What Python version is required?

Python 3.11+. The Dockerfile pins `python:3.11-slim` with a specific image digest.

______________________________________________________________________

### How do I update the agent code after deployment?

**Local:** Rebuild and restart:

```bash
docker compose up --build -d
```

**AWS:** Build a new image, push to ECR, and force a new deployment:

```bash
docker build -t your-agent ./agent
docker tag your-agent:latest YOUR_ECR_URI:latest
docker push YOUR_ECR_URI:latest
aws ecs update-service --cluster your-cluster --service your-service --force-new-deployment
```

______________________________________________________________________

## RAG Pipeline

### How do I add my documents?

Three options depending on your deployment:

**Local development:**

```bash
mkdir -p documents
cp your-files/* documents/

# Upload a single file
curl -X POST http://localhost:8443/ingest \
  -F "file=@documents/your-file.pdf"

# Or ingest an entire directory (must be under /data or /tmp/earlycore)
curl -X POST http://localhost:8443/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory": "/data/documents"}'
```

**AWS production:**

```bash
aws s3 cp ./documents/ s3://your-bucket/documents/ --recursive
# Then trigger ingestion via the /ingest endpoint
```

**Supported formats:** `.txt`, `.md`, `.pdf`, `.docx`

______________________________________________________________________

### Can I use Pinecone instead of pgvector?

Yes. Update your `.env`:

```bash
VECTORSTORE_PROVIDER=pinecone
PINECONE_API_KEY=your-key
PINECONE_INDEX=your-index-host-url.svc.us-east-1.pinecone.io
```

No code changes needed. The retriever automatically uses the configured provider.

______________________________________________________________________

### Can I use ChromaDB?

Yes, for local development and prototyping:

```bash
VECTORSTORE_PROVIDER=chromadb
CHROMADB_PATH=./chromadb_data
```

ChromaDB runs embedded in the agent process. Not recommended for production.

______________________________________________________________________

### How do I change the chunk size?

Set `CHUNK_SIZE` and `CHUNK_OVERLAP` in your `.env`:

```bash
CHUNK_SIZE=256    # Characters per chunk (default: 512)
CHUNK_OVERLAP=25  # Overlap between chunks (default: 50)
```

After changing, re-ingest all documents for the new settings to take effect.

______________________________________________________________________

### How do I use a different embedding model?

Set `EMBEDDING_PROVIDER` and `EMBEDDING_MODEL` in your `.env`:

```bash
# Option: Local (free, no API key)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Option: OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

> **Important:** Changing the embedding model requires dropping the documents table and re-ingesting all documents. Existing embeddings are incompatible with a new model.

______________________________________________________________________

### How many documents can I index?

| Vector Store                | Practical Limit | Notes                          |
| --------------------------- | --------------- | ------------------------------ |
| pgvector (local Docker)     | ~100K chunks    | Limited by container RAM       |
| pgvector (RDS db.t4g.small) | ~1M chunks      | Add HNSW index for performance |
| pgvector (RDS db.r6g.large) | ~10M chunks     | Production-grade               |
| Pinecone                    | Billions        | Managed scaling                |
| ChromaDB                    | ~50K chunks     | Prototyping only               |

______________________________________________________________________

## Security

### What happens if EarlyCore is down?

The sidecar **fails open**. If it cannot reach the EarlyCore API:

- Your agent continues to work normally.
- Guardrails continue to run locally (they don't depend on the API).
- Telemetry is buffered and sent when connectivity is restored.
- Alerts pause until the connection is re-established.

Your users will not notice any disruption.

______________________________________________________________________

### Is my data sent to EarlyCore?

Only **anonymised telemetry**. Specifically:

| Sent to EarlyCore          | NOT Sent to EarlyCore   |
| -------------------------- | ----------------------- |
| Request count              | User queries            |
| Latency metrics            | Document contents       |
| Guardrail event counts     | Agent responses         |
| Error types (not messages) | PII (redacted locally)  |
| Token usage                | API keys or credentials |

PII is redacted locally by the sidecar before any telemetry is generated.

______________________________________________________________________

### Where are my API keys stored?

| Environment       | Storage                   | Accessed By         |
| ----------------- | ------------------------- | ------------------- |
| Local development | `.env` file (git-ignored) | Docker Compose      |
| AWS production    | AWS Secrets Manager       | ECS task definition |

API keys are **never** stored in code, images, or CloudFormation templates. The `EarlycoreApiKey` parameter uses `NoEcho: true` so it doesn't appear in the CloudFormation console.

______________________________________________________________________

### How do I rotate API keys?

**Local:** Update the key in `.env` and restart containers.

**AWS:** Update the secret in Secrets Manager and force a new ECS deployment:

```bash
aws secretsmanager update-secret \
  --secret-id your-client-name/earlycore-api-key \
  --secret-string "new-key-value"

aws ecs update-service --cluster your-cluster --service your-service --force-new-deployment
```

______________________________________________________________________

## Deployment

### How long does the AWS deployment take?

| Resource            | Typical Time      |
| ------------------- | ----------------- |
| VPC + Subnets       | 2-3 minutes       |
| RDS PostgreSQL      | 10-15 minutes     |
| ElastiCache Redis   | 5-8 minutes       |
| ECS Cluster + Tasks | 3-5 minutes       |
| **Total**           | **15-20 minutes** |

RDS is the bottleneck. Everything else runs in parallel via nested CloudFormation stacks.

______________________________________________________________________

### Can I use an existing VPC?

Not in the current version. The template creates a dedicated VPC to ensure correct subnet layout and security group configuration. Future versions will support importing existing VPC and subnet IDs.

______________________________________________________________________

### Can I deploy to a different AWS region?

Yes. Change the `region` in `earlycore.yaml` and the `AWS_DEFAULT_REGION` in `.env`:

```yaml
deployment:
  region: us-east-1
```

Verify that your chosen LLM model is available in that region. Bedrock model availability varies by region.

______________________________________________________________________

### What is the minimum server spec for Docker production?

| Resource | Minimum                            | Recommended |
| -------- | ---------------------------------- | ----------- |
| CPU      | 2 cores                            | 4 cores     |
| RAM      | 4 GB                               | 8 GB        |
| Disk     | 20 GB                              | 50 GB       |
| OS       | Ubuntu 22.04+ or Amazon Linux 2023 | -           |

______________________________________________________________________

## Monitoring

### How do I set up Slack alerts?

1. Create a Slack webhook at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks).
1. Add it to `earlycore.yaml`:
   ```yaml
   alerts:
     channels:
       - type: slack
         target: https://hooks.slack.com/services/T00/B00/xxxx
   ```
1. Restart the sidecar: `docker compose restart earlycore-sidecar`

______________________________________________________________________

### Can I white-label the monitoring reports?

Yes. Agency branding is available on the Professional and Enterprise plans. Contact [sales@earlycore.dev](mailto:sales@earlycore.dev) for details.

______________________________________________________________________

## Cost

### How much does EarlyCore monitoring cost?

EarlyCore monitoring is a separate subscription. Contact [sales@earlycore.dev](mailto:sales@earlycore.dev) for current pricing. See [Cost Estimation](cost-estimation.md) for infrastructure and LLM costs.

______________________________________________________________________

### What is the cheapest production setup?

The minimal AWS setup costs approximately **$102/month**:

- 1 ECS Fargate task (0.5 vCPU, 1 GB)
- db.t4g.micro RDS
- cache.t4g.micro ElastiCache
- 1 NAT Gateway
- 1 ALB

Plus LLM costs (use `GPT-4o mini` or `Claude 3.5 Haiku` for the lowest per-query cost). See [Cost Estimation](cost-estimation.md) for full details.

______________________________________________________________________

### Can I reduce costs during development?

Yes. Use **local development** (Path 1 in the Setup Guide) for $0/month. Everything runs in Docker on your machine. Only deploy to AWS when you're ready for staging or production.
