"""General-purpose visual reference curation via numbered contact sheets."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from google.genai import types

from gemini_omni_mcp.client import generate_content_with_retry, get_client
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.media import build_numbered_contact_grid, extract_json_text
from gemini_omni_mcp.schemas import CuratedRefsResponse


async def gemini_curate_refs(
    candidate_image_paths: list[str],
    goal: str = "Identify the sharpest, best-framed reference images across distinct angles and details",
    top_k: int = 8,
    save_contact_sheet_path: Optional[str] = None,
    model: str = "gemini-4-hydrogen",
) -> dict[str, Any]:
    """Curate a batch of candidate images in one shot using a numbered contact grid and Gemini 4 Hydrogen.

    Rejects blurry, heavily cropped, watermarked, or occluded images and returns the top-ranked
    reference paths with per-image view categorization and descriptions.
    """
    if not candidate_image_paths:
        raise ValueError("candidate_image_paths must contain at least one image path.")

    grid_bytes, meta_list = await asyncio.to_thread(
        build_numbered_contact_grid, candidate_image_paths
    )

    saved_grid_path: Optional[str] = None
    if save_contact_sheet_path:
        out_grid = resolve_path(save_contact_sheet_path)
        out_grid.parent.mkdir(parents=True, exist_ok=True)
        out_grid.write_bytes(grid_bytes)
        saved_grid_path = str(out_grid)

    prompt = (
        "You are an expert Visual Reference Curator.\n"
        f"Goal: {goal}\n"
        f"Select up to top_k={top_k} best reference images from the numbered contact grid [#0 .. #{len(candidate_image_paths) - 1}].\n"
        f"Candidate metadata:\n{json.dumps(meta_list, indent=2)}\n\n"
        "Filtering Rules:\n"
        "1. REJECT blurry, heavily cropped, severely occluded, watermarked, or off-topic images.\n"
        "2. PRIORITIZE high-resolution, well-lit images that collectively cover the requested angles or details.\n"
        "3. Return your response strictly matching the CuratedRefsResponse JSON schema."
    )

    client = get_client(context="gemini_curate_refs")
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        response_mime_type="application/json",
        response_schema=CuratedRefsResponse,
        temperature=0.1,
    )

    contents = [
        types.Part.from_bytes(data=grid_bytes, mime_type="image/jpeg"),
        types.Part.from_text(text=prompt),
    ]

    response = await asyncio.to_thread(
        generate_content_with_retry,
        client,
        model,
        contents,
        config,
        False,
        "gemini_curate_refs",
    )
    parsed = CuratedRefsResponse.model_validate_json(extract_json_text(response))

    selected_paths: list[str] = []
    for item in parsed.selected_refs[:top_k]:
        if 0 <= item.index < len(candidate_image_paths):
            item.file_path = str(resolve_path(candidate_image_paths[item.index]))
        selected_paths.append(item.file_path)

    return {
        "model": model,
        "selected_image_paths": selected_paths,
        "selected_refs": [r.model_dump() for r in parsed.selected_refs[:top_k]],
        "rejected_indices": parsed.rejected_indices,
        "curation_summary": parsed.curation_summary,
        "contact_sheet_path": saved_grid_path,
    }


def register(mcp: Any) -> None:
    """Register visual reference curation tools on the MCP server instance."""
    mcp.tool()(gemini_curate_refs)
