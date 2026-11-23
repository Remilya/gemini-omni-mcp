"""MCP server factory and CLI entry point for `gemini-omni-mcp`."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]

from gemini_omni_mcp import __version__
from gemini_omni_mcp.config import is_3d_tools_enabled, logger
from gemini_omni_mcp.tools import (
    analyze,
    audio,
    budget,
    cad_3d,
    decisions,
    docs,
    embeddings,
    files,
    image,
    research,
    swarm,
    video,
    vision,
)


def create_server(enable_3d_tools: Optional[bool] = None) -> FastMCP:
    """Create and configure the `gemini-omni` MCP server with all selected tools."""
    mcp = FastMCP("gemini-omni")

    docs.register(mcp)
    analyze.register(mcp)
    files.register(mcp)
    decisions.register(mcp)
    research.register(mcp)
    embeddings.register(mcp)
    image.register(mcp)
    video.register(mcp)
    audio.register(mcp)
    swarm.register(mcp)
    vision.register(mcp)
    budget.register(mcp)

    use_3d = is_3d_tools_enabled() if enable_3d_tools is None else bool(enable_3d_tools)
    if use_3d:
        cad_3d.register(mcp)

    return mcp


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gemini-omni-mcp",
        description="All-in-one Google GenAI Multimodal, Decisions, Analyze, Files & Live Docs MCP Server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--no-3d-tools",
        action="store_true",
        help="Disable the 3 optional 3D/CAD tools and run in lean 15-tool mode.",
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
    if args.no_3d_tools:
        os.environ["GEMINI_OMNI_ENABLE_3D_TOOLS"] = "false"

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    server = create_server(enable_3d_tools=(False if args.no_3d_tools else None))

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
