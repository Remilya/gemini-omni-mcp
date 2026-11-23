"""Offline tests for modular MCP toolset registration, budget actions, and defaults."""

from __future__ import annotations

import asyncio
import inspect

import pytest

from gemini_omni_mcp.server import create_server
from gemini_omni_mcp.tools import (
    ALL_TOOL_NAMES,
    CORE_TOOL_NAMES,
    OPTIONAL_3D_TOOL_NAMES,
    RESEARCH_TOOL_NAMES,
    SWARM_TOOL_NAMES,
)
from gemini_omni_mcp.tools.analyze import gemini_analyze
from gemini_omni_mcp.tools.budget import gemini_budget
from gemini_omni_mcp.tools.cad_3d import gemini_3d_judge_and_autopatch
from gemini_omni_mcp.tools.image import gemini_image
from gemini_omni_mcp.tools.swarm import gemini_async_swarm, gemini_context_cache
from gemini_omni_mcp.tools.video import gemini_video


def test_default_model_parameters():
    assert inspect.signature(gemini_3d_judge_and_autopatch).parameters["model"].default == "gemini-4-neon"
    assert inspect.signature(gemini_context_cache).parameters["model"].default == "gemini-4-neon"
    assert inspect.signature(gemini_async_swarm).parameters["model"].default == "gemini-4-hydrogen"
    assert inspect.signature(gemini_analyze).parameters["model"].default == "gemini-4-hydrogen"
    assert inspect.signature(gemini_image).parameters["model"].default == "gemini-nano-banana-2.1"
    assert inspect.signature(gemini_video).parameters["model"].default == "gemini-omni-1.2-flash"


def test_server_registers_6_core_tools_by_default():
    server = create_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == set(CORE_TOOL_NAMES)
    assert len(names) == 6
    for excluded in (*SWARM_TOOL_NAMES, *RESEARCH_TOOL_NAMES, *OPTIONAL_3D_TOOL_NAMES):
        assert excluded not in names


def test_server_registers_9_tools_with_core_and_swarm():
    server = create_server(toolsets="core,swarm")
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == set(CORE_TOOL_NAMES) | set(SWARM_TOOL_NAMES)
    assert len(names) == 9


def test_server_registers_all_13_tools_with_all():
    server = create_server(toolsets="all")
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == set(ALL_TOOL_NAMES)
    assert len(names) == 13


def test_server_env_var_and_legacy_3d_flag(monkeypatch):
    monkeypatch.setenv("GEMINI_OMNI_TOOLSETS", "core,research")
    server = create_server()
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == set(CORE_TOOL_NAMES) | set(RESEARCH_TOOL_NAMES)
    assert len(names) == 7

    monkeypatch.delenv("GEMINI_OMNI_TOOLSETS", raising=False)
    monkeypatch.setenv("GEMINI_OMNI_ENABLE_3D_TOOLS", "true")
    server_legacy = create_server()
    names_legacy = {t.name for t in asyncio.run(server_legacy.list_tools())}
    assert names_legacy == set(CORE_TOOL_NAMES) | set(OPTIONAL_3D_TOOL_NAMES)
    assert len(names_legacy) == 9


def test_invalid_toolset_raises_value_error():
    with pytest.raises(ValueError, match="Unknown toolset"):
        create_server(toolsets="core,nonexistent")


def test_budget_tool_offline_actions():
    pricing = asyncio.run(gemini_budget(action="pricing_table"))
    for expected in (
        "gemini-4-carbon",
        "gemini-4-neon",
        "gemini-4-hydrogen",
        "gemini-decision-1",
        "gemini-3.5-transcribe",
        "gemini-omni-1.2-flash",
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    ):
        assert expected in pricing["models"]

    calc = asyncio.run(
        gemini_budget(
            action="calculate_call",
            model="gemini-4-hydrogen",
            input_tokens=100_000,
            output_tokens=20_000,
        )
    )
    assert calc["recorded"] is False
    assert calc["calculation"]["cost_usd"] > 0

    batch = asyncio.run(
        gemini_budget(
            action="estimate_batch",
            model="gemini-4-hydrogen",
            num_items=25,
            avg_input_tokens=5000,
            avg_output_tokens=1000,
        )
    )
    assert batch["num_items"] == 25
    assert batch["batch_tier"]["cost_usd"] < batch["standard_tier"]["cost_usd"]

    updated = asyncio.run(
        gemini_budget(action="set_budget_limit", new_budget_limit_usd=75.0)
    )
    assert updated["hard_stop_limit_usd"] == 75.0

    summary = asyncio.run(gemini_budget(action="summary"))
    assert summary["hard_stop_limit_usd"] == 75.0

    reset = asyncio.run(gemini_budget(action="reset_ledger"))
    assert reset["status"] == "reset"


def test_swarm_fails_cleanly_without_api_key():
    with pytest.raises(RuntimeError, match="Missing GEMINI_API_KEY"):
        asyncio.run(
            gemini_async_swarm(
                tasks=[{"id": "t1", "prompt": "Say hello"}],
            )
        )
