# Setup Guide

Three deployment paths. Pick the one that matches your situation.

| Path                                           | Time       | Cost             | Best For                    |
| ---------------------------------------------- | ---------- | ---------------- | --------------------------- |
| [Local Development](#path-1-local-development) | 5 minutes  | $0/month         | Development, testing, demos |
| [AWS Production](#path-2-aws-production)       | 30 minutes | ~$220/month      | Production workloads        |
| [Docker Production](#path-3-docker-production) | 15 minutes | Server cost only | Self-hosted production      |

______________________________________________________________________

## Path 1: Local Development

Everything runs on your machine via Docker Compose. No cloud costs.

### Prerequisites

| Requirement       | Version | Check                                              |
| ----------------- | ------- | -------------------------------------------------- |
| Docker            | 24+     | `docker --version`                                 |
| Docker Compose    | v2+     | `docker compose version`                           |
| EarlyCore API key | -       | [Get one here](https://app.earlycore.dev/settings) |
| LLM API key       | -       | AWS credentials, OpenAI key, or Anthropic key      |

### Step 1: Configure Environment

```bash
cp .env.example .env
```

Open `.env` and set the required values:

```bash
# Required
EARLYCORE_API_KEY=ec_your_key_here

# Option A: AWS Bedrock (default)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=eu-west-2

# Option B: OpenAI (uncomment in .env)
# OPENAI_API_KEY=sk-...

# Option C: Anthropic (uncomment in .env)
# ANTHROPIC_API_KEY=sk-ant-...

# Database password (change this)
POSTGRES_PASSWORD=your_secure_password_here
VECTORSTORE_URL=postgresql://earlycore:your_secure_password_here@postgres:5432/earlycore
```

> **Security note:** Generate a random password for `POSTGRES_PASSWORD`. Never use the default.

### Step 2: Customise Your Agent

Edit the system prompt to define your agent's behaviour:

```bash
nano agent/prompts/system.txt
```

This controls how the agent responds. See the default for a starting point.

### Step 3: Review Guardrails

Open `earlycore.yaml` and confirm the guardrail settings match your requirements:

```yaml
guardrails:
  level: moderate        # strict | moderate | permissive
  block_injection: true  # Detect prompt injection attacks
  block_pii: true        # Redact personal information
  check_groundedness: true  # Ensure answers cite retrieved docs
  topic_restrictions: [] # Add forbidden topics here
```

### Step 4: Start the Agent

Using the EarlyCore CLI:

```bash
earlycore deploy --dev
```

Telemetry mode behavior:

- `sidecar` / `hybrid`: health + query endpoints are exposed via sidecar on `:8443`
- `bedrock`: sidecar telemetry is disabled and the direct agent endpoint on `:8080` is the primary local route

Or directly with Docker Compose:

```bash
docker compose up --build
```

Wait for all containers to report healthy. You should see output similar to:

```
postgres  | database system is ready to accept connections
redis     | Ready to accept connections
agent     | Uvicorn running on http://0.0.0.0:8080
sidecar   | EarlyCore sidecar ready on :8443
```

### Step 5: Verify

Check the health endpoint:

```bash
curl http://localhost:8443/health
```

Expected response:

```json
{"status": "ok", "vectorstore": "pgvector", "llm": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"}
```

Send a test query:

```bash
curl -X POST http://localhost:8443/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello, can you help me?"}'
```

Expected response:

```json
{
  "answer": "This is a placeholder response...",
  "sources": ["setup-guide.md"]
}
```

### Step 6: Ingest Documents

Add your documents to a `documents/` directory and trigger ingestion:

```bash
mkdir -p documents
cp your-files/*.pdf documents/

# Upload a single file
curl -X POST http://localhost:8443/ingest \
  -F "file=@documents/your-file.pdf"

# Or ingest an entire directory (must be under /data or /tmp/earlycore in the container)
curl -X POST http://localhost:8443/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory": "/data/documents"}'
```

Supported formats: `.txt`, `.md`, `.pdf`, `.docx`.

### Step 7: Monitor

View real-time security events and monitoring at:

- **EarlyCore Dashboard:** [app.earlycore.dev](https://app.earlycore.dev)
- **Local logs:** `docker compose logs -f`

### Common Issues (Local)

| Symptom                                   | Cause                                        | Fix                                                                          |
| ----------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------- |
| Port 8443 already in use                  | Another service on that port                 | `lsof -i :8443` then stop it, or change the port in `docker-compose.yml`     |
| Sidecar shows "EARLYCORE_API_KEY not set" | Missing or empty key in `.env`               | Add your key to `.env` and run `docker compose down && docker compose up -d` |
| Agent can't reach PostgreSQL              | Container hasn't finished starting           | Wait 10 seconds and retry. Check: `docker compose ps`                        |
| Bedrock returns 403                       | Invalid AWS credentials or model not enabled | Verify credentials in `.env`. Enable model access in the Bedrock console.    |

______________________________________________________________________

## Path 2: AWS Production

Full cloud deployment with VPC, ECS Fargate, RDS, ElastiCache, S3, and CloudWatch.

### Prerequisites

| Requirement                        | Version | Check                                              |
| ---------------------------------- | ------- | -------------------------------------------------- |
| AWS CLI                            | v2+     | `aws --version`                                    |
| Docker                             | 24+     | `docker --version`                                 |
| EarlyCore CLI                      | latest  | `earlycore --version`                              |
| AWS account with admin permissions | -       | `aws sts get-caller-identity`                      |
| EarlyCore API key                  | -       | [Get one here](https://app.earlycore.dev/settings) |

### Step 1: Configure AWS Credentials

```bash
aws configure
```

Enter your access key, secret key, and region (`eu-west-2` recommended for EU data residency).

Verify access:

```bash
aws sts get-caller-identity
```

### Step 2: Build and Push Agent Image

Create an ECR repository and push the agent image:

```bash
# Create repository
aws ecr create-repository --repository-name your-client-name-agent --region eu-west-2

# Login to ECR
aws ecr get-login-password --region eu-west-2 | \
  docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-2.amazonaws.com

# Build and push
docker build -t your-client-name-agent ./agent
docker tag your-client-name-agent:latest $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-2.amazonaws.com/your-client-name-agent:latest
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-2.amazonaws.com/your-client-name-agent:latest
```

### Step 3: Deploy Infrastructure

Using the EarlyCore CLI:

```bash
earlycore deploy --target aws
```

Or directly with CloudFormation:

```bash
aws cloudformation deploy \
  --template-file infra/aws/template.yaml \
  --stack-name your-client-name-production \
  --parameter-overrides \
    ClientName=your-client-name \
    Environment=production \
    AgentImageUri=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-2.amazonaws.com/your-client-name-agent:latest \
    EarlycoreApiKey=ec_your_key_here \
    AlertEmail=ops@yourcompany.com \
  --capabilities CAPABILITY_IAM \
  --region eu-west-2
```

Deployment takes 15-20 minutes. Monitor progress:

```bash
aws cloudformation describe-stacks \
  --stack-name your-client-name-production \
  --query "Stacks[0].StackStatus" \
  --output text
```

### Step 4: Get the Endpoint

Once the stack reaches `CREATE_COMPLETE`:

```bash
aws cloudformation describe-stacks \
  --stack-name your-client-name-production \
  --query "Stacks[0].Outputs[?OutputKey=='AgentEndpoint'].OutputValue" \
  --output text
```

### Step 5: Verify

```bash
curl https://your-alb-url.eu-west-2.elb.amazonaws.com/health
```

Expected response:

```json
{"status": "ok", "vectorstore": "pgvector", "llm": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"}
```

### Step 6: Upload Documents

```bash
# Get the S3 bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name your-client-name-production \
  --query "Stacks[0].Outputs[?OutputKey=='DocumentBucketName'].OutputValue" \
  --output text)

# Upload documents
aws s3 cp ./documents/ s3://$BUCKET/documents/ --recursive
```

### Step 7: Monitor

- **EarlyCore Dashboard:** [app.earlycore.dev](https://app.earlycore.dev)
- **CloudWatch Dashboard:** Available in the stack outputs (`DashboardURL`)
- **Logs:** CloudWatch Log Groups `/ecs/your-client-name/agent` and `/ecs/your-client-name/sidecar`

### Common Issues (AWS)

| Symptom                      | Cause                             | Fix                                                                       |
| ---------------------------- | --------------------------------- | ------------------------------------------------------------------------- |
| Stack fails at VPC           | CIDR conflict with existing VPC   | Change `VpcCidr` parameter to a non-overlapping range                     |
| ECS tasks keep restarting    | Missing secrets or bad config     | Check ECS task logs in CloudWatch. Verify Secrets Manager values.         |
| Stack hangs at RDS           | Database creation takes 10-15 min | Wait. RDS is the slowest resource to create.                              |
| Bedrock returns AccessDenied | Model not enabled in your region  | Go to the Bedrock console and enable model access for the required model. |
| ALB returns 503              | ECS tasks not yet healthy         | Wait 2-3 minutes after deployment for health checks to pass.              |

______________________________________________________________________

## Path 3: Docker Production

Run on any server with Docker installed. You manage the server; EarlyCore manages the security monitoring.

### Prerequisites

| Requirement             | Details                                                |
| ----------------------- | ------------------------------------------------------ |
| Remote server           | Ubuntu 22.04+ or Amazon Linux 2023, 2+ vCPU, 4+ GB RAM |
| Docker + Docker Compose | Installed on the server                                |
| Domain name (optional)  | For HTTPS via reverse proxy                            |
| EarlyCore API key       | [Get one here](https://app.earlycore.dev/settings)     |

### Step 1: Set Up the Server

SSH into your server:

```bash
ssh user@your-server-ip
```

Install Docker if not already present:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

### Step 2: Copy Project Files

From your local machine:

```bash
scp -r ./ user@your-server-ip:~/rag-agent/
```

Or clone from your repository:

```bash
git clone https://your-repo-url.git ~/rag-agent
```

### Step 3: Configure Environment

```bash
cd ~/rag-agent
cp .env.example .env
nano .env
```

Set the same values as in Path 1. For production, use strong passwords and consider pointing `VECTORSTORE_URL` at an external managed PostgreSQL instance.

### Step 4: Deploy

```bash
earlycore deploy --target docker
```

Or directly:

```bash
docker compose up -d --build
```

### Step 5: Verify

```bash
curl http://localhost:8443/health
```

### Step 6: Set Up HTTPS (Recommended)

Use a reverse proxy like Caddy or nginx with Let's Encrypt:

```bash
# Example with Caddy
sudo apt install caddy
```

Create `/etc/caddy/Caddyfile`:

```
your-domain.com {
    reverse_proxy localhost:8443
}
```

```bash
sudo systemctl restart caddy
```

Your agent is now accessible at `https://your-domain.com` with automatic TLS.

### Common Issues (Docker Production)

| Symptom                      | Cause                           | Fix                                                                           |
| ---------------------------- | ------------------------------- | ----------------------------------------------------------------------------- |
| Out of memory                | Server has \< 2 GB free RAM     | Increase server RAM or reduce container memory limits in `docker-compose.yml` |
| Containers restart on reboot | Docker not set to start on boot | `sudo systemctl enable docker`                                                |
| Can't pull sidecar image     | No access to `ghcr.io`          | Check firewall rules. Ensure port 443 outbound is open.                       |

______________________________________________________________________

## Next Steps

After deployment:

1. **Ingest your documents** -- Upload PDFs, DOCX, TXT, or MD files
1. **Tune the system prompt** -- Refine `agent/prompts/system.txt` based on test queries
1. **Adjust guardrails** -- Review flagged requests in the EarlyCore dashboard and tune thresholds
1. **Set up alerts** -- Configure Slack or email notifications in `earlycore.yaml`
1. **Read the docs** -- [Configuration Reference](configuration.md) | [Security](security.md) | [Monitoring](monitoring.md)
