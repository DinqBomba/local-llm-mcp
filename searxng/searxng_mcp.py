import os
import re
import logging

import httpx
from fastmcp import FastMCP

logger = logging.getLogger("searxng-mcp")
logging.basicConfig(level=logging.INFO)

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng-core:9090")
MAX_LIMIT = 50

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30)
    return _client


mcp = FastMCP("SearXNG Search")


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<.*?>", "", text).strip()


def _score_result(r: dict, query: str) -> int:
    title = (r.get("title") or "").lower()
    url = (r.get("url") or "").lower()
    q = query.lower()

    score = 0
    if q in title:
        score += 3
    if "wikipedia" in url:
        score += 2
    if "github" in url:
        score += 1
    return score


def _dedupe(results: list[dict]) -> list[dict]:
    seen: set[str] = set()
    cleaned: list[dict] = []
    for r in results:
        url = r.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        cleaned.append(r)
    return cleaned


async def _search(
    query: str,
    *,
    limit: int = 5,
    categories: str | None = None,
    language: str | None = None,
    time_range: str | None = None,
    pageno: int = 1,
) -> dict:
    limit = max(1, min(limit, MAX_LIMIT))
    pageno = max(1, pageno)

    params: dict = {"q": query, "format": "json", "pageno": pageno}
    if categories:
        params["categories"] = categories
    if language:
        params["language"] = language
    if time_range:
        params["time_range"] = time_range

    try:
        r = await _get_client().get(
            f"{SEARXNG_URL}/search",
            params=params,
            headers={"User-Agent": "MCP-SearXNG"},
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.error("SearXNG returned %s: %s", e.response.status_code, e.response.text[:200])
        raise RuntimeError(f"SearXNG returned {e.response.status_code}") from e
    except httpx.RequestError as e:
        logger.error("SearXNG request failed: %s", e)
        raise RuntimeError(f"SearXNG request failed: {e}") from e


@mcp.tool()
async def web_search(
    query: str,
    limit: int = 5,
    categories: str | None = None,
    language: str | None = None,
    time_range: str | None = None,
) -> dict:
    """Search the web using SearXNG. Returns a list of results with title, url, and snippet.
    Use 'categories' to narrow results: general, news, images, videos, it, science, files, music, map.
    Use 'time_range' for recency: day, week, month, year.
    """
    data = await _search(query, limit=limit, categories=categories, language=language, time_range=time_range)

    results = _dedupe(data.get("results", []))
    results.sort(key=lambda r: _score_result(r, query), reverse=True)
    results = results[:limit]

    return {
        "query": query,
        "results": [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": clean(r.get("content")),
            }
            for r in results
        ],
    }


@mcp.tool()
async def web_answer(
    query: str,
    limit: int = 5,
    categories: str | None = None,
    language: str | None = None,
    time_range: str | None = None,
) -> dict:
    """Search the web and return structured results for answering questions.
    Each result has a numbered id for citation. Cite sources as [1], [2], etc.
    Use 'categories' to narrow results: general, news, images, videos, it, science, files, music, map.
    """
    data = await _search(query, limit=limit, categories=categories, language=language, time_range=time_range)

    results = _dedupe(data.get("results", []))
    results.sort(key=lambda r: _score_result(r, query), reverse=True)
    results = results[:limit]

    return {
        "query": query,
        "results": [
            {
                "id": i,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": clean(r.get("content")),
            }
            for i, r in enumerate(results, 1)
        ],
        "instructions": "Use results to answer with citations [1]-[n].",
    }


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
