"""Managed background research agent tool (`deep-research-preview-04-2026`)."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional

from gemini_omni_mcp.client import api_retry, get_client
from gemini_omni_mcp.config import resolve_path


def _extract_interaction_text(interaction: Any) -> str:
    txt = getattr(interaction, "output_text", None)
    if isinstance(txt, str) and txt.strip():
        return txt.strip()
    for out_item in getattr(interaction, "outputs", None) or []:
        t = getattr(out_item, "text", None)
        if isinstance(t, str) and t.strip():
            return t.strip()
    steps = getattr(interaction, "steps", None) or []
    for step in reversed(steps):
        for content in getattr(step, "content", None) or []:
            t = getattr(content, "text", None)
            if isinstance(t, str) and t.strip():
                return t.strip()
    return ""


async def gemini_deep_research(
    action: Literal["start", "status", "run_and_wait"] = "start",
    prompt: str = "",
    interaction_id: Optional[str] = None,
    agent: Literal[
        "deep-research-preview-04-2026",
        "deep-research-max-preview-04-2026",
        "antigravity-preview-09-2026",
    ] = "deep-research-preview-04-2026",
    poll_interval_sec: int = 10,
    max_wait_sec: int = 300,
    output_markdown_path: Optional[str] = None,
) -> dict[str, Any]:
    """Run or poll autonomous Gemini Deep Research & managed agents via the Interactions API.

    - `action="start"`: Launches background research (`background=True`) and returns `interaction_id`.
    - `action="status"`: Polls `interaction_id` and returns `status` + report text when completed.
    - `action="run_and_wait"`: Starts and polls until completion or `max_wait_sec` timeout.
    """
    client = get_client(context=f"gemini_deep_research:{action}", api_version="v1beta")

    if action == "status":
        if not interaction_id or not interaction_id.strip():
            raise ValueError("interaction_id is required for action='status'.")

        @api_retry
        def _get_status() -> Any:
            return client.interactions.get(interaction_id.strip())

        interaction = await asyncio.to_thread(_get_status)
        status = str(getattr(interaction, "status", "unknown"))
        report_text = _extract_interaction_text(interaction)
        saved_path: Optional[str] = None
        if status == "completed" and report_text and output_markdown_path:
            out_file = resolve_path(output_markdown_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(report_text, encoding="utf-8")
            saved_path = str(out_file)

        return {
            "status": status,
            "interaction_id": getattr(interaction, "id", interaction_id),
            "report_text": report_text or None,
            "output_markdown_path": saved_path,
            "error": str(getattr(interaction, "error", "")) or None,
        }

    if not prompt.strip():
        raise ValueError(f"prompt is required for action='{action}'.")

    @api_retry
    def _start_agent() -> Any:
        return client.interactions.create(
            input=prompt.strip(),
            agent=agent,
            background=True,
        )

    interaction = await asyncio.to_thread(_start_agent)
    created_id = getattr(interaction, "id", None)
    status = str(getattr(interaction, "status", "in_progress"))

    if action == "start" or not created_id:
        return {
            "status": status,
            "agent": agent,
            "interaction_id": created_id,
            "note": "Poll with action='status' and this interaction_id until status == 'completed'.",
        }

    interval = max(2, min(int(poll_interval_sec), 60))
    deadline = asyncio.get_running_loop().time() + max(interval, int(max_wait_sec))

    while status not in ("completed", "failed", "cancelled"):
        if asyncio.get_running_loop().time() >= deadline:
            return {
                "status": status,
                "agent": agent,
                "interaction_id": created_id,
                "timed_out": True,
                "note": "Research is still running; continue polling with action='status'.",
            }
        await asyncio.sleep(interval)
        interaction = await asyncio.to_thread(client.interactions.get, created_id)
        status = str(getattr(interaction, "status", "unknown"))

    report_text = _extract_interaction_text(interaction)
    saved_path = None
    if status == "completed" and report_text and output_markdown_path:
        out_file = resolve_path(output_markdown_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(report_text, encoding="utf-8")
        saved_path = str(out_file)

    return {
        "status": status,
        "agent": agent,
        "interaction_id": created_id,
        "report_text": report_text or None,
        "output_markdown_path": saved_path,
        "error": str(getattr(interaction, "error", "")) or None,
    }


def register(mcp: Any) -> None:
    """Register Deep Research and managed agent tools on the MCP server instance."""
    mcp.tool()(gemini_deep_research)
