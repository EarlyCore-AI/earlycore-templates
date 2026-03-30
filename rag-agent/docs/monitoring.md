# Monitoring Guide

Two monitoring systems work together: **EarlyCore** monitors your agent's AI-specific behaviour (guardrails, groundedness, injection attempts), while **CloudWatch** monitors infrastructure (CPU, memory, errors, logs).

______________________________________________________________________

## What the EarlyCore Sidecar Monitors

The sidecar captures telemetry on every request and sends it to the EarlyCore platform.

| Metric                  | Description                                                             | Updated     |
| ----------------------- | ----------------------------------------------------------------------- | ----------- |
| **Request count**       | Total queries processed                                                 | Per request |
| **Latency breakdown**   | Time spent in: sidecar guardrails, embedding, retrieval, LLM generation | Per request |
| **Injection attempts**  | Detected prompt injection attacks (blocked and allowed)                 | Per request |
| **PII detections**      | Count and type of PII tokens found and redacted                         | Per request |
| **Groundedness score**  | Percentage of response claims supported by retrieved documents          | Per request |
| **Token usage**         | Input and output tokens consumed per LLM call                           | Per request |
| **Error rate**          | Requests that resulted in 4xx/5xx responses                             | Per request |
| **Guardrail decisions** | Block/allow decisions with confidence scores                            | Per request |

### Viewing the EarlyCore Dashboard

1. Go to [app.earlycore.dev](https://app.earlycore.dev).
1. Select your agent from the sidebar.
1. The dashboard shows real-time data across four panels:

| Panel        | What It Shows                                                   |
| ------------ | --------------------------------------------------------------- |
| **Overview** | Request volume, latency percentiles, error rate over time       |
| **Security** | Injection attempts, PII detections, blocked requests            |
| **Quality**  | Groundedness scores, source citation rates, hallucination flags |
| **Usage**    | Token consumption, LLM cost estimates, per-model breakdown      |

______________________________________________________________________

## What CloudWatch Monitors (AWS Only)

The CloudFormation template creates a dashboard and alarms automatically.

### Log Groups

| Log Group                    | Contents                                 | Retention |
| ---------------------------- | ---------------------------------------- | --------- |
| `/ecs/{client-name}/agent`   | Agent application logs (JSON structured) | 30 days   |
| `/ecs/{client-name}/sidecar` | Sidecar security event logs              | 30 days   |

### Useful CloudWatch Insights Queries

**Find all blocked requests in the last hour:**

```
fields @timestamp, @message
| filter @message like /blocked/
| sort @timestamp desc
| limit 50
```

**View latency percentiles:**

```
fields @timestamp, latency_ms
| stats avg(latency_ms) as avg_latency,
        pct(latency_ms, 95) as p95,
        pct(latency_ms, 99) as p99
  by bin(5m)
```

**Find errors:**

```
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 50
```

______________________________________________________________________

## Alert Types

Alerts are classified by severity. Configure alert channels in `earlycore.yaml`.

### P0 -- Critical (Immediate Action Required)

| Alert                          | Trigger                                       | What To Do                                                                           |
| ------------------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Agent down**                 | Health check fails for > 2 minutes            | Check container logs. Restart containers. See [Troubleshooting](troubleshooting.md). |
| **Database unreachable**       | Connection failures for > 1 minute            | Check RDS status in AWS console. Verify security group rules.                        |
| **Sustained injection attack** | > 50 blocked injection attempts in 10 minutes | Review blocked requests in EarlyCore dashboard. Consider IP-level blocking at ALB.   |

### P1 -- High (Action Within 1 Hour)

| Alert                       | Trigger                      | What To Do                                                                                           |
| --------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------- |
| **High error rate**         | > 10 5xx errors in 5 minutes | Check agent logs for stack traces. Common causes: LLM provider down, database connection exhaustion. |
| **CPU sustained > 80%**     | 5 minutes continuous         | Scale up: increase `DesiredCount` or `ContainerCpu`.                                                 |
| **Memory sustained > 85%**  | 5 minutes continuous         | Check for memory leaks. Increase `ContainerMemory`.                                                  |
| **High PII detection rate** | > 100 PII detections/hour    | Review queries in EarlyCore dashboard. May indicate data quality issue in source documents.          |

### P2 -- Medium (Action Within 24 Hours)

| Alert                      | Trigger                            | What To Do                                                           |
| -------------------------- | ---------------------------------- | -------------------------------------------------------------------- |
| **Groundedness declining** | Groundedness score drops below 70% | Review source documents. May need re-ingestion with updated content. |
| **Latency increasing**     | p95 latency > 5 seconds            | Check LLM provider status. Consider caching frequent queries.        |
| **Disk usage > 80%**       | RDS storage utilisation            | Extend storage or clean old data.                                    |

### P3 -- Low (Review Weekly)

| Alert                 | Trigger                             | What To Do                                                     |
| --------------------- | ----------------------------------- | -------------------------------------------------------------- |
| **Token usage spike** | > 2x normal daily token consumption | Review query patterns. May indicate a bot or integration loop. |
| **Unused capacity**   | Average CPU \< 20% for 7 days       | Scale down to save cost.                                       |

______________________________________________________________________

## Setting Up Alert Channels

### Slack

1. Create a Slack webhook at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks).
1. Add it to `earlycore.yaml`:

```yaml
alerts:
  channels:
    - type: slack
      target: https://hooks.slack.com/services/T00/B00/xxxx
```

3. Restart the sidecar: `docker compose restart earlycore-sidecar`

### Email

```yaml
alerts:
  channels:
    - type: email
      target: ops@yourcompany.com
```

### Multiple Channels

```yaml
alerts:
  channels:
    - type: slack
      target: https://hooks.slack.com/services/T00/B00/xxxx
    - type: email
      target: ops@yourcompany.com
    - type: pagerduty
      target: your-pagerduty-integration-key
```

### CloudWatch Alarms (AWS)

CloudWatch alarms are configured automatically during deployment. They send notifications to the `AlertEmail` provided in the CloudFormation parameters.

To change the alert email after deployment:

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:eu-west-2:ACCOUNT:your-client-name-alerts \
  --protocol email \
  --notification-endpoint new-email@yourcompany.com
```

______________________________________________________________________

## Monthly Security Report

EarlyCore generates a monthly security report for each deployment. The report includes:

| Section                   | Contents                                                 |
| ------------------------- | -------------------------------------------------------- |
| **Executive Summary**     | Total requests, blocked threats, uptime percentage       |
| **Threat Overview**       | Injection attempts by category, trend vs. previous month |
| **PII Report**            | Types and volumes of PII detected and redacted           |
| **Quality Metrics**       | Average groundedness score, hallucination rate           |
| **Latency & Performance** | p50, p95, p99 latency; token usage; cost estimate        |
| **Recommendations**       | Suggested guardrail tuning, scaling advice               |

Access reports at [app.earlycore.dev](https://app.earlycore.dev) under your agent's **Reports** tab.

______________________________________________________________________

## Runbooks

### Agent Not Responding

```
1. Check container status
   docker compose ps                    # local
   aws ecs describe-services ...        # AWS

2. Check sidecar logs
   docker compose logs earlycore-sidecar --tail 50

3. Check agent logs
   docker compose logs agent --tail 50

4. If sidecar is down:
   - Verify EARLYCORE_API_KEY is set in .env
   - Restart: docker compose restart earlycore-sidecar

5. If agent is down:
   - Check for Python errors in logs
   - Verify .env has valid LLM credentials
   - Restart: docker compose restart agent
```

### LLM Provider Errors

```
1. Check which provider is configured
   grep LLM_PROVIDER .env

2. For Bedrock:
   - Verify AWS credentials: aws sts get-caller-identity
   - Check model access: aws bedrock list-foundation-models --query "modelSummaries[?modelId=='your-model']"
   - Verify region: model must be available in your configured region

3. For OpenAI:
   - Check API status: https://status.openai.com
   - Verify key: curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

4. For Anthropic:
   - Check API status: https://status.anthropic.com
   - Verify key works with a direct curl call
```

### High Latency

```
1. Check which component is slow
   - EarlyCore dashboard > Latency breakdown

2. If embedding is slow:
   - Consider switching to a faster model
   - For local embeddings: check CPU/memory availability

3. If retrieval is slow:
   - Check vector store connection and query performance
   - Consider adding an HNSW index (pgvector)

4. If LLM generation is slow:
   - Normal for large context windows
   - Consider reducing TOP_K to retrieve fewer documents
   - Consider a faster model (e.g., Haiku instead of Sonnet)
```

### Injection Attack Detected

```
1. Review the blocked request in EarlyCore dashboard
   - Dashboard > Security > Recent Events

2. Determine if it's a false positive
   - If legitimate query was blocked: lower guardrail level to "permissive"
   - If attack: no action needed, the sidecar blocked it

3. For sustained attacks from one IP:
   - Add IP to ALB WAF deny list (AWS)
   - Or add rate limiting in earlycore.yaml

4. Document the incident for the monthly security report
```
