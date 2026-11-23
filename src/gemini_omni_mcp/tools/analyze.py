"""Single-shot multimodal analysis for PDFs, images, audio, video, code, and YouTube URLs."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from google.genai import types

from gemini_omni_mcp.client import (
    build_thinking_config,
    generate_content_with_retry,
    get_client,
)
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.media import guess_mime, load_media_part

YOUTUBE_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})

_TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".sql",
    ".sh",
    ".log",
    ".ini",
    ".cfg",
    ".env",
}


def _validate_youtube_url(url: str) -> str:
    """Validate that a URL is an HTTPS/HTTP YouTube link."""
    raw = url.strip()
    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if parsed.scheme not in ("https", "http") or host not in YOUTUBE_HOSTS:
        raise ValueError(
            f"Unsupported YouTube URL {url!r}. Allowed hosts: {sorted(YOUTUBE_HOSTS)}"
        )
    if not parsed.path or parsed.path == "/":
        if not parsed.query:
            raise ValueError(f"YouTube URL missing video path/query: {url!r}")
    return raw


async def gemini_analyze(
    prompt: str,
    input_paths: list[str] = [],
    youtube_urls: list[str] = [],
    model: str = "gemini-4-hydrogen",
    system_instruction: Optional[str] = None,
    thinking_level: Literal["minimal", "low", "medium", "high", "xhigh"] = "high",
    enable_google_search: bool = False,
    enable_code_execution: bool = False,
    response_json_schema: Optional[dict[str, Any]] = None,
    output_file: Optional[str] = None,
) -> dict[str, Any]:
    """Analyze PDFs, images, audio, video, code/CSV/text files, Files API URIs, or YouTube URLs.

    Supports pre-uploaded `files/<id>` references (from `gemini_files`), automatic Files API
    upload for local files > 15 MB, YouTube video URL understanding, Google Search grounding,
    code execution, structured JSON schemas, and direct saving to `output_file`.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        raise ValueError("prompt cannot be empty.")

    validated_youtube = [_validate_youtube_url(u) for u in youtube_urls]
    client = get_client(context=f"gemini_analyze:{model}")

    parts: list[types.Part] = []
    for item in input_paths:
        raw_item = item.strip()
        if not raw_item:
            continue
        if raw_item.startswith("files/"):
            f_obj = await asyncio.to_thread(client.files.get, name=raw_item)
            parts.append(
                types.Part.from_uri(
                    file_uri=getattr(f_obj, "uri", raw_item),
                    mime_type=getattr(f_obj, "mime_type", None),
                )
            )
            continue
        if raw_item.startswith("https://generativelanguage.googleapis.com/"):
            parts.append(types.Part.from_uri(file_uri=raw_item))
            continue

        fpath = resolve_path(raw_item)
        if not fpath.is_file():
            raise FileNotFoundError(f"Input file not found: {fpath}")

        mime = guess_mime(fpath)
        if fpath.suffix.lower() in _TEXT_SUFFIXES or mime.startswith("text/"):
            text_data = fpath.read_text(encoding="utf-8", errors="replace")
            parts.append(types.Part.from_text(text=f"=== FILE: {fpath.name} ===\n{text_data}\n"))
        elif fpath.stat().st_size > 15 * 1024 * 1024:
            uploaded = await asyncio.to_thread(client.files.upload, file=str(fpath))
            while (
                getattr(uploaded, "state", None)
                and getattr(uploaded.state, "name", str(uploaded.state)) == "PROCESSING"
            ):
                await asyncio.sleep(2.0)
                uploaded = await asyncio.to_thread(client.files.get, name=uploaded.name)
            parts.append(
                types.Part.from_uri(
                    file_uri=uploaded.uri,
                    mime_type=getattr(uploaded, "mime_type", None) or mime,
                )
            )
        else:
            parts.append(await asyncio.to_thread(load_media_part, str(fpath), 1536))

    for yt_url in validated_youtube:
        parts.append(types.Part.from_uri(file_uri=yt_url, mime_type="video/mp4"))

    parts.append(types.Part.from_text(text=clean_prompt))

    cfg_kwargs: dict[str, Any] = {}
    thinking_cfg = build_thinking_config(model, thinking_level)
    if thinking_cfg is not None:
        cfg_kwargs["thinking_config"] = thinking_cfg
    if system_instruction and system_instruction.strip():
        cfg_kwargs["system_instruction"] = system_instruction.strip()

    if not response_json_schema:
        tools_list: list[types.Tool] = []
        if enable_code_execution:
            tools_list.append(types.Tool(code_execution=types.ToolCodeExecution()))
        if enable_google_search:
            tools_list.append(types.Tool(google_search=types.GoogleSearch()))
        if tools_list:
            cfg_kwargs["tools"] = tools_list
    else:
        cfg_kwargs["response_mime_type"] = "application/json"
        cfg_kwargs["response_json_schema"] = response_json_schema

    config = types.GenerateContentConfig(**cfg_kwargs)
    response = await asyncio.to_thread(
        generate_content_with_retry,
        client,
        model,
        parts,
        config,
        False,
        "gemini_analyze",
    )

    output_text = (getattr(response, "text", None) or "").strip()
    saved_out: Optional[str] = None
    if output_file and output_text:
        out_p = resolve_path(output_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output_text, encoding="utf-8")
        saved_out = str(out_p)

    return {
        "status": "success",
        "model": model,
        "inputs_count": len(input_paths),
        "youtube_count": len(validated_youtube),
        "output_file": saved_out,
        "text": output_text,
    }


def register(mcp: Any) -> None:
    """Register single-shot multimodal analysis tools on the MCP server instance."""
    mcp.tool()(gemini_analyze)
