"""Tool modules for the Gemini Omni MCP server."""

from __future__ import annotations

CORE_TOOL_NAMES = (
    "gemini_search_docs",
    "gemini_fetch_doc",
    "gemini_decide",
    "gemini_deep_research",
    "gemini_embed",
    "gemini_image_fusion",
    "gemini_image_edit",
    "gemini_video_studio",
    "gemini_audio_studio",
    "gemini_context_cache",
    "gemini_async_swarm",
    "gemini_curate_refs",
    "gemini_cost_and_budget",
)

OPTIONAL_3D_TOOL_NAMES = (
    "vision_extract_3d_spec",
    "vision_rlaif_3d_critic",
    "gemini_3d_judge_and_autopatch",
)

__all__ = ["CORE_TOOL_NAMES", "OPTIONAL_3D_TOOL_NAMES"]
