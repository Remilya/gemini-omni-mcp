"""Stateful video generation, extension, editing, and seamless looping via Gemini Omni."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Literal, Optional

from gemini_omni_mcp.client import api_retry, get_client
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.media import guess_mime
from gemini_omni_mcp.pricing import record_api_usage


async def gemini_video(
    action: Literal["generate", "extend", "edit", "seamless_loop"] = "generate",
    prompt: str = "",
    output_mp4_path: str = "output/gemini_video.mp4",
    resolution: Literal["360p", "720p", "1080p", "4k"] = "720p",
    duration: str = "10s",
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
    delivery: Literal["inline", "uri", "auto"] = "auto",
    model: str = "gemini-omni-1.2-flash",
    previous_interaction_id: Optional[str] = None,
    start_frame_path: Optional[str] = None,
    end_frame_path: Optional[str] = None,
    source_video_path: Optional[str] = None,
    ref_media_paths: list[str] = [],
    task: Optional[
        Literal["text_to_video", "image_to_video", "reference_to_video", "edit", "extend"]
    ] = None,
) -> dict[str, Any]:
    """Stateful video generation, extension, editing, and looping via `client.interactions.create`.

    Supports `gemini-omni-1.2-flash` (default) and `gemini-omni-1.1-flash`, durations `"3s"`–`"15s"`,
    two-frame interpolation (`start_frame_path` -> `end_frame_path`), up to 6 reference images/videos,
    and automatic `uri` delivery for 1080p/4K or >10s clips.
    """
    if not prompt.strip():
        raise ValueError("prompt cannot be empty.")

    client = get_client(context=f"gemini_video:{action}", api_version="v1beta")

    dur_str = duration.strip().lower()
    if not dur_str.endswith("s"):
        dur_str = f"{dur_str}s"
    try:
        dur_sec = max(3, min(15, int(float(dur_str[:-1]))))
    except ValueError:
        dur_sec = 10

    effective_end_frame = (
        start_frame_path if action == "seamless_loop" and start_frame_path else end_frame_path
    )
    if (start_frame_path and effective_end_frame) or action == "extend":
        dur_sec = min(10, dur_sec)
    dur_str = f"{dur_sec}s"

    input_items: list[dict[str, Any]] = []
    if source_video_path:
        sv_path = resolve_path(source_video_path)
        uploaded_vid = await asyncio.to_thread(client.files.upload, file=str(sv_path))
        while (
            getattr(uploaded_vid, "state", None)
            and getattr(uploaded_vid.state, "name", str(uploaded_vid.state)) == "PROCESSING"
        ):
            await asyncio.sleep(2.0)
            uploaded_vid = await asyncio.to_thread(client.files.get, name=uploaded_vid.name)
        input_items.append({"type": "video", "uri": uploaded_vid.uri})

    if start_frame_path:
        sf = resolve_path(start_frame_path)
        input_items.append(
            {
                "type": "image",
                "mime_type": guess_mime(sf),
                "data": base64.b64encode(sf.read_bytes()).decode("ascii"),
            }
        )
    if effective_end_frame:
        ef = resolve_path(effective_end_frame)
        input_items.append(
            {
                "type": "image",
                "mime_type": guess_mime(ef),
                "data": base64.b64encode(ef.read_bytes()).decode("ascii"),
            }
        )
    for rp in ref_media_paths[:6]:
        rf = resolve_path(rp)
        if rf.suffix.lower() == ".mp4":
            up_ref = await asyncio.to_thread(client.files.upload, file=str(rf))
            while (
                getattr(up_ref, "state", None)
                and getattr(up_ref.state, "name", str(up_ref.state)) == "PROCESSING"
            ):
                await asyncio.sleep(2.0)
                up_ref = await asyncio.to_thread(client.files.get, name=up_ref.name)
            input_items.append({"type": "video", "uri": up_ref.uri})
        else:
            input_items.append(
                {
                    "type": "image",
                    "mime_type": guess_mime(rf),
                    "data": base64.b64encode(rf.read_bytes()).decode("ascii"),
                }
            )

    natural_prompt = prompt.strip()
    if action == "seamless_loop" and start_frame_path:
        natural_prompt = (
            "Create a seamless loop starting from the first image and ending at the second image. "
            f"{natural_prompt}"
        )
    elif start_frame_path and effective_end_frame:
        natural_prompt = (
            "Start from the first image and transition smoothly to the second image as the final frame. "
            f"{natural_prompt}"
        )

    input_items.append({"type": "text", "text": natural_prompt})

    effective_delivery = delivery
    if delivery == "auto":
        effective_delivery = (
            "uri" if (resolution in ("1080p", "4k") or dur_sec > 10) else "inline"
        )

    resp_fmt: dict[str, Any] = {
        "type": "video",
        "resolution": resolution,
        "duration": dur_str,
        "aspect_ratio": aspect_ratio,
    }
    if effective_delivery == "uri":
        resp_fmt["delivery"] = "uri"

    create_kwargs: dict[str, Any] = {
        "model": model,
        "input": input_items if len(input_items) > 1 else natural_prompt,
        "response_format": resp_fmt,
    }
    if previous_interaction_id:
        create_kwargs["previous_interaction_id"] = previous_interaction_id
    if task:
        create_kwargs["generation_config"] = {"video_config": {"task": task}}

    @api_retry
    def _call_interactions() -> Any:
        return client.interactions.create(**create_kwargs)

    interaction = await asyncio.to_thread(_call_interactions)
    interaction_id = getattr(interaction, "id", None)

    video_bytes: Optional[bytes] = None
    out_vid = getattr(interaction, "output_video", None)
    if out_vid and getattr(out_vid, "data", None):
        raw_v = out_vid.data
        video_bytes = base64.b64decode(raw_v) if isinstance(raw_v, str) else bytes(raw_v)
    elif out_vid and getattr(out_vid, "uri", None):
        vid_uri = str(out_vid.uri)
        file_id = vid_uri.rstrip("/").split("/")[-1].split(":")[0]
        file_name = f"files/{file_id}" if not file_id.startswith("files/") else file_id
        for _ in range(30):
            f_info = await asyncio.to_thread(client.files.get, name=file_name)
            state_name = getattr(
                getattr(f_info, "state", None), "name", str(getattr(f_info, "state", ""))
            )
            if state_name == "ACTIVE":
                break
            await asyncio.sleep(2.0)
        dl_bytes = await asyncio.to_thread(client.files.download, file=file_name)
        video_bytes = bytes(dl_bytes) if dl_bytes else None
    else:
        for out_item in getattr(interaction, "outputs", None) or []:
            data = getattr(out_item, "data", None)
            mime = getattr(out_item, "mime_type", "") or ""
            if data and ("video" in mime or getattr(out_item, "type", "") == "video"):
                video_bytes = base64.b64decode(data) if isinstance(data, str) else bytes(data)
                break

    out_file = resolve_path(output_mp4_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if video_bytes:
        out_file.write_bytes(video_bytes)

    num_img_inputs = (
        (1 if start_frame_path else 0)
        + (1 if effective_end_frame else 0)
        + len(ref_media_paths[:6])
    )
    est_in_tokens = num_img_inputs * 560 + max(50, len(prompt) // 4)
    cost_entry = record_api_usage(
        tool_name="gemini_video",
        model=model,
        tier="standard",
        input_tokens=est_in_tokens,
        output_tokens=450,
        video_seconds=float(dur_sec) if video_bytes else 0.0,
        video_resolution=resolution,
        note=f"{action} ({resolution}, {dur_str}, {aspect_ratio}) -> {out_file.name}",
    )

    return {
        "status": "success" if video_bytes else "interaction_created",
        "model": model,
        "action": action,
        "resolution": resolution,
        "duration": dur_str,
        "aspect_ratio": aspect_ratio,
        "delivery": effective_delivery,
        "interaction_id": interaction_id,
        "previous_interaction_id": previous_interaction_id,
        "output_mp4_path": str(out_file) if video_bytes else None,
        "bytes_written": len(video_bytes) if video_bytes else 0,
        "cost_usd": cost_entry["cost_usd"],
        "cost_breakdown": cost_entry["breakdown_usd"],
    }


def register(mcp: Any) -> None:
    """Register video tools on the MCP server instance."""
    mcp.tool()(gemini_video)
