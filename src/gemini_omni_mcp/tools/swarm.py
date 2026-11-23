"""Context caching and high-concurrency async worker swarm tools."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any, Optional

from google.genai import types

from gemini_omni_mcp.client import get_client, is_retryable_exception
from gemini_omni_mcp.config import (
    get_cache_dir,
    get_workspace_root,
    logger,
    resolve_path,
)
from gemini_omni_mcp.media import load_media_part
from gemini_omni_mcp.pricing import enforce_hard_budget_limit, record_api_usage

_CODE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".sql",
    ".sh",
    ".rs",
    ".go",
    ".cpp",
    ".c",
    ".cs",
    ".html",
    ".css",
}


async def gemini_context_cache(
    paths: list[str],
    system_instruction: str,
    model: str = "gemini-4-argon",
    ttl_minutes: int = 180,
) -> dict[str, Any]:
    """Upload files, directories, or reference images to Google Context Cache (up to 95% input discount).

    Also writes a deterministic implicit prefix fallback bundle under `<workspace>/.gemini-omni/cache/`
    if explicit caching is unavailable or below the model's minimum token threshold.
    """
    if not paths:
        raise ValueError("paths list cannot be empty.")

    workspace = get_workspace_root()
    cache_parts: list[types.Part] = []
    loaded_files: list[str] = []
    text_chunks: list[str] = [system_instruction]

    for raw_p in paths:
        p = resolve_path(raw_p)
        if not p.exists():
            logger.warning("Skipping non-existent path in gemini_context_cache: %s", p)
            continue
        if p.is_dir():
            for sub in sorted(p.rglob("*")):
                if sub.is_file() and sub.suffix.lower() in (
                    ".py",
                    ".md",
                    ".json",
                    ".ts",
                    ".tsx",
                    ".js",
                    ".txt",
                    ".yaml",
                    ".yml",
                ):
                    text_data = sub.read_text(encoding="utf-8", errors="replace")
                    rel = sub.relative_to(workspace) if sub.is_relative_to(workspace) else sub.name
                    block = f"=== FILE: {rel} ===\n{text_data}\n"
                    cache_parts.append(types.Part.from_text(text=block))
                    text_chunks.append(block)
                    loaded_files.append(str(sub))
        elif p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            cache_parts.append(load_media_part(str(p), max_dim=1536))
            loaded_files.append(str(p))
        else:
            text_data = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(workspace) if p.is_relative_to(workspace) else p.name
            block = f"=== FILE: {rel} ===\n{text_data}\n"
            cache_parts.append(types.Part.from_text(text=block))
            text_chunks.append(block)
            loaded_files.append(str(p))

    if not cache_parts:
        raise ValueError("No valid files could be loaded from the provided paths.")

    safe_model = re.sub(r"[^a-zA-Z0-9._-]+", "_", model.strip()) or "gemini"
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    imp_bundle_path = cache_dir / f"implicit_cache_{safe_model}.txt"
    imp_bundle_path.write_text("\n\n".join(text_chunks), encoding="utf-8")

    client = get_client(context=f"gemini_context_cache:{model}")
    ttl_str = f"{max(1, int(ttl_minutes)) * 60}s"

    cache_cfg = types.CreateCachedContentConfig(
        contents=[types.Content(role="user", parts=cache_parts)],
        system_instruction=system_instruction,
        ttl=ttl_str,
        display_name=f"gemini-omni-cache-{safe_model}-{int(time.time())}",
    )

    try:
        cache_obj = await asyncio.to_thread(
            client.caches.create,
            model=model,
            config=cache_cfg,
        )
        um = getattr(cache_obj, "usage_metadata", None)
        cached_tok = int(getattr(um, "total_token_count", None) or 0) if um else 0
        cost_entry = record_api_usage(
            tool_name="gemini_context_cache",
            model=model,
            tier="standard",
            cached_tokens=cached_tok,
            cache_storage_hours=max(1, int(ttl_minutes)) / 60.0,
            note=f"Explicit cache created ({len(loaded_files)} files, TTL={ttl_minutes}m)",
        )
        return {
            "status": "cached_explicit",
            "cached_content_name": cache_obj.name,
            "implicit_prefix_bundle": f"implicit:{imp_bundle_path}",
            "model": model,
            "ttl_minutes": ttl_minutes,
            "files_cached_count": len(loaded_files),
            "files_cached": loaded_files,
            "usage_metadata": str(getattr(cache_obj, "usage_metadata", "")),
            "cost_usd": cost_entry["cost_usd"],
        }
    except Exception as exc:
        logger.info("Explicit cache fallback to implicit prefix bundle for %s (%s)", model, exc)
        return {
            "status": "cached_implicit_prefix",
            "cached_content_name": f"implicit:{imp_bundle_path}",
            "model": model,
            "ttl_minutes": ttl_minutes,
            "files_cached_count": len(loaded_files),
            "files_cached": loaded_files,
            "note": f"Using deterministic implicit prefix cache bundle ({imp_bundle_path.name})",
            "cost_usd": 0.0,
        }


async def gemini_async_swarm(
    tasks: list[dict[str, Any]],
    model: str = "gemini-3.8-flash",
    cached_content_name: Optional[str] = None,
    concurrency: int = 20,
    thinking_level: str = "HIGH",
    enable_code_execution: bool = True,
    enable_google_search: bool = False,
    response_json_schema: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """High-concurrency async parallel worker swarm (up to 64 concurrent requests).

    Each item in `tasks` accepts:
      `{"id": str, "prompt": str, "image_paths": list[str] (optional), "output_file": str (optional)}`
    """
    if not tasks:
        raise ValueError("tasks list cannot be empty.")

    sem = asyncio.Semaphore(max(1, min(int(concurrency), 64)))
    client = get_client(context=f"gemini_async_swarm:{model}")

    async def _run_single_worker(idx: int, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("id", f"task_{idx}"))
        prompt_text = str(task.get("prompt", ""))
        img_paths = list(task.get("image_paths") or [])
        out_file_str = task.get("output_file")

        async with sem:
            t0 = time.perf_counter()
            try:
                parts: list[types.Part] = []
                for ip in img_paths:
                    part = await asyncio.to_thread(load_media_part, ip, 1536)
                    parts.append(part)
                parts.append(types.Part.from_text(text=prompt_text))

                cfg_kwargs: dict[str, Any] = {
                    "thinking_config": types.ThinkingConfig(
                        thinking_level=thinking_level.upper()
                    ),
                }
                if cached_content_name and str(cached_content_name).startswith("cachedContents/"):
                    cfg_kwargs["cached_content"] = cached_content_name
                elif cached_content_name and str(cached_content_name).startswith("implicit:"):
                    imp_path = Path(str(cached_content_name).removeprefix("implicit:"))
                    if imp_path.is_file():
                        cfg_kwargs["system_instruction"] = imp_path.read_text(encoding="utf-8")

                if not response_json_schema and "cached_content" not in cfg_kwargs:
                    tools_list: list[types.Tool] = []
                    if enable_code_execution:
                        tools_list.append(types.Tool(code_execution=types.ToolCodeExecution()))
                    if enable_google_search:
                        tools_list.append(types.Tool(google_search=types.GoogleSearch()))
                    if tools_list:
                        cfg_kwargs["tools"] = tools_list

                if response_json_schema:
                    cfg_kwargs["response_mime_type"] = "application/json"
                    cfg_kwargs["response_json_schema"] = response_json_schema

                config = types.GenerateContentConfig(**cfg_kwargs)

                resp = None
                for attempt in range(1, 5):
                    try:
                        enforce_hard_budget_limit(context=f"gemini_async_swarm[{task_id}]")
                        resp = await client.aio.models.generate_content(
                            model=model,
                            contents=parts,
                            config=config,
                        )
                        break
                    except Exception as exc:
                        if is_retryable_exception(exc) and attempt < 4:
                            await asyncio.sleep(1.5**attempt)
                            continue
                        raise

                worker_cost_entry = await asyncio.to_thread(
                    record_api_usage,
                    "gemini_async_swarm",
                    model,
                    "standard",
                    resp,
                    0,
                    0,
                    0,
                    0,
                    0,
                    "2k",
                    0.0,
                    "720p",
                    0.0,
                    0,
                    0.0,
                    f"Swarm worker task_id={task_id}",
                )

                output_text = (getattr(resp, "text", None) or "").strip()
                resolved_out: Optional[str] = None
                if out_file_str and output_text:
                    out_p = resolve_path(str(out_file_str))
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    cleaned = output_text
                    if out_p.suffix.lower() in _CODE_SUFFIXES and cleaned.startswith("```"):
                        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
                        cleaned = re.sub(r"\s*```$", "", cleaned)
                    await asyncio.to_thread(out_p.write_text, cleaned, encoding="utf-8")
                    resolved_out = str(out_p)

                elapsed = round(time.perf_counter() - t0, 2)
                return {
                    "id": task_id,
                    "status": "completed",
                    "elapsed_sec": elapsed,
                    "cost_usd": worker_cost_entry["cost_usd"],
                    "output_file": resolved_out,
                    "output_preview": output_text[:280],
                }
            except Exception as exc:
                elapsed = round(time.perf_counter() - t0, 2)
                return {
                    "id": task_id,
                    "status": "failed",
                    "elapsed_sec": elapsed,
                    "cost_usd": 0.0,
                    "error": str(exc)[:300],
                }

    t_start = time.perf_counter()
    results = await asyncio.gather(*(_run_single_worker(i, t) for i, t in enumerate(tasks)))
    total_elapsed = round(time.perf_counter() - t_start, 2)

    succeeded = sum(1 for r in results if r["status"] == "completed")
    failed = len(results) - succeeded
    swarm_cost_usd = round(sum(float(r.get("cost_usd", 0.0)) for r in results), 6)

    return {
        "model": model,
        "total_tasks": len(tasks),
        "concurrency": concurrency,
        "succeeded": succeeded,
        "failed": failed,
        "total_elapsed_sec": total_elapsed,
        "swarm_cost_usd": swarm_cost_usd,
        "results": results,
    }


def register(mcp: Any) -> None:
    """Register context caching and swarm tools on the MCP server instance."""
    mcp.tool()(gemini_context_cache)
    mcp.tool()(gemini_async_swarm)
