"""Live Gemini API documentation search and Markdown/chunk fetcher (`gemini-api-docs-mcp.dev`)."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional
from urllib.parse import urlparse, urlunparse

import httpx

DOCS_MCP_URL = "https://gemini-api-docs-mcp.dev"
LLMS_TXT_URL = "https://aistudio.google.com/llms.txt"
ALLOWED_DOC_HOSTS = frozenset({"aistudio.google.com", "ai.google.dev", "raw.githubusercontent.com"})


def _parse_mcp_sse_json(raw_text: str) -> dict[str, Any]:
    """Parse Streamable HTTP SSE (`event: message\\ndata: {...}`) or plain JSON MCP responses."""
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("Empty response from docs MCP server.")

    if stripped.startswith("{"):
        return json.loads(stripped)

    last_payload: Optional[dict[str, Any]] = None
    for line in stripped.splitlines():
        line_s = line.strip()
        if not line_s.startswith("data:"):
            continue
        data_part = line_s[5:].strip()
        if not data_part or data_part == "[DONE]":
            continue
        try:
            obj = json.loads(data_part)
            if isinstance(obj, dict):
                last_payload = obj
                if "result" in obj or "error" in obj:
                    return obj
        except json.JSONDecodeError:
            continue

    if last_payload is not None:
        return last_payload
    raise ValueError(f"Could not parse MCP response payload: {stripped[:200]}")


def _normalize_doc_url(slug_or_url: str) -> str:
    """Normalize a doc slug or URL to an allowlisted HTTPS Markdown/text endpoint."""
    raw = slug_or_url.strip()
    if not raw:
        raise ValueError("slug_or_url cannot be empty.")

    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        if parsed.scheme != "https" or host not in ALLOWED_DOC_HOSTS:
            raise ValueError(
                f"Disallowed doc host or scheme: {raw!r}. "
                f"Allowed HTTPS hosts: {sorted(ALLOWED_DOC_HOSTS)}"
            )
        path = parsed.path or "/"
        if host in ("aistudio.google.com", "ai.google.dev") and not path.endswith((".md", ".txt")):
            path = path.rstrip("/") + ".md"
        return urlunparse(("https", host, path, parsed.params, parsed.query, ""))

    slug = raw.lstrip("/")
    if slug == "llms.txt":
        return LLMS_TXT_URL

    query = ""
    if "?" in slug:
        slug, query = slug.split("?", 1)

    if slug.startswith(("docs/", "api-reference/")):
        path = f"/{slug}"
    else:
        path = f"/docs/{slug}"

    if not path.endswith((".md", ".txt")):
        path = path.rstrip("/") + ".md"

    return urlunparse(("https", "aistudio.google.com", path, "", query, ""))


def _search_llms_txt_fallback(llms_text: str, query: str, limit: int) -> list[dict[str, Any]]:
    """Keyword-rank markdown entries inside `llms.txt` when the remote MCP is unreachable."""
    terms = [t for t in re.split(r"[\s._/+-]+", query.lower()) if len(t) >= 2]
    if not terms:
        terms = [query.lower().strip()]

    scored: list[tuple[int, dict[str, Any]]] = []
    link_re = re.compile(r"^-?\s*\[([^\]]+)\]\((https?://[^)]+)\)\s*:?\s*(.*)$")

    for line in llms_text.splitlines():
        m = link_re.match(line.strip())
        if not m:
            continue
        title, url, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        hay = f"{title} {url} {desc}".lower()
        score = sum(hay.count(t) for t in terms)
        if score > 0:
            scored.append(
                (
                    score,
                    {
                        "title": title,
                        "url": url,
                        "snippet": desc,
                        "score": score,
                    },
                )
            )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[: max(1, min(int(limit), 50))]]


async def _call_remote_docs_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool on `https://gemini-api-docs-mcp.dev` over stateless Streamable HTTP."""
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        resp = await http.post(DOCS_MCP_URL, json=rpc_payload, headers=headers)
        resp.raise_for_status()
        parsed = _parse_mcp_sse_json(resp.text)

    if "error" in parsed:
        raise RuntimeError(f"Docs MCP error: {parsed['error']}")

    result = parsed.get("result") or {}
    if result.get("isError"):
        err_texts = [
            c.get("text", "")
            for c in result.get("content", [])
            if isinstance(c, dict)
        ]
        raise RuntimeError(" ".join(err_texts) or "Docs MCP tool returned isError=True")

    return result


async def gemini_docs(
    action: Literal["search", "fetch"] = "search",
    query: Optional[str] = None,
    limit: int = 10,
    scope: Optional[
        Literal["api-reference", "deprecated", "guide", "migration", "sdk", "type-reference"]
    ] = None,
    source: Optional[
        Literal[
            "dotnet-sdk",
            "gemini-api-guides",
            "gemini-api-reference",
            "gemini-api-schema",
            "go-sdk",
            "java-sdk",
            "javascript-sdk",
            "python-sdk",
        ]
    ] = None,
    language: Optional[Literal["dotnet", "go", "java", "javascript", "python"]] = None,
    api: Optional[Literal["interactions", "generate-content"]] = None,
    cursor: Optional[str] = None,
    chunk_id: Optional[str] = None,
    slug_or_url: Optional[str] = None,
    context: int = 0,
    max_chars: int = 24000,
) -> dict[str, Any]:
    """Search or fetch live official Google Gemini API & SDK documentation ($0.00 cost).

    - `action="search"`: Search live docs at `gemini-api-docs-mcp.dev` using `query` (automatically
      falls back to `https://aistudio.google.com/llms.txt` keyword search if unreachable).
    - `action="fetch"`: Fetch a specific chunk by `chunk_id` OR full Markdown page by `slug_or_url`
      (e.g. `"latest-model"`, `"pricing"`, `"llms.txt"`, or an HTTPS URL on allowlisted hosts).
    """
    if action == "search":
        if not query or not query.strip():
            raise ValueError("query is required for action='search'.")
        clean_query = query.strip()

        safe_limit = max(1, min(int(limit), 50))
        args: dict[str, Any] = {"query": clean_query, "limit": safe_limit}
        if scope:
            args["scope"] = scope
        if source:
            args["source"] = source
        if language:
            args["language"] = language
        if api:
            args["api"] = api
        if cursor:
            args["cursor"] = cursor

        try:
            result = await _call_remote_docs_mcp("gemini_search_docs", args)
            content_blocks = result.get("content") or []
            raw_text = ""
            for blk in content_blocks:
                if isinstance(blk, dict) and blk.get("text"):
                    raw_text = blk["text"]
                    break
            if raw_text:
                try:
                    inner = json.loads(raw_text)
                    if isinstance(inner, dict):
                        return {
                            "status": "ok",
                            "source": DOCS_MCP_URL,
                            "query": clean_query,
                            "hits": inner.get("hits", []),
                            "next_cursor": inner.get("next_cursor"),
                        }
                except json.JSONDecodeError:
                    return {
                        "status": "ok",
                        "source": DOCS_MCP_URL,
                        "query": clean_query,
                        "raw_text": raw_text,
                    }
            return {"status": "ok", "source": DOCS_MCP_URL, "query": clean_query, "result": result}
        except Exception as exc:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
                llms_resp = await http.get(LLMS_TXT_URL)
                llms_resp.raise_for_status()
                hits = _search_llms_txt_fallback(llms_resp.text, clean_query, safe_limit)
            return {
                "status": "fallback_llms_txt",
                "source_url": LLMS_TXT_URL,
                "fallback_reason": str(exc)[:240],
                "query": clean_query,
                "hits": hits,
            }

    # action == "fetch"
    has_chunk = bool(chunk_id and chunk_id.strip())
    has_slug = bool(slug_or_url and slug_or_url.strip())
    if has_chunk == has_slug:
        raise ValueError("Provide exactly one of `chunk_id` or `slug_or_url` for action='fetch'.")

    limit_chars = max(500, int(max_chars))

    if has_chunk:
        clean_chunk = str(chunk_id).strip()
        result = await _call_remote_docs_mcp(
            "gemini_get_doc",
            {"chunk_id": clean_chunk, "context": max(0, min(5, int(context)))},
        )
        chunks = [
            blk.get("text", "")
            for blk in (result.get("content") or [])
            if isinstance(blk, dict) and blk.get("text")
        ]
        full_text = "\n\n".join(chunks)
        return {
            "status": "ok",
            "source": DOCS_MCP_URL,
            "chunk_id": clean_chunk,
            "total_chars": len(full_text),
            "truncated": len(full_text) > limit_chars,
            "content": full_text[:limit_chars],
        }

    target_url = _normalize_doc_url(str(slug_or_url))
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        resp = await http.get(target_url)
        resp.raise_for_status()
        final_url = str(getattr(resp, "url", "") or target_url)
        if final_url and "://" in final_url:
            parsed_final = urlparse(final_url)
            if (
                parsed_final.scheme != "https"
                or parsed_final.netloc.lower() not in ALLOWED_DOC_HOSTS
            ):
                raise ValueError(
                    f"Redirected to disallowed doc host: {final_url!r}."
                )
        full_text = resp.text

    return {
        "status": "ok",
        "url": target_url,
        "total_chars": len(full_text),
        "truncated": len(full_text) > limit_chars,
        "content": full_text[:limit_chars],
    }


def register(mcp: Any) -> None:
    """Register unified live Gemini documentation tool on the MCP server instance."""
    mcp.tool()(gemini_docs)
