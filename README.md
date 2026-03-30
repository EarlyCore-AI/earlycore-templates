# EarlyCore CLI Templates

Versioned template registry for the [EarlyCore CLI](https://pypi.org/project/earlycore/).

Templates are downloaded on demand when you run `earlycore init`. They are verified against SHA-256 checksums before extraction.

## Available Templates

| Template | Description |
|----------|-------------|
| `rag-agent` | Secure RAG agent with Presidio PII detection, prompt injection guardrails, and AWS CloudFormation infrastructure |

## How it works

```
pip install earlycore
earlycore init --client my-company
```

The CLI:
1. Fetches `manifest.json` from this repo
2. Downloads the template archive from GitHub Releases
3. Verifies SHA-256 checksum
4. Extracts to `~/.earlycore/templates/` (cached for future use)

## Verify a download

```bash
curl -sL https://github.com/EarlyCore-AI/earlycore-templates/releases/download/v0.1.0/rag-agent-v0.1.0.tar.gz | shasum -a 256
# Compare against the checksum in manifest.json
```

## Security

- All downloads over HTTPS (GitHub CDN backed by Fastly)
- SHA-256 integrity verification before extraction
- Tar extraction rejects path traversal and symlinks
- No authentication required (public repo)
