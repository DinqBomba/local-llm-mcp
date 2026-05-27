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
- [Ollama](https://ollama.com) (for the LLM)
- [Open WebUI](https://github.com/open-webui/open-webui) (or another MCP-compatible client)

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

## Connecting to Open WebUI

### 5. Add as a Tool Server

In Open WebUI:

1. Go to **Admin Panel > Settings > Integrations > Manage Tool Servers**
2. Click **+** to add a new tool server
3. Set the URL to:

```
http://localhost:8000/mcp
```

> **Important:** Use `/mcp` (Streamable HTTP transport), not `/sse`. The `/sse` endpoint is legacy and not compatible with Open WebUI's MCP client.

4. Save and verify the connection shows as healthy.

### 6. Enable function calling for your model

In Open WebUI:

1. **Admin Panel > Settings > Models > Settings** — enable **Native Function Calling**
2. **Admin Panel > Settings > Models > [your model] > Tools** — checkmark the SearXNG MCP Server

The tools (`web_search`, `web_answer`) will now appear in new chats as available tools.

### 7. Configure the model for tool use (Ollama)

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

### 8. Test it

Start a new chat with the model, enable the SearXNG tool, and ask something:

> What is the weather in Sofia today?

The model should call `web_answer` or `web_search`, receive results, and synthesize a response with linked citations.

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
