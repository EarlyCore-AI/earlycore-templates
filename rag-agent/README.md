# {{ client_name }} -- Secure AI Agent

Built with [EarlyCore](https://earlycore.dev). Security monitoring baked in.

## Quick Start

1. Copy `.env.example` to `.env` and add your API keys
1. Edit `agent/prompts/system.txt` with your agent's instructions
1. Run: `earlycore deploy --dev`

Your agent is now running at `http://localhost:8443` with:

- Prompt injection detection
- PII redaction
- Groundedness checking
- Real-time monitoring via EarlyCore

## Files You'll Edit

| File                       | What It Does                                                   |
| -------------------------- | -------------------------------------------------------------- |
| `agent/prompts/system.txt` | Your agent's personality and instructions                      |
| `agent/rag/pipeline.py`    | Your RAG pipeline (add your Haystack/LangChain code)           |
| `agent/app.py`             | FastAPI server with endpoints (`/query`, `/ingest`, `/health`) |
| `.env`                     | API keys and configuration                                     |
| `earlycore.yaml`           | Security guardrail settings                                    |

## Files You Won't Touch

| File                 | What It Does                   |
| -------------------- | ------------------------------ |
| `docker-compose.yml` | Runs agent + EarlyCore sidecar |
| `agent/Dockerfile`   | Builds the agent container     |

## Documentation

See `docs/setup-guide.md` for the full step-by-step walkthrough.
