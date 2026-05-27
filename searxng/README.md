# SearXNG MCP Server

Exposes [SearXNG](https://github.com/searxng/searxng) web search as MCP tools, running entirely via Docker Compose.

## Tools

| Tool | Description |
|------|-------------|
| `web_search` | Returns a list of results with title, url, and snippet |
| `web_answer` | Returns numbered results for cited answering (`[1]`, `[2]`, etc.) |

Both tools accept these optional parameters:

- `categories` — general, news, images, videos, it, science, files, music, map
- `language` — language code (e.g. `en`, `de`)
- `time_range` — `day`, `week`, `month`, `year`
- `limit` — max results to return (default 5, max 50)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose support

## Setup

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` to set the SearXNG version, host bind address, and port. Defaults:

| Variable | Default |
|----------|---------|
| `SEARXNG_VERSION` | `latest` |
| `SEARXNG_HOST` | `0.0.0.0` |
| `SEARXNG_PORT` | `9090` |

### 2. Create SearXNG config

The `core-config/` directory is mounted into the SearXNG container at `/etc/searxng/`. At minimum you need a `settings.yml` that enables JSON format:

```yaml
use_default_settings: true

search:
  formats:
    - html
    - json

server:
  secret_key: "generate-a-random-secret-here"
```

See the [SearXNG docs](https://docs.searxng.org/admin/settings/) for all available options.

### 3. Start the stack

```bash
docker compose up -d --build
```

This starts three containers:

| Container | Port | Purpose |
|-----------|------|---------|
| `searxng-core` | `9090` | SearXNG search engine |
| `searxng-valkey` | — | Redis-compatible cache for SearXNG |
| `searxng-mcp` | `8000` | MCP server (SSE transport) |

### 4. Verify

```bash
curl http://localhost:8000/sse
```

Or run the included test script (requires a venv with `fastmcp` installed):

```bash
python test_mcp.py
```

## Connecting to an LLM client

Point your MCP client at:

```
http://localhost:8000/sse
```

The server uses SSE transport on port 8000.
