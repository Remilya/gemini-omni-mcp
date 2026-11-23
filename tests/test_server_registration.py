"""Offline tests for MCP server tool registration, budget tool actions, and swarm preflight."""

from __future__ import annotations

import asyncio

import pytest

from gemini_omni_mcp.server import create_server
from gemini_omni_mcp.tools import CORE_TOOL_NAMES, OPTIONAL_3D_TOOL_NAMES
from gemini_omni_mcp.tools.budget import gemini_cost_and_budget
from gemini_omni_mcp.tools.swarm import gemini_async_swarm


def test_server_registers_all_12_tools_by_default():
    server = create_server(enable_3d_tools=True)
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == set(CORE_TOOL_NAMES) | set(OPTIONAL_3D_TOOL_NAMES)
    assert len(names) == 12


def test_server_registers_9_core_tools_when_3d_disabled():
    server = create_server(enable_3d_tools=False)
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    assert names == set(CORE_TOOL_NAMES)
    assert len(names) == 9
    for excluded in OPTIONAL_3D_TOOL_NAMES:
        assert excluded not in names


def test_budget_tool_offline_actions():
    pricing = asyncio.run(gemini_cost_and_budget(action="pricing_table"))
    assert "gemini-4-argon" in pricing["models"]
    assert "gemini-omni-1.2-flash" in pricing["models"]

    calc = asyncio.run(
        gemini_cost_and_budget(
            action="calculate_call",
            model="gemini-3.8-flash",
            input_tokens=100_000,
            output_tokens=20_000,
        )
    )
    assert calc["recorded"] is False
    assert calc["calculation"]["cost_usd"] > 0

    batch = asyncio.run(
        gemini_cost_and_budget(
            action="estimate_batch",
            model="gemini-3.8-flash",
            num_items=25,
            avg_input_tokens=5000,
            avg_output_tokens=1000,
        )
    )
    assert batch["num_items"] == 25
    assert batch["batch_tier"]["cost_usd"] < batch["standard_tier"]["cost_usd"]

    updated = asyncio.run(
        gemini_cost_and_budget(action="set_budget_limit", new_budget_limit_usd=75.0)
    )
    assert updated["hard_stop_limit_usd"] == 75.0

    summary = asyncio.run(gemini_cost_and_budget(action="summary"))
    assert summary["hard_stop_limit_usd"] == 75.0

    reset = asyncio.run(gemini_cost_and_budget(action="reset_ledger"))
    assert reset["status"] == "reset"


def test_swarm_fails_cleanly_without_api_key():
    with pytest.raises(RuntimeError, match="Missing GEMINI_API_KEY"):
        asyncio.run(
            gemini_async_swarm(
                tasks=[{"id": "t1", "prompt": "Say hello"}],
            )
        )
