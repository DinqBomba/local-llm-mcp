# SearXNG MCP Server

Exposes [SearXNG](https://github.com/searxng/searxng) web search as MCP tools, running entirely via Docker Compose. Built with FastMCP.

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

## Output Formats

Results are deduplicated by URL, relevance-scored (query match in title, Wikipedia/Github boost), then truncated to `limit`. HTML tags are stripped from all snippets.

### `web_search`

```json
{
  "query": "linux kernel",
  "results": [
    {
      "title": "Linux kernel - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Linux_kernel",
      "snippet": "The Linux kernel is a free and open-source..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `query` | `string` | The original search query |
| `results` | `array` | Ordered list of results (best matches first) |
| `results[].title` | `string` | Page title |
| `results[].url` | `string` | Result URL |
| `results[].snippet` | `string` | Short excerpt from the page (HTML-stripped) |

### `web_answer`

```json
{
  "query": "what is rust programming",
  "results": [
    {
      "id": 1,
      "title": "Rust (programming language) - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Rust_(programming_language)",
      "snippet": "Rust is a multi-paradigm, general-purpose programming language..."
    }
  ],
  "instructions": "Use results to answer with citations [1]-[n]."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `query` | `string` | The original search query |
| `results` | `array` | Ordered list of numbered results |
| `results[].id` | `integer` | Citation number (`1`–`n`) for inline referencing |
| `results[].title` | `string` | Page title |
| `results[].url` | `string` | Result URL |
| `results[].snippet` | `string` | Short excerpt from the page (HTML-stripped) |
| `instructions` | `string` | Hardcoded hint: `"Use results to answer with citations [1]-[n]."` |

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose support
- An MCP-compatible client (see [Connecting to Clients](#connecting-to-clients))

## Setup

### 1. Configure environment

```bash
cd searxng/
cp ../.env.example .env
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
| `searxng-mcp` | `8000` | MCP server (Streamable HTTP transport) |

### 4. Verify

```bash
curl -X POST http://localhost:8000/mcp
```

Or run the included test script (requires a venv with `fastmcp` installed):

```bash
python -m venv .venv && source .venv/bin/activate
pip install fastmcp httpx
python test_mcp.py
```

Expected output:

```
Available tools:
  - web_search: Search the web using SearXNG. Returns a list of results with title, url, and snippet. ...
  - web_answer: Search the web and return structured results for answering questions. ...

Search result:
CallToolResult(content=[TextContent(type='text', text='{"query":"linux kernel","results":[...]}', ...)])
```

## Connecting to Clients

The MCP server listens on `http://localhost:8000/mcp` using the Streamable HTTP transport. FastMCP also exposes a legacy SSE endpoint at `http://localhost:8000/sse` for clients that require it.

### Open WebUI (local Ollama)

#### Add as a Tool Server

In Open WebUI:

1. Go to **Admin Panel > Settings > Integrations > Manage Tool Servers**
2. Click **+** to add a new tool server
3. Set the URL to:

```
http://localhost:8000/mcp
```

> **Important:** Use `/mcp` (Streamable HTTP transport), not `/sse`. The `/sse` endpoint is legacy and not compatible with Open WebUI's MCP client.

4. Save and verify the connection shows as healthy.

#### Enable function calling for your model

In Open WebUI:

1. **Admin Panel > Settings > Models > Settings** — enable **Native Function Calling**
2. **Admin Panel > Settings > Models > [your model] > Tools** — checkmark the SearXNG MCP Server

The tools (`web_search`, `web_answer`) will now appear in new chats as available tools.

#### Configure the model for tool use (Ollama)

Models need a large enough context window to hold tool results and conversation history. Create a custom Modelfile:

```bash
ollama show gemma4:26b --modelfile > gemma4-assistant.Modelfile
```

Edit it to customize your parameters. I have set it up like this:

```
FROM gemma4:26b

PARAMETER num_ctx 8192
PARAMETER temperature 0.6
PARAMETER top_k 40
PARAMETER top_p 0.9
PARAMETER min_p 0.05
PARAMETER repeat_penalty 1.1
PARAMETER num_gpu 999
PARAMETER num_thread 8

SYSTEM """You are a helpful, accurate, and concise assistant. When tools are available, use them to find information before answering. Always prefer MCP server tools over built-in tools when both are available. After receiving tool results, always synthesize them into a clear, direct answer for the user. Do not ignore tool results or ask unrelated questions.

When citing sources, use markdown links with the source URL. For example: [1](https://example.com) instead of bare [1]. Always link citations to their source URLs from the tool results."""
```

The system prompt can be very important for properly finding and using tools exposed by the MCP server depending on your configuration.

Key parameters explained:

| Parameter | Value | Why |
|-----------|-------|-----|
| `num_ctx` | 8192 | Fits tool results + conversation. Lower = faster, higher = more context. |
| `temperature` | 0.6 | More deterministic, reduces hallucination with tool use |
| `top_k` / `top_p` / `min_p` | 40 / 0.9 / 0.05 | Tighter sampling to reduce confusion after tool results |
| `repeat_penalty` | 1.1 | Prevents repetitive tool calls |
| `num_gpu` | 999 | Offloads maximum layers to GPU (remainder goes to RAM) |
| `num_thread` | 8 | Match physical CPU cores for layers on RAM |

Build the model:

```bash
ollama create gemma4-custom -f gemma4-assistant.Modelfile
```

Then in Open WebUI, select `gemma4-custom` as your model.

#### Test it

Start a new chat with the model, enable the SearXNG tool, and ask something:

> What is the weather in Sofia today?

The model should call `web_answer` or `web_search`, receive results, and synthesize a response with linked citations.

### Claude Desktop (Anthropic)

Claude Desktop supports local MCP servers via its config file. The server runs entirely on your machine — no data is sent to Anthropic beyond what Claude normally processes.

1. Open (or create) the Claude Desktop config:

| OS | Path |
|----|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

2. Add the SearXNG MCP server:

```json
{
  "mcpServers": {
    "searxng": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

3. Restart Claude Desktop. The tools will appear as available in new chats.

> **Note:** Claude Desktop uses the Streamable HTTP transport (`/mcp`). If your version requires SSE, use `"url": "http://localhost:8000/sse"` instead.

### Cursor

Cursor supports MCP servers in project or global settings.

1. Open **Settings > MCP**
2. Click **Add new MCP server**
3. Configure:

| Field | Value |
|-------|-------|
| Name | `searxng` |
| Type | `streamable-http` |
| URL | `http://localhost:8000/mcp` |

Or add it directly to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project):

```json
{
  "mcpServers": {
    "searxng": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

The `web_search` and `web_answer` tools will be available in Cursor's agent mode.

### VS Code (GitHub Copilot, Cline, Continue)

#### GitHub Copilot

In your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "searxng": {
        "url": "http://localhost:8000/mcp"
      }
    }
  }
}
```

Open the Copilot Chat panel, switch to **Agent** mode, and the tools will appear.

#### Cline

1. Open the Cline sidebar
2. Click the **MCP Servers** icon
3. Click **Add MCP Server**
4. Enter the URL: `http://localhost:8000/mcp`

#### Continue

In `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "http",
          "url": "http://localhost:8000/mcp"
        }
      }
    ]
  }
}
```

### Kilo

In your project's `kilo.json` or global config:

```json
{
  "mcps": {
    "searxng": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Cloud-hosted LLMs

> **TODO:** Add instructions for exposing the local MCP server to cloud providers (e.g. Claude API, OpenAI, Gemini) via a reverse proxy or tunnel. Cloud-based LLMs cannot reach `localhost` directly — the MCP server must be exposed publicly (e.g. Cloudflare Tunnel, ngrok, nginx with TLS) and secured with authentication.

## Troubleshooting

### "Failed to connect to MCP server"

- Ensure the URL ends in `/mcp`, not `/sse`
- Check the container is running: `docker ps | grep searxng-mcp`
- Check logs: `docker logs searxng-mcp`

### Model ignores tool results or hallucinates

- Increase `num_ctx` (try `16384` if you have enough VRAM)
- Lower `temperature` (try `0.4`)
- Verify the model's system prompt instructs it to use MCP tools

### Model is slow

- Reduce `num_ctx` — the KV cache competes with model weights for VRAM
- Use a smaller quantization (e.g. `gemma4:26b-q4_K_M`)
- Check GPU utilization: `watch -n1 rocm-smi` (AMD) or `nvidia-smi` (NVIDIA)

### Wrong tools appear (e.g. `list_searches` instead of `web_search`)

- Those are Open WebUI built-in tools, not from this MCP server
- Verify the SearXNG tool server is connected in Admin Panel > Integrations
- Run `test_mcp.py` to confirm the server exposes `web_search` and `web_answer`
- If it still struggles to find the correct tools refine your system prompt
