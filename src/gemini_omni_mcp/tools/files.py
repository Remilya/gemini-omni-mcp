"""Gemini Files API management tool (`upload`, `list`, `get`, `delete`) with 48h retention."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional

from gemini_omni_mcp.client import get_client
from gemini_omni_mcp.config import resolve_path


def _serialize_file_obj(f: Any) -> dict[str, Any]:
    state = getattr(f, "state", None)
    state_str = getattr(state, "name", str(state)) if state is not None else None
    create_t = getattr(f, "create_time", None)
    exp_t = getattr(f, "expiration_time", None)
    return {
        "name": getattr(f, "name", None),
        "display_name": getattr(f, "display_name", None),
        "uri": getattr(f, "uri", None),
        "mime_type": getattr(f, "mime_type", None),
        "size_bytes": getattr(f, "size_bytes", None),
        "state": state_str,
        "create_time": create_t.isoformat() if hasattr(create_t, "isoformat") else create_t,
        "expiration_time": exp_t.isoformat() if hasattr(exp_t, "isoformat") else exp_t,
    }


async def gemini_files(
    action: Literal["upload", "list", "get", "delete"] = "list",
    file_path: Optional[str] = None,
    file_name: Optional[str] = None,
    display_name: Optional[str] = None,
    wait_until_active: bool = True,
    limit: int = 25,
) -> dict[str, Any]:
    """Manage reusable files via the Gemini Files API (48-hour retention).

    Upload large videos, PDFs, or audio once and reuse the returned `files/<id>` name
    across `gemini_analyze`, `gemini_decide`, `gemini_audio_studio`, and `gemini_video_studio`.
    """
    client = get_client(context=f"gemini_files:{action}")

    if action == "upload":
        if not file_path or not file_path.strip():
            raise ValueError("file_path is required for action='upload'.")
        fpath = resolve_path(file_path)
        if not fpath.is_file():
            raise FileNotFoundError(f"File not found: {fpath}")

        upload_kwargs: dict[str, Any] = {"file": str(fpath)}
        if display_name and display_name.strip():
            upload_kwargs["config"] = {"display_name": display_name.strip()}

        uploaded = await asyncio.to_thread(client.files.upload, **upload_kwargs)
        if wait_until_active:
            for _ in range(60):
                state = getattr(uploaded, "state", None)
                state_name = getattr(state, "name", str(state)) if state is not None else ""
                if state_name != "PROCESSING":
                    break
                await asyncio.sleep(2.0)
                uploaded = await asyncio.to_thread(client.files.get, name=uploaded.name)

        return {
            "status": "success",
            "action": "upload",
            "file": _serialize_file_obj(uploaded),
        }

    if action == "get":
        if not file_name or not file_name.strip():
            raise ValueError("file_name is required for action='get'.")
        f_obj = await asyncio.to_thread(client.files.get, name=file_name.strip())
        return {
            "status": "success",
            "action": "get",
            "file": _serialize_file_obj(f_obj),
        }

    if action == "delete":
        if not file_name or not file_name.strip():
            raise ValueError("file_name is required for action='delete'.")
        await asyncio.to_thread(client.files.delete, name=file_name.strip())
        return {
            "status": "success",
            "action": "delete",
            "deleted": file_name.strip(),
        }

    # action == "list"
    cap = max(1, min(int(limit), 200))

    def _list_files() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for f_obj in client.files.list():
            items.append(_serialize_file_obj(f_obj))
            if len(items) >= cap:
                break
        return items

    files_out = await asyncio.to_thread(_list_files)
    return {
        "status": "success",
        "action": "list",
        "count": len(files_out),
        "files": files_out,
    }


def register(mcp: Any) -> None:
    """Register Gemini Files API tools on the MCP server instance."""
    mcp.tool()(gemini_files)
