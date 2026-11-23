"""MCP server factory and CLI entry point for `gemini-omni-mcp`."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Iterable, Optional, Union

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]

from gemini_omni_mcp import __version__
from gemini_omni_mcp.config import get_enabled_toolsets, logger
from gemini_omni_mcp.tools import (
    analyze,
    audio,
    budget,
    cad_3d,
    docs,
    files,
    image,
    research,
    swarm,
    video,
)


def create_server(
    toolsets: Optional[Union[str, Iterable[str]]] = None,
    enable_3d_tools: Optional[bool] = None,
) -> FastMCP:
    """Create and configure the `gemini-omni` MCP server for the selected toolsets.

    Default (`core`) registers 6 lean high-impact tools (`gemini_image`, `gemini_video`,
    `gemini_audio`, `gemini_analyze`, `gemini_docs`, `gemini_budget`). Opt into additional
    groups via `toolsets` / `GEMINI_OMNI_TOOLSETS`: `swarm` (+3), `research` (+1), `3d` (+3),
    or `all` (13 tools).
    """
    enabled = get_enabled_toolsets(toolsets)
    if enable_3d_tools is True:
        enabled.add("3d")
    elif enable_3d_tools is False:
        enabled.discard("3d")

    mcp = FastMCP("gemini-omni")

    if "core" in enabled:
        image.register(mcp)
        video.register(mcp)
        audio.register(mcp)
        analyze.register(mcp)
        docs.register(mcp)
        budget.register(mcp)

    if "swarm" in enabled:
        swarm.register(mcp)
        files.register(mcp)

    if "research" in enabled:
        research.register(mcp)

    if "3d" in enabled:
        cad_3d.register(mcp)

    return mcp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gemini-omni-mcp",
        description=(
            "Lean, hardened Google GenAI Multimodal & Agentic MCP Server "
            "(default 6 core tools; opt-in toolsets: swarm, research, 3d, all)."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--toolsets",
        type=str,
        default=None,
        help=(
            "Comma-separated toolsets to enable: core (default, 6 tools), "
            "swarm (+3), research (+1), 3d (+3), or all (13 tools). "
            "Overrides GEMINI_OMNI_TOOLSETS."
        ),
    )
    parser.add_argument(
        "--allow-outside-workspace",
        action="store_true",
        help=(
            "Allow file reads/writes outside GEMINI_OMNI_WORKSPACE "
            "(sets GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=true)."
        ),
    )
    parser.add_argument(
        "--no-3d-tools",
        action="store_true",
        help="Legacy flag: explicitly exclude the optional `3d` toolset (already off by default).",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Override the workspace directory used for relative paths and usage ledger.",
    )
    parser.add_argument(
        "--budget-limit",
        type=float,
        default=None,
        help="Override OMNI_HARD_STOP_LIMIT_USD (set 0 to disable hard stop).",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="Print registered MCP tools and exit.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    """CLI entry point for starting the Gemini Omni MCP server."""
    args = _build_parser().parse_args(argv)

    if args.version:
        print(f"gemini-omni-mcp {__version__}")
        return

    if args.workspace:
        os.environ["GEMINI_OMNI_WORKSPACE"] = args.workspace
    if args.budget_limit is not None:
        os.environ["OMNI_HARD_STOP_LIMIT_USD"] = str(args.budget_limit)
    if args.toolsets:
        os.environ["GEMINI_OMNI_TOOLSETS"] = args.toolsets
    if args.allow_outside_workspace:
        os.environ["GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE"] = "true"
    if args.no_3d_tools:
        os.environ["GEMINI_OMNI_ENABLE_3D_TOOLS"] = "false"

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    server = create_server(
        toolsets=args.toolsets,
        enable_3d_tools=(False if args.no_3d_tools else None),
    )

    if args.list_tools:
        tools = asyncio.run(server.list_tools())
        print(f"gemini-omni-mcp {__version__} ({len(tools)} tools):")
        for tool in tools:
            first_line = (getattr(tool, "description", "") or "").strip().splitlines()[0]
            print(f"  - {tool.name}: {first_line}")
        return

    if sys.platform == "win32":
        logger.debug("Starting gemini-omni-mcp on Windows (%s transport)", args.transport)

    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
