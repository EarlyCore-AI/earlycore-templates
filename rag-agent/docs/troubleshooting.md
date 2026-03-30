# Troubleshooting

Common issues with exact error messages and exact fixes.

______________________________________________________________________

## Docker / Container Issues

### "Connection refused" when testing /health

**Error:**

```
curl: (7) Failed to connect to localhost port 8443: Connection refused
```

**Cause:** Containers haven't finished starting, or the sidecar failed its health check.

**Fix:**

1. Check container status:
   ```bash
   docker compose ps
   ```
1. Check sidecar logs:
   ```bash
   docker compose logs earlycore-sidecar --tail 20
   ```
1. If the sidecar shows `EARLYCORE_API_KEY not set`: add your key to `.env`.
1. Restart:
   ```bash
   docker compose down && docker compose up -d
   ```

______________________________________________________________________

### Port 8443 already in use

**Error:**

```
Bind for 0.0.0.0:8443 failed: port is already allocated
```

**Cause:** Another process is using port 8443.

**Fix:**

1. Find the process:
   ```bash
   lsof -i :8443
   ```
1. Stop it, or change the sidecar port in `docker-compose.yml`:
   ```yaml
   ports:
     - "9443:8443"
   ```

______________________________________________________________________

### Container exits with "read-only file system"

**Error:**

```
OSError: [Errno 30] Read-only file system: '/app/some-file'
```

**Cause:** The containers run with `read_only: true` for security. Your code is trying to write to the application directory.

**Fix:**
Write temporary files to `/tmp` instead. The `tmpfs` mount is available at `/tmp` with a 64 MB limit:

```python
# Instead of:
with open("/app/cache.json", "w") as f: ...

# Use:
with open("/tmp/cache.json", "w") as f: ...
```

______________________________________________________________________

### Docker build fails at pip install

**Error:**

```
ERROR: Could not find a version that satisfies the requirement haystack-ai>=2.0.0
```

**Cause:** The commented-out dependencies in `requirements.txt` were uncommented but the package name changed.

**Fix:**
Check the current package name on PyPI. For Haystack:

```
haystack-ai>=2.0.0
```

For LangChain:

```
langchain>=0.1.0
langchain-community>=0.0.10
```

______________________________________________________________________

### PostgreSQL container won't start

**Error:**

```
FATAL: password authentication failed for user "earlycore"
```

**Cause:** The `POSTGRES_PASSWORD` in `.env` doesn't match the password in the `VECTORSTORE_URL` connection string.

**Fix:**
Ensure both values match in `.env`:

```bash
POSTGRES_PASSWORD=my_secure_password
VECTORSTORE_URL=postgresql://earlycore:my_secure_password@postgres:5432/earlycore
```

Then reset the database volume:

```bash
docker compose down -v
docker compose up -d
```

> **Warning:** `docker compose down -v` deletes the database volume. Re-ingest your documents after.

______________________________________________________________________

## Connection Issues

### Agent can't reach PostgreSQL

**Error:**

```
psycopg.OperationalError: connection to server at "postgres" (172.x.x.x), port 5432 failed: Connection refused
```

**Cause:** The PostgreSQL container hasn't finished initialising.

**Fix:**

1. Wait 10-15 seconds after `docker compose up` for PostgreSQL to become ready.
1. Check its health:
   ```bash
   docker compose ps postgres
   ```
1. If status is `unhealthy`, check logs:
   ```bash
   docker compose logs postgres --tail 20
   ```

______________________________________________________________________

### Agent can't reach Redis

**Error:**

```
redis.exceptions.ConnectionError: Error connecting to redis:6379
```

**Cause:** Redis container not started or unhealthy.

**Fix:**

```bash
docker compose ps redis
docker compose logs redis --tail 20
```

If Redis keeps restarting, check that the memory limit (128 MB) is sufficient:

```bash
docker stats redis
```

______________________________________________________________________

### Sidecar can't reach EarlyCore API

**Error (in sidecar logs):**

```
Failed to send telemetry: connection to api.earlycore.dev timed out
```

**Cause:** No outbound internet access, firewall blocking HTTPS, or DNS resolution failure.

**Fix:**

1. Test DNS from inside the container:
   ```bash
   docker compose exec earlycore-sidecar nslookup api.earlycore.dev
   ```
1. Test connectivity:
   ```bash
   docker compose exec earlycore-sidecar curl -I https://api.earlycore.dev/health
   ```
1. If behind a corporate proxy, configure the proxy in the sidecar environment:
   ```yaml
   environment:
     - HTTPS_PROXY=http://proxy.company.com:8080
   ```

> **Note:** The sidecar fails open. If it cannot reach EarlyCore, your agent continues to work -- but monitoring and alerts are paused until connectivity is restored.

______________________________________________________________________

## LLM Provider Issues

### Bedrock returns AccessDeniedException

**Error:**

```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the InvokeModel operation
```

**Cause:** Either the AWS credentials are invalid, or the model hasn't been enabled in your Bedrock console.

**Fix:**

1. Verify credentials:
   ```bash
   aws sts get-caller-identity
   ```
1. Enable model access:
   - Go to the [Bedrock console](https://console.aws.amazon.com/bedrock/)
   - Select your region
   - Go to **Model access** and request access for the model specified in your `.env`
1. If using a non-default region, ensure the model is available there.

______________________________________________________________________

### OpenAI returns 401 Unauthorized

**Error:**

```
httpx.HTTPStatusError: 401 Unauthorized
```

**Cause:** Invalid or expired OpenAI API key.

**Fix:**

1. Verify the key is set:
   ```bash
   grep OPENAI_API_KEY .env
   ```
1. Test the key directly:
   ```bash
   curl -H "Authorization: Bearer sk-your-key" https://api.openai.com/v1/models
   ```
1. Generate a new key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) if needed.

______________________________________________________________________

### LLM returns empty or truncated responses

**Cause:** The context window is too large (too many retrieved documents), or `max_tokens` is set too low.

**Fix:**

1. Reduce `TOP_K` in `.env` to retrieve fewer documents:
   ```bash
   TOP_K=3
   ```
1. Reduce `CHUNK_SIZE` to make each chunk shorter:
   ```bash
   CHUNK_SIZE=256
   ```
1. If using a model with a small context window, switch to a model with a larger one.

______________________________________________________________________

## Vector Store Issues

### "relation 'documents' does not exist"

**Error:**

```
psycopg.errors.UndefinedTable: relation "documents" does not exist
```

**Cause:** The documents table hasn't been created yet. This happens when you skip the ingestion step.

**Fix:**
Run the ingestion endpoint to initialise the table, or create it manually:

```bash
docker compose exec postgres psql -U earlycore -d earlycore -c "
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    embedding vector(1024)
  );
  CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops);
"
```

Adjust the vector dimension (`1024`) to match your embedding model.

______________________________________________________________________

### Embedding dimension mismatch

**Error:**

```
ERROR: expected 1024 dimensions, not 1536
```

**Cause:** You changed the embedding model without re-creating the vector store table.

**Fix:**

1. Drop the existing table and re-create it with the correct dimension:
   ```bash
   docker compose exec postgres psql -U earlycore -d earlycore -c "
     DROP TABLE IF EXISTS documents;
     CREATE TABLE documents (
       id TEXT PRIMARY KEY,
       content TEXT NOT NULL,
       source TEXT NOT NULL DEFAULT 'unknown',
       embedding vector(1536)
     );
     CREATE INDEX documents_embedding_idx
       ON documents USING hnsw (embedding vector_cosine_ops);
   "
   ```
1. Re-ingest all documents.

______________________________________________________________________

### Pinecone returns 403 Forbidden

**Error:**

```
httpx.HTTPStatusError: 403 Forbidden
```

**Cause:** Invalid Pinecone API key or wrong index host URL.

**Fix:**

1. Verify `PINECONE_API_KEY` and `PINECONE_INDEX` in `.env`.
1. The `PINECONE_INDEX` should be the full host URL (e.g., `your-index-abc1234.svc.us-east-1.pinecone.io`), not just the index name.

______________________________________________________________________

## AWS Deployment Issues

### CloudFormation stack fails at VPC

**Error:**

```
The CIDR '10.0.0.0/16' conflicts with another subnet
```

**Cause:** The VPC CIDR block overlaps with an existing VPC in the same account and region.

**Fix:**
Change the `VpcCidr` parameter to a non-overlapping range:

```bash
--parameter-overrides VpcCidr=10.1.0.0/16
```

______________________________________________________________________

### ECS tasks keep restarting

**Symptoms:** Tasks cycle between `RUNNING` and `STOPPED`. Health checks fail.

**Fix:**

1. Check the stopped task reason:
   ```bash
   aws ecs describe-tasks \
     --cluster your-client-name-cluster \
     --tasks $(aws ecs list-tasks --cluster your-client-name-cluster --desired-status STOPPED --query "taskArns[0]" --output text) \
     --query "tasks[0].stoppedReason"
   ```
1. Check container logs in CloudWatch: `/ecs/your-client-name/agent`
1. Common causes:
   - Missing or invalid secrets in Secrets Manager
   - Agent image not found in ECR
   - Container running out of memory (increase `ContainerMemory`)

______________________________________________________________________

### ALB returns 503 Service Unavailable

**Cause:** No healthy ECS tasks behind the load balancer.

**Fix:**

1. Check target group health:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn $(aws elbv2 describe-target-groups --query "TargetGroups[?contains(TargetGroupName,'your-client-name')].TargetGroupArn" --output text)
   ```
1. If targets are `unhealthy`: check ECS task logs for startup errors.
1. If targets are `draining`: a deployment is in progress. Wait 2-3 minutes.

______________________________________________________________________

### Stack deletion hangs

**Cause:** Non-empty S3 bucket or ENI still attached.

**Fix:**

1. Empty the S3 bucket first:
   ```bash
   aws s3 rm s3://your-client-name-documents --recursive
   ```
1. Then delete the stack:
   ```bash
   aws cloudformation delete-stack --stack-name your-client-name-production
   ```

______________________________________________________________________

## Configuration Issues

### Agent ignores changes to system prompt

**Cause:** The system prompt is loaded at container startup and cached in memory.

**Fix:**
Restart the agent container after changing `agent/prompts/system.txt`:

```bash
docker compose restart agent
```

______________________________________________________________________

### Changes to .env have no effect

**Cause:** Docker Compose caches environment variables. A simple `restart` doesn't re-read `.env`.

**Fix:**

```bash
docker compose down && docker compose up -d
```

______________________________________________________________________

## Permission Issues

### "Permission denied" writing to /app

**Cause:** The container runs as non-root user `agent` (UID 1000) with a read-only filesystem.

**Fix:**

- Write temporary data to `/tmp` (tmpfs mount).
- For persistent data, add a named volume in `docker-compose.yml`.

______________________________________________________________________

## Still Stuck?

1. Check the [FAQ](faq.md) for common questions.
1. Review the [EarlyCore status page](https://status.earlycore.dev) for platform issues.
1. Contact support at [support@earlycore.dev](mailto:support@earlycore.dev) with:
   - Your agent name (from `earlycore.yaml`)
   - The exact error message
   - Output of `docker compose logs --tail 50`
