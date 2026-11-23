"""Nano Banana 2.1 unified image synthesis, editing, inpaint/outpaint, and upscaling."""

from __future__ import annotations

import asyncio
import io
from typing import Any, Literal, Optional

from google.genai import types
from PIL import Image

from gemini_omni_mcp.client import (
    build_thinking_config,
    generate_content_with_retry,
    get_client,
)
from gemini_omni_mcp.config import logger, resolve_path
from gemini_omni_mcp.media import extract_image_bytes, load_media_part

_PRESET_INSTRUCTIONS = {
    "pixel_sprite": (
        "SINGLE-SPRITE PIXEL ART REFERENCE LAYOUT:\n"
        "- Generate EXACTLY ONE centered full-body front-facing pixel-art sprite (do NOT draw multiple angles or turnaround panels).\n"
        "- Crisp distinct pixel clusters, clean dark outline, zero anti-aliasing blur.\n"
        "- Faithfully preserve signature colors, outfit, accessories, and held items from any attached references.\n"
        "- No pedestal, no drop-shadow, no text labels, on a completely flat uniform #F2EFE9 light neutral background."
    ),
    "story_scene": (
        "CINEMATIC STORY SCENE ILLUSTRATION (SINGLE FULL-BLEED FRAME):\n"
        "- Generate a single cohesive, richly lit narrative frame (no split panels, turnaround grids, or text labels).\n"
        "- Preserve exact character identity, facial features, wardrobe, and environment atmosphere from any attached reference sheets."
    ),
    "character_sheet": (
        "4-ANGLE ORTHOGRAPHIC CHARACTER TURNAROUND SHEET:\n"
        "- Panel 1: Front Orthographic Full-Body View (neutral A-pose, clear features and outfit layers).\n"
        "- Panel 2: Back Orthographic Full-Body View (showing rear hair, cape, wings, and back details).\n"
        "- Panel 3: Left Side Orthographic Profile View.\n"
        "- Panel 4: 3/4 South-East Isometric View with signature prop or accessory.\n"
        "- Lock proportions and style to Image #1 (Style Anchor) if provided, fusing colors and details from remaining refs.\n"
        "- Clean neutral #F2EFE9 background, crisp alignment, zero text labels or watermarks."
    ),
    "architectural_sheet": (
        "3-ANGLE ARCHITECTURAL / DIORAMA DESIGN SHEET:\n"
        "- Main View (70%): 3/4 South-East Isometric View showing full massing and exterior materials.\n"
        "- Inset 1 (Top-Right): Front Orthographic Elevation showing exact roof pitch, facade, and entryways.\n"
        "- Inset 2 (Bottom-Right): Top-Down Orthographic Plan showing footprint, layout, and surrounding props.\n"
        "- Lock rendering style to Image #1 (Style Anchor) if provided; neutral #F2EFE9 background, zero text labels."
    ),
    "freeform": (
        "MULTI-REFERENCE VISUAL FUSION:\n"
        "- Combine attached visual references faithfully according to the prompt instructions with zero unwanted text or watermarks."
    ),
}


def _build_image_config(
    aspect_ratio: Optional[str],
    image_size: Optional[str],
) -> Optional[types.ImageConfig]:
    cfg_kwargs: dict[str, Any] = {}
    if aspect_ratio:
        cfg_kwargs["aspect_ratio"] = aspect_ratio
    if image_size:
        cfg_kwargs["image_size"] = image_size.upper()
    return types.ImageConfig(**cfg_kwargs) if cfg_kwargs else None


async def gemini_image(
    prompt: str = "",
    output_path: str = "output/gemini_image.png",
    action: Literal["generate", "edit", "inpaint", "outpaint", "upscale"] = "generate",
    source_image_path: Optional[str] = None,
    mask_image_path: Optional[str] = None,
    ref_image_paths: list[str] = [],
    style_anchor_path: Optional[str] = None,
    upscale_factor: Literal["x2", "x4"] = "x4",
    preset: Literal[
        "freeform",
        "character_sheet",
        "architectural_sheet",
        "story_scene",
        "pixel_sprite",
    ] = "freeform",
    aspect_ratio: Optional[str] = None,
    image_size: Optional[str] = None,
    model: str = "gemini-nano-banana-2.1",
    thinking_level: str = "HIGH",
    use_google_search: bool = False,
) -> dict[str, Any]:
    """Generate, fuse, edit, inpaint, outpaint, or upscale images with Nano Banana 2.1.

    - `action="generate"`: Text-to-image and multi-reference visual fusion (up to 14 refs +
      optional `style_anchor_path`), presets (`freeform`, `character_sheet`,
      `architectural_sheet`, `story_scene`, `pixel_sprite`), `aspect_ratio`, and `image_size`
      (`0.5K`, `1K`, `2K`, `4K`).
    - `action="edit" | "inpaint" | "outpaint" | "upscale"`: Conversational editing on
      `source_image_path` (with optional `mask_image_path` and up to 6 `ref_image_paths`),
      plus deterministic Pillow Lanczos fallback for `action="upscale"`.
    """
    out_file = resolve_path(output_path)

    if action == "generate":
        if not prompt.strip():
            raise ValueError("prompt cannot be empty for action='generate'.")

        contents: list[types.Part] = []
        if style_anchor_path:
            contents.append(load_media_part(style_anchor_path, max_dim=1536))
        for ref_p in ref_image_paths[:14]:
            contents.append(load_media_part(ref_p, max_dim=1536))

        layout_instruction = _PRESET_INSTRUCTIONS[preset]
        full_prompt = f"{layout_instruction}\n\nPrompt & Specific Requirements:\n{prompt}"
        contents.append(types.Part.from_text(text=full_prompt))

        tools_list = [types.Tool(google_search=types.GoogleSearch())] if use_google_search else None
        image_cfg = _build_image_config(aspect_ratio, image_size)

        client = get_client(context="gemini_image:generate")
        if "nano-banana" in model.lower():
            config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=image_cfg,
            )
        else:
            cfg_kwargs: dict[str, Any] = {
                "response_modalities": ["IMAGE", "TEXT"],
                "tools": tools_list,
                "image_config": image_cfg,
            }
            thinking_cfg = build_thinking_config(model, thinking_level)
            if thinking_cfg is not None:
                cfg_kwargs["thinking_config"] = thinking_cfg
            config = types.GenerateContentConfig(**cfg_kwargs)

        try:
            response = await asyncio.to_thread(
                generate_content_with_retry,
                client,
                model,
                contents,
                config,
                False,
                "gemini_image",
            )
        except Exception as first_err:
            logger.warning(
                "Model %s failed with advanced config (%s); retrying with streamlined IMAGE config.",
                model,
                first_err,
            )
            fallback_config = types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
            response = await asyncio.to_thread(
                generate_content_with_retry,
                client,
                model,
                contents,
                fallback_config,
                False,
                "gemini_image",
            )

        img_bytes = extract_image_bytes(response)
        if not img_bytes:
            raise RuntimeError(
                f"Model '{model}' did not return an inline image. Text output: {getattr(response, 'text', '')}"
            )

        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(img_bytes)
        return {
            "status": "success",
            "action": "generate",
            "model": model,
            "preset": preset,
            "output_path": str(out_file),
            "style_anchor_used": bool(style_anchor_path),
            "reference_count": min(14, len(ref_image_paths)),
            "bytes_written": len(img_bytes),
        }

    # Editing / inpaint / outpaint / upscale branch
    if not source_image_path or not source_image_path.strip():
        raise ValueError(f"source_image_path is required for action='{action}'.")
    if action != "upscale" and not prompt.strip():
        raise ValueError(f"prompt cannot be empty for action='{action}'.")

    src_path = resolve_path(source_image_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    client = get_client(context=f"gemini_image:{action}")
    contents = [load_media_part(str(src_path), max_dim=2048)]
    if mask_image_path:
        contents.append(load_media_part(mask_image_path, max_dim=2048))
    if style_anchor_path:
        contents.append(load_media_part(style_anchor_path, max_dim=1536))
    for rp in ref_image_paths[:6]:
        contents.append(load_media_part(rp, max_dim=1536))

    if action == "inpaint":
        edit_prompt = (
            "Perform targeted inpainting on Image #1"
            + (" strictly inside the masked region shown in Image #2." if mask_image_path else ".")
            + "\nKeep all unmasked pixels, proportions, and lighting consistent.\n"
            f"Inpaint Instruction: {prompt}"
        )
    elif action == "outpaint":
        edit_prompt = (
            "Seamlessly outpaint and extend the canvas of Image #1"
            + (" guided by the layout/mask in Image #2." if mask_image_path else ".")
            + "\nPreserve the original subject, perspective, lighting, and textures seamlessly.\n"
            f"Outpaint Instruction: {prompt}"
        )
    elif action == "upscale":
        edit_prompt = (
            f"Enhance and upscale Image #1 to crisp high-definition ({upscale_factor} detail) "
            "while preserving 100% of the exact composition, colors, and identity.\n"
            f"Detail Notes: {prompt or 'Sharpen fine textures and remove compression artifacts.'}"
        )
    else:
        edit_prompt = (
            "Perform a precise localized image edit on the first attached source image.\n"
            "Preserve the existing layout, proportions, background, and unmentioned regions intact.\n"
            f"Edit Instruction: {prompt}"
        )

    contents.append(types.Part.from_text(text=edit_prompt))

    eff_size = image_size
    if action == "upscale" and not eff_size:
        eff_size = "4K" if upscale_factor == "x4" else "2K"

    image_cfg = _build_image_config(aspect_ratio, eff_size)
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=image_cfg,
    )

    img_bytes = None
    used_model = model
    try:
        response = await asyncio.to_thread(
            generate_content_with_retry,
            client,
            model,
            contents,
            config,
            False,
            "gemini_image",
        )
        img_bytes = extract_image_bytes(response)
    except Exception as exc:
        if action != "upscale":
            raise
        logger.info("AI upscale fallback to Pillow Lanczos (%s)", exc)

    if not img_bytes and action == "upscale":
        with Image.open(src_path) as im:
            scale = 4 if upscale_factor == "x4" else 2
            up_im = im.resize((im.width * scale, im.height * scale), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            up_im.save(buf, format="PNG")
            img_bytes = buf.getvalue()
        used_model = f"{model} (lanczos-fallback)"

    if not img_bytes:
        raise RuntimeError(
            f"gemini_image ({action}) did not receive image bytes from '{model}'."
        )

    out_file.write_bytes(img_bytes)
    return {
        "status": "success",
        "action": action,
        "model": used_model,
        "source_image_path": str(src_path),
        "output_path": str(out_file),
        "prompt": prompt,
        "bytes_written": len(img_bytes),
    }


def register(mcp: Any) -> None:
    """Register unified Nano Banana image tool on the MCP server instance."""
    mcp.tool()(gemini_image)
