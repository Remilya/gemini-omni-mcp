"""Multimodal embedding generation and similarity comparison via `gemini-embedding-2`."""

from __future__ import annotations

import asyncio
import math
from typing import Any, Optional

from google.genai import types

from gemini_omni_mcp.client import api_retry, get_client
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.media import load_media_part
from gemini_omni_mcp.pricing import record_api_usage


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two equal-length float vectors."""
    if not vec_a or len(vec_a) != len(vec_b):
        raise ValueError("Vectors must be non-empty and of equal length.")
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return round(dot / (norm_a * norm_b), 6)


async def gemini_embed(
    texts: list[str] = [],
    media_paths: list[str] = [],
    model: str = "gemini-embedding-2",
    task_type: Optional[str] = None,
    output_dimensionality: Optional[int] = None,
    compute_similarity_matrix: bool = False,
) -> dict[str, Any]:
    """Generate unified multimodal embeddings (`text`, `image`, `audio`, `video`, `pdf`).

    Uses `gemini-embedding-2` via `client.models.embed_content`, optionally computing
    a pairwise cosine similarity matrix across all embedded items.
    """
    if not texts and not media_paths:
        raise ValueError("Provide at least one item in `texts` or `media_paths`.")

    client = get_client(context=f"gemini_embed:{model}")
    cfg_kwargs: dict[str, Any] = {}
    if task_type:
        cfg_kwargs["task_type"] = task_type.strip().upper()
    if output_dimensionality is not None:
        cfg_kwargs["output_dimensionality"] = int(output_dimensionality)
    embed_cfg = types.EmbedContentConfig(**cfg_kwargs) if cfg_kwargs else None

    items_to_embed: list[tuple[str, str, Any]] = []
    for idx, txt in enumerate(texts):
        items_to_embed.append(("text", f"text[{idx}]", txt))
    for mp in media_paths:
        resolved = resolve_path(mp)
        part = await asyncio.to_thread(load_media_part, str(resolved), 1536)
        items_to_embed.append(("media", resolved.name, [part]))

    @api_retry
    def _embed_one(content_item: Any) -> Any:
        return client.models.embed_content(
            model=model,
            contents=content_item,
            config=embed_cfg,
        )

    embeddings_out: list[dict[str, Any]] = []
    vectors: list[list[float]] = []
    est_tokens = 0

    for idx, (kind, label, content_item) in enumerate(items_to_embed):
        resp = await asyncio.to_thread(_embed_one, content_item)
        emb_list = getattr(resp, "embeddings", None) or []
        if not emb_list and getattr(resp, "embedding", None) is not None:
            emb_list = [resp.embedding]
        if not emb_list:
            raise RuntimeError(f"Model {model!r} returned no embedding for {label}.")

        vals = [float(x) for x in (getattr(emb_list[0], "values", None) or [])]
        vectors.append(vals)
        embeddings_out.append(
            {
                "index": idx,
                "kind": kind,
                "label": label,
                "dimensions": len(vals),
                "values": vals,
            }
        )
        if kind == "text":
            est_tokens += max(8, len(str(content_item)) // 4)
        else:
            est_tokens += 512

    similarity_matrix: Optional[list[list[float]]] = None
    if compute_similarity_matrix and len(vectors) >= 2:
        similarity_matrix = [
            [cosine_similarity(va, vb) for vb in vectors] for va in vectors
        ]

    cost_entry = record_api_usage(
        tool_name="gemini_embed",
        model=model,
        tier="standard",
        input_tokens=est_tokens,
        output_tokens=0,
        note=f"Embedded {len(embeddings_out)} item(s)",
    )

    return {
        "status": "success",
        "model": model,
        "count": len(embeddings_out),
        "embeddings": embeddings_out,
        "similarity_matrix": similarity_matrix,
        "cost_usd": cost_entry["cost_usd"],
    }


def register(mcp: Any) -> None:
    """Register multimodal embedding tools on the MCP server instance."""
    mcp.tool()(gemini_embed)
