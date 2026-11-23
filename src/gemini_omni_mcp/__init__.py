"""All-in-one Google GenAI Multimodal & Agentic MCP Server."""

from __future__ import annotations

__version__ = "2.1.0"


def create_server(*args, **kwargs):
    """Create and configure the Gemini Omni MCP server instance."""
    from gemini_omni_mcp.server import create_server as _create_server

    return _create_server(*args, **kwargs)


__all__ = ["__version__", "create_server"]
