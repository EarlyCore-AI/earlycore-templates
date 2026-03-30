# Cost Estimation

Monthly cost breakdown for each deployment option. All prices are estimates based on AWS eu-west-2 (London) pricing as of March 2026. Actual costs vary with usage.

______________________________________________________________________

## Local Development: $0/month

Everything runs on your machine. No cloud costs.

| Component             | How It Runs      | Cost |
| --------------------- | ---------------- | ---- |
| RAG Agent             | Docker container | $0   |
| EarlyCore Sidecar     | Docker container | $0   |
| PostgreSQL + pgvector | Docker container | $0   |
| Redis                 | Docker container | $0   |

**Requirements:** Docker installed, 4 GB free RAM, 2+ CPU cores.

______________________________________________________________________

## AWS Staging: ~$102/month

Minimal AWS footprint for testing and staging environments.

| Service           | Configuration                          | Monthly Cost    |
| ----------------- | -------------------------------------- | --------------- |
| ECS Fargate       | 1 task, 0.5 vCPU, 1 GB RAM             | ~$15            |
| RDS PostgreSQL    | db.t4g.micro, 20 GB GP3, Single-AZ     | ~$15            |
| ElastiCache Redis | cache.t4g.micro, single node           | ~$12            |
| ALB               | 1 ALB + low traffic (~10K requests/mo) | ~$20            |
| NAT Gateway       | 1 gateway + 10 GB data transfer        | ~$35            |
| S3                | 1 GB Standard                          | ~$0.03          |
| CloudWatch        | Logs + metrics                         | ~$5             |
| **Total**         |                                        | **~$102/month** |

______________________________________________________________________

## AWS Production: ~$220/month

Recommended configuration for production workloads serving up to 50 concurrent users.

| Service           | Configuration                                | Monthly Cost    |
| ----------------- | -------------------------------------------- | --------------- |
| ECS Fargate       | 2 tasks, 1 vCPU, 2 GB RAM each               | ~$60            |
| RDS PostgreSQL    | db.t4g.small, 50 GB GP3, Multi-AZ            | ~$55            |
| ElastiCache Redis | cache.t4g.micro, 2 nodes                     | ~$24            |
| ALB               | 1 ALB + moderate traffic (~100K requests/mo) | ~$25            |
| NAT Gateway       | 1 gateway + 50 GB data transfer              | ~$45            |
| S3                | 10 GB Standard                               | ~$0.25          |
| CloudWatch        | Logs + metrics + 10 alarms                   | ~$10            |
| Secrets Manager   | 3 secrets                                    | ~$1.20          |
| **Total**         |                                              | **~$220/month** |

______________________________________________________________________

## AWS Enterprise: ~$650/month

High-availability configuration with auto-scaling, dedicated capacity, and full VPC endpoint coverage.

| Service           | Configuration                             | Monthly Cost    |
| ----------------- | ----------------------------------------- | --------------- |
| ECS Fargate       | 4 tasks, 2 vCPU, 4 GB RAM each            | ~$240           |
| RDS PostgreSQL    | db.r6g.large, 100 GB GP3, Multi-AZ        | ~$190           |
| ElastiCache Redis | cache.r6g.large, 2 nodes                  | ~$100           |
| ALB               | 1 ALB + high traffic (~500K requests/mo)  | ~$35            |
| NAT Gateway       | 2 gateways (one per AZ) + data transfer   | ~$70            |
| S3                | 50 GB Standard + lifecycle policies       | ~$1.50          |
| VPC Endpoints     | Bedrock, ECR, Secrets Manager, CloudWatch | ~$58            |
| CloudWatch        | Logs + metrics + alarms + dashboard       | ~$15            |
| Secrets Manager   | 5 secrets                                 | ~$2             |
| KMS               | 1 customer-managed key                    | ~$1             |
| **Total**         |                                           | **~$650/month** |

> **Note:** Enterprise auto-scaling (2-10 tasks) means compute costs vary. The $650 estimate assumes steady-state 4 tasks.

______________________________________________________________________

## LLM API Costs (Variable, Not Included Above)

LLM costs depend on query volume, context length, and model choice. These are billed by the provider, not by EarlyCore.

### Cost per 1,000 Queries

Assumes: average 5 retrieved chunks per query, 512 chars per chunk, ~2,000 input tokens, ~500 output tokens per query.

| Provider    | Model             | Input Cost     | Output Cost     | Total per 1K Queries |
| ----------- | ----------------- | -------------- | --------------- | -------------------- |
| AWS Bedrock | Claude 3.5 Sonnet | $6.00/M tokens | $30.00/M tokens | ~$27.00              |
| AWS Bedrock | Claude 3.5 Haiku  | $1.00/M tokens | $5.00/M tokens  | ~$4.50               |
| OpenAI      | GPT-4o            | $2.50/M tokens | $10.00/M tokens | ~$10.00              |
| OpenAI      | GPT-4o mini       | $0.15/M tokens | $0.60/M tokens  | ~$0.60               |
| Anthropic   | Claude 3.5 Sonnet | $3.00/M tokens | $15.00/M tokens | ~$13.50              |

### Monthly Estimates by Query Volume

| Monthly Queries | Claude 3.5 Sonnet (Bedrock) | GPT-4o  | GPT-4o mini |
| --------------- | --------------------------- | ------- | ----------- |
| 1,000           | ~$27                        | ~$10    | ~$0.60      |
| 10,000          | ~$270                       | ~$100   | ~$6         |
| 50,000          | ~$1,350                     | ~$500   | ~$30        |
| 100,000         | ~$2,700                     | ~$1,000 | ~$60        |

### Embedding Costs

| Provider    | Model                  | Cost per 1M Tokens | Monthly at 10K Queries |
| ----------- | ---------------------- | ------------------ | ---------------------- |
| AWS Bedrock | Titan Embed v2         | $0.02              | ~$0.40                 |
| OpenAI      | text-embedding-3-small | $0.02              | ~$0.40                 |
| Local       | all-MiniLM-L6-v2       | $0 (CPU only)      | $0                     |

______________________________________________________________________

## EarlyCore Platform Cost

EarlyCore monitoring and guardrails are a separate subscription.

| Plan             | Monthly Cost  | Includes                                                                      |
| ---------------- | ------------- | ----------------------------------------------------------------------------- |
| **Starter**      | Contact sales | 1 deployment, basic monitoring, email alerts                                  |
| **Professional** | Contact sales | Multiple deployments, full dashboard, Slack/PagerDuty alerts, monthly reports |
| **Enterprise**   | Contact sales | Custom SLAs, dedicated support, white-label reports, compliance documentation |

Contact [sales@earlycore.dev](mailto:sales@earlycore.dev) for current pricing.

______________________________________________________________________

## Cost Optimisation Tips

### Quick Wins

| Tip                                                          | Savings                     | Effort                       |
| ------------------------------------------------------------ | --------------------------- | ---------------------------- |
| Use S3 Gateway endpoint (free) instead of NAT for S3 traffic | ~$5-20/mo                   | Low (already configured)     |
| Use `GPT-4o mini` or `Claude 3.5 Haiku` for simple queries   | 50-95% LLM cost reduction   | Low (change model in `.env`) |
| Reduce `TOP_K` from 5 to 3                                   | ~20% fewer tokens per query | Low (change in `.env`)       |
| Scale down staging to 1 ECS task                             | ~$30/mo compute savings     | Low                          |

### Medium Effort

| Tip                                | Savings                        | Effort                 |
| ---------------------------------- | ------------------------------ | ---------------------- |
| Add Bedrock VPC endpoint           | ~$15-30/mo NAT savings         | Add to CloudFormation  |
| Use Fargate Spot for staging       | 70% compute discount           | Update task definition |
| Implement response caching (Redis) | Proportional to cache hit rate | Agent code change      |

### Long-Term

| Tip                                      | Savings                | Effort                           |
| ---------------------------------------- | ---------------------- | -------------------------------- |
| RDS Reserved Instance (1-year)           | ~40% database savings  | Commit via AWS console           |
| Use Graviton (ARM) instances for Fargate | ~20% compute savings   | Rebuild image for ARM            |
| Implement semantic caching               | 30-50% fewer LLM calls | Agent code change                |
| Scale to zero outside business hours     | ~65% compute savings   | Auto-scaling + scheduled scaling |

______________________________________________________________________

## Cost Calculator

To estimate your specific costs, use these inputs:

```
Monthly queries:          ___________
Average chunks per query: ___________  (default: 5)
LLM model:               ___________
Deployment tier:          ___________  (staging / production / enterprise)

Infrastructure:     $ _________ /month  (from tables above)
LLM cost:           $ _________ /month  (queries x cost per 1K / 1000)
Embedding cost:     $ _________ /month  (queries x $0.40 per 10K)
EarlyCore platform: $ _________ /month  (contact sales)
                    ─────────────────
Total:              $ _________ /month
```
