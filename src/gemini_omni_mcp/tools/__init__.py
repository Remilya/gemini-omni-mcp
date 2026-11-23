"""Modular toolset registry for the Gemini Omni MCP server."""

from __future__ import annotations

TOOLSET_TOOLS: dict[str, tuple[str, ...]] = {
    "core": (
        "gemini_image",
        "gemini_video",
        "gemini_audio",
        "gemini_analyze",
        "gemini_docs",
        "gemini_budget",
    ),
    "swarm": (
        "gemini_async_swarm",
        "gemini_context_cache",
        "gemini_files",
    ),
    "research": (
        "gemini_deep_research",
    ),
    "3d": (
        "vision_extract_3d_spec",
        "vision_rlaif_3d_critic",
        "gemini_3d_judge_and_autopatch",
    ),
}

ALL_TOOLSETS = tuple(TOOLSET_TOOLS.keys())
CORE_TOOL_NAMES = TOOLSET_TOOLS["core"]
SWARM_TOOL_NAMES = TOOLSET_TOOLS["swarm"]
RESEARCH_TOOL_NAMES = TOOLSET_TOOLS["research"]
OPTIONAL_3D_TOOL_NAMES = TOOLSET_TOOLS["3d"]
ALL_TOOL_NAMES = tuple(name for names in TOOLSET_TOOLS.values() for name in names)

__all__ = [
    "ALL_TOOLSETS",
    "ALL_TOOL_NAMES",
    "CORE_TOOL_NAMES",
    "OPTIONAL_3D_TOOL_NAMES",
    "RESEARCH_TOOL_NAMES",
    "SWARM_TOOL_NAMES",
    "TOOLSET_TOOLS",
]
