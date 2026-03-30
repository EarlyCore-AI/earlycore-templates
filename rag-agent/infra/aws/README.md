# EarlyCore RAG Agent - AWS Infrastructure

CloudFormation templates for deploying the EarlyCore RAG agent on AWS with ECS Fargate, RDS PostgreSQL (pgvector), ElastiCache Redis, and S3 document storage.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- An AWS account with permissions to create VPCs, ECS clusters, RDS instances, S3 buckets, IAM roles
- A container image for the RAG agent pushed to ECR (or accessible registry)
- An EarlyCore API key

## Architecture

```
                    Internet
                       |
                  [Route 53]
                       |
              +--------+--------+
              |   ALB (HTTPS)   |   Public Subnets (2 AZs)
              +--------+--------+
                       |
         +-------------+-------------+
         |                           |
  +------+------+            +------+------+
  | ECS Fargate |            | ECS Fargate |   Private Subnets (2 AZs)
  | +--------+  |            | +--------+  |
  | |sidecar |  |            | |sidecar |  |
  | +---+----+  |            | +---+----+  |
  |     |       |            |     |       |
  | +---+----+  |            | +---+----+  |
  | | agent  |  |            | | agent  |  |
  | +--------+  |            | +--------+  |
  +------+------+            +------+------+
         |                           |
    +----+----+----+----+----+----+--+
    |         |         |         |
+---+---+ +---+---+ +---+---+ +---+---+
|  RDS  | | Redis | |  S3   | |Bedrock|   Isolated Subnets / VPC Endpoints
+-------+ +-------+ +-------+ +-------+
```

## Files

| File              | Description                                                                         |
| ----------------- | ----------------------------------------------------------------------------------- |
| `template.yaml`   | Master stack that orchestrates all nested stacks                                    |
| `vpc.yaml`        | VPC, subnets (public/private/isolated), NAT Gateway, security groups, VPC endpoints |
| `ecs.yaml`        | ECS Fargate cluster, task definition (agent + sidecar), ALB, auto-scaling           |
| `database.yaml`   | RDS PostgreSQL 16 with pgvector, encrypted, Multi-AZ in production                  |
| `cache.yaml`      | ElastiCache Redis 7.x with encryption at rest and in transit                        |
| `storage.yaml`    | S3 bucket with KMS encryption, versioning, lifecycle rules                          |
| `iam.yaml`        | IAM roles and least-privilege policies for ECS tasks                                |
| `monitoring.yaml` | CloudWatch log groups, dashboard, alarms, SNS alerts                                |
| `secrets.yaml`    | Secrets Manager for API keys and configuration                                      |
| `parameters.json` | Default parameter values (edit before deploying)                                    |

## Deployment

### 1. Upload nested templates to S3

```bash
BUCKET_NAME="earlycore-cfn-templates-$(aws sts get-caller-identity --query Account --output text)"
aws s3 mb s3://$BUCKET_NAME

aws s3 sync . s3://$BUCKET_NAME/rag-agent/ \
  --exclude "*.json" \
  --exclude "*.md" \
  --include "*.yaml"
```

### 2. Edit parameters

```bash
cp parameters.json my-parameters.json
# Edit my-parameters.json with your values:
# - ClientName: your client identifier
# - AgentImageUri: your ECR image URI
# - EarlycoreApiKey: your API key
# - AlertEmail: your alert email
# - TemplateBaseUrl: s3://$BUCKET_NAME/rag-agent
```

Note: Redis auth token is generated and stored automatically in AWS Secrets Manager
as `${ClientName}/${Environment}/redis-auth-token`.

### 3. Deploy the stack

```bash
TEMPLATE_URL="https://$BUCKET_NAME.s3.amazonaws.com/rag-agent/template.yaml"

aws cloudformation create-stack \
  --stack-name earlycore-rag-my-company \
  --template-url $TEMPLATE_URL \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --tags \
    Key=ManagedBy,Value=earlycore \
    Key=Project,Value=rag-agent

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name earlycore-rag-my-company
```

### 4. Post-deployment

After the stack is created, update the agent config secret with real values:

```bash
CLIENT_NAME="my-company"
ENVIRONMENT="staging"

# Get the RDS endpoint and credentials
DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name earlycore-rag-$CLIENT_NAME \
  --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" \
  --output text)

# Update the agent config secret
aws secretsmanager update-secret \
  --secret-id "$CLIENT_NAME/$ENVIRONMENT/agent-config" \
  --secret-string "{
    \"vectorstore_url\": \"postgresql://earlycore_admin@$DB_ENDPOINT:5432/earlycore\",
    \"llm_api_key\": \"your-llm-api-key-if-not-bedrock\"
  }"
```

Initialize the pgvector extension on the database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1024),
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

## Updating

Always use change sets for production updates:

```bash
aws cloudformation create-change-set \
  --stack-name earlycore-rag-my-company \
  --change-set-name update-$(date +%Y%m%d-%H%M%S) \
  --template-url $TEMPLATE_URL \
  --parameters file://my-parameters.json \
  --capabilities CAPABILITY_NAMED_IAM

# Review the change set, then execute
aws cloudformation execute-change-set \
  --change-set-name update-YYYYMMDD-HHMMSS \
  --stack-name earlycore-rag-my-company
```

## Cost Estimation

Monthly cost estimates (us-east-1, on-demand pricing):

| Component                             | Staging      | Production      |
| ------------------------------------- | ------------ | --------------- |
| ECS Fargate (2 tasks, 0.5 vCPU, 1 GB) | ~$30         | ~$60 (4 tasks)  |
| ALB                                   | ~$22         | ~$22            |
| NAT Gateway (1 AZ)                    | ~$32         | ~$64 (2 AZs)    |
| RDS db.t4g.small (Single-AZ)          | ~$29         | ~$58 (Multi-AZ) |
| ElastiCache cache.t4g.micro (1 node)  | ~$12         | ~$24 (2 nodes)  |
| S3 (10 GB)                            | ~$1          | ~$1             |
| CloudWatch                            | ~$5          | ~$10            |
| VPC Endpoints (Bedrock, SM, CW Logs)  | ~$44         | ~$44            |
| Secrets Manager (3 secrets)           | ~$2          | ~$2             |
| **Total**                             | **~$177/mo** | **~$285/mo**    |

Bedrock model costs are usage-based and not included above. Typical RAG query costs $0.003-$0.015 per query depending on model and context size.

## Cleanup

To delete the stack (data in RDS and S3 is retained by deletion policy):

```bash
# Disable deletion protection on ALB first
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn $(aws cloudformation describe-stack-resource \
    --stack-name earlycore-rag-my-company \
    --logical-resource-id ECSStack \
    --query "StackResourceDetail.PhysicalResourceId" --output text) \
  --attributes Key=deletion_protection.enabled,Value=false

# Disable deletion protection on RDS
aws rds modify-db-instance \
  --db-instance-identifier my-company-staging-postgres \
  --no-deletion-protection

# Delete the stack
aws cloudformation delete-stack \
  --stack-name earlycore-rag-my-company

# Note: S3 bucket and RDS snapshot are retained after deletion.
# Delete them manually when no longer needed.
```

## Troubleshooting

| Issue                                | Resolution                                                                                                                                           |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Stack creation fails on VPC endpoint | Verify the Bedrock runtime endpoint is available in your region. Remove the BedrockEndpoint resource if not using Bedrock.                           |
| ECS tasks fail to start              | Check CloudWatch logs at `/ecs/{client}/agent` and `/ecs/{client}/sidecar`. Verify the container image URI is correct and accessible.                |
| RDS connection refused               | Ensure the ECS security group can reach the RDS security group on port 5432. Check that the database endpoint in the agent config secret is correct. |
| ALB returns 502                      | The ECS tasks may not be healthy yet. Check the target group health in the EC2 console. Verify the health check path `/health` returns 200.          |
| HTTPS listener error                 | The HTTPS listener requires an ACM certificate ARN. Add the `CertificateArn` property to the `HTTPSListener` resource in `ecs.yaml`.                 |
| Auto-scaling not working             | Verify the service-linked role for Application Auto Scaling exists. Check CloudWatch metrics for the ECS service.                                    |
