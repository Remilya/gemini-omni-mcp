"""Image synthesis, multi-reference fusion, conversational editing, and Imagen 3 tools."""

from __future__ import annotations

import asyncio
import io
from typing import Any, Literal, Optional

from google.genai import types
from PIL import Image

from gemini_omni_mcp.client import generate_content_with_retry, get_client
from gemini_omni_mcp.config import logger, resolve_path
from gemini_omni_mcp.media import extract_image_bytes, load_media_part
from gemini_omni_mcp.pricing import record_api_usage


async def gemini_image_fusion(
    prompt: str,
    output_path: str,
    ref_image_paths: list[str] = [],
    style_anchor_path: Optional[str] = None,
    model: str = "gemini-nano-banana-2.1",
    thinking_level: str = "HIGH",
    use_google_search: bool = False,
    preset: Literal[
        "freeform",
        "character_sheet",
        "architectural_sheet",
        "story_scene",
        "pixel_sprite",
    ] = "freeform",
    aspect_ratio: Optional[str] = None,
    image_size: Optional[str] = None,
) -> dict[str, Any]:
    """Multi-reference image synthesis and fusion (up to 14 reference images + optional style anchor).

    Supports presets (`freeform`, `character_sheet`, `architectural_sheet`, `story_scene`,
    `pixel_sprite`) and official `ImageConfig` (`aspect_ratio` and `image_size`: `0.5K`, `1K`, `2K`, `4K`).
    """
    contents: list[types.Part] = []

    if style_anchor_path:
        contents.append(load_media_part(style_anchor_path, max_dim=1536))

    for ref_p in ref_image_paths[:14]:
        contents.append(load_media_part(ref_p, max_dim=1536))

    if preset == "pixel_sprite":
        layout_instruction = (
            "SINGLE-SPRITE PIXEL ART REFERENCE LAYOUT:\n"
            "- Generate EXACTLY ONE centered full-body front-facing pixel-art sprite (do NOT draw multiple angles or turnaround panels).\n"
            "- Crisp distinct pixel clusters, clean dark outline, zero anti-aliasing blur.\n"
            "- Faithfully preserve signature colors, outfit, accessories, and held items from any attached references.\n"
            "- No pedestal, no drop-shadow, no text labels, on a completely flat uniform #F2EFE9 light neutral background."
        )
    elif preset == "story_scene":
        layout_instruction = (
            "CINEMATIC STORY SCENE ILLUSTRATION (SINGLE FULL-BLEED FRAME):\n"
            "- Generate a single cohesive, richly lit narrative frame (no split panels, turnaround grids, or text labels).\n"
            "- Preserve exact character identity, facial features, wardrobe, and environment atmosphere from any attached reference sheets."
        )
    elif preset == "character_sheet":
        layout_instruction = (
            "4-ANGLE ORTHOGRAPHIC CHARACTER TURNAROUND SHEET:\n"
            "- Panel 1: Front Orthographic Full-Body View (neutral A-pose, clear features and outfit layers).\n"
            "- Panel 2: Back Orthographic Full-Body View (showing rear hair, cape, wings, and back details).\n"
            "- Panel 3: Left Side Orthographic Profile View.\n"
            "- Panel 4: 3/4 South-East Isometric View with signature prop or accessory.\n"
            "- Lock proportions and style to Image #1 (Style Anchor) if provided, fusing colors and details from remaining refs.\n"
            "- Clean neutral #F2EFE9 background, crisp alignment, zero text labels or watermarks."
        )
    elif preset == "architectural_sheet":
        layout_instruction = (
            "3-ANGLE ARCHITECTURAL / DIORAMA DESIGN SHEET:\n"
            "- Main View (70%): 3/4 South-East Isometric View showing full massing and exterior materials.\n"
            "- Inset 1 (Top-Right): Front Orthographic Elevation showing exact roof pitch, facade, and entryways.\n"
            "- Inset 2 (Bottom-Right): Top-Down Orthographic Plan showing footprint, layout, and surrounding props.\n"
            "- Lock rendering style to Image #1 (Style Anchor) if provided; neutral #F2EFE9 background, zero text labels."
        )
    else:
        layout_instruction = (
            "MULTI-REFERENCE VISUAL FUSION:\n"
            "- Combine attached visual references faithfully according to the prompt instructions with zero unwanted text or watermarks."
        )

    full_prompt = f"{layout_instruction}\n\nPrompt & Specific Requirements:\n{prompt}"
    contents.append(types.Part.from_text(text=full_prompt))

    tools_list = [types.Tool(google_search=types.GoogleSearch())] if use_google_search else None

    img_cfg_kwargs: dict[str, Any] = {}
    if aspect_ratio:
        img_cfg_kwargs["aspect_ratio"] = aspect_ratio
    if image_size:
        img_cfg_kwargs["image_size"] = image_size.upper()
    image_cfg = types.ImageConfig(**img_cfg_kwargs) if img_cfg_kwargs else None

    client = get_client(context="gemini_image_fusion")
    if "nano-banana" in model.lower():
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=image_cfg,
        )
    else:
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level.upper()),
            tools=tools_list,
            image_config=image_cfg,
        )

    try:
        response = await asyncio.to_thread(
            generate_content_with_retry,
            client,
            model,
            contents,
            config,
            False,
            "gemini_image_fusion",
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
            "gemini_image_fusion",
        )

    img_bytes = extract_image_bytes(response)
    if not img_bytes:
        raise RuntimeError(
            f"Model '{model}' did not return an inline image. Text output: {getattr(response, 'text', '')}"
        )

    out_file = resolve_path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(img_bytes)

    return {
        "status": "success",
        "model": model,
        "preset": preset,
        "output_path": str(out_file),
        "style_anchor_used": bool(style_anchor_path),
        "reference_count": min(14, len(ref_image_paths)),
        "bytes_written": len(img_bytes),
    }


async def gemini_image_edit(
    source_image_path: str,
    edit_instruction: str,
    output_path: str,
    extra_ref_paths: list[str] = [],
    model: str = "gemini-nano-banana-2.1",
) -> dict[str, Any]:
    """Conversational and regional image editing without regenerating from scratch.

    Applies targeted changes to `source_image_path` (with up to 6 optional `extra_ref_paths`)
    while keeping unmentioned areas, lighting, and proportions intact.
    """
    contents: list[types.Part] = [load_media_part(source_image_path, max_dim=2048)]
    for rp in extra_ref_paths[:6]:
        contents.append(load_media_part(rp, max_dim=1536))

    prompt = (
        "Perform a precise localized image edit on the first attached source image.\n"
        "Preserve the existing layout, proportions, background, and unmentioned regions intact.\n"
        f"Edit Instruction: {edit_instruction}"
    )
    contents.append(types.Part.from_text(text=prompt))

    client = get_client(context="gemini_image_edit")
    config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])

    response = await asyncio.to_thread(
        generate_content_with_retry,
        client,
        model,
        contents,
        config,
        False,
        "gemini_image_edit",
    )
    img_bytes = extract_image_bytes(response)
    if not img_bytes:
        raise RuntimeError(
            f"gemini_image_edit did not receive edited image bytes from '{model}'. "
            f"Response text: {getattr(response, 'text', '')}"
        )

    out_file = resolve_path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(img_bytes)

    return {
        "status": "success",
        "model": model,
        "source_image_path": str(resolve_path(source_image_path)),
        "output_path": str(out_file),
        "edit_instruction": edit_instruction,
        "bytes_written": len(img_bytes),
    }


async def imagen_studio(
    action: Literal["generate", "inpaint", "outpaint", "upscale"],
    prompt: str,
    output_path: str,
    source_image_path: Optional[str] = None,
    mask_image_path: Optional[str] = None,
    upscale_factor: str = "x4",
) -> dict[str, Any]:
    """Imagen 3 generation, masked inpaint/outpaint, and 2x/4x upscaling with Gemini fallback."""
    client = get_client(context=f"imagen_studio:{action}")
    out_file = resolve_path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    model_used = ""
    img_bytes: Optional[bytes] = None

    if action == "generate":
        model_used = "imagen-3.0-generate-002"
        try:
            resp = await asyncio.to_thread(
                client.models.generate_images,
                model=model_used,
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1),
            )
            img_bytes = extract_image_bytes(resp)
            record_api_usage(
                tool_name="imagen_studio",
                model=model_used,
                images_generated=1,
                note=f"generate -> {out_file.name}",
            )
        except Exception as exc:
            logger.info("Imagen generate fallback to gemini-3-pro-image (%s)", exc)
            model_used = "gemini-3-pro-image"
            resp = await asyncio.to_thread(
                generate_content_with_retry,
                client,
                model_used,
                [types.Part.from_text(text=prompt)],
                types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
                False,
                "imagen_studio",
            )
            img_bytes = extract_image_bytes(resp)

    elif action in ("inpaint", "outpaint"):
        if not source_image_path:
            raise ValueError(f"source_image_path is required for action='{action}'.")
        model_used = "imagen-3.0-capability-001"
        src_path = resolve_path(source_image_path)
        try:
            raw_ref = types.RawReferenceImage(
                reference_id=1,
                reference_image=types.Image.from_file(location=str(src_path)),
            )
            ref_images: list[Any] = [raw_ref]
            if mask_image_path:
                m_path = resolve_path(mask_image_path)
                edit_mode = (
                    types.EditMode.EDIT_MODE_INPAINT_INSERTION
                    if action == "inpaint"
                    else types.EditMode.EDIT_MODE_OUTPAINT
                )
                mask_ref = types.MaskReferenceImage(
                    reference_id=2,
                    reference_image=types.Image.from_file(location=str(m_path)),
                    config=types.MaskReferenceConfig(
                        mask_mode=types.MaskReferenceMode.MASK_MODE_USER_PROVIDED
                    ),
                )
                ref_images.append(mask_ref)
            else:
                edit_mode = types.EditMode.EDIT_MODE_DEFAULT

            resp = await asyncio.to_thread(
                client.models.edit_image,
                model=model_used,
                prompt=prompt,
                reference_images=ref_images,
                config=types.EditImageConfig(edit_mode=edit_mode, number_of_images=1),
            )
            img_bytes = extract_image_bytes(resp)
            record_api_usage(
                tool_name="imagen_studio",
                model=model_used,
                images_generated=1,
                note=f"{action} -> {out_file.name}",
            )
        except Exception as exc:
            logger.info("Imagen edit_image fallback to gemini-nano-banana-2.1 (%s)", exc)
            model_used = "gemini-nano-banana-2.1"
            parts = [load_media_part(str(src_path), max_dim=2048)]
            if mask_image_path:
                parts.append(load_media_part(mask_image_path, max_dim=2048))
            parts.append(
                types.Part.from_text(
                    text=(
                        f"Perform {action} on the source image "
                        f"(using the second image as mask if provided): {prompt}"
                    )
                )
            )
            resp = await asyncio.to_thread(
                generate_content_with_retry,
                client,
                model_used,
                parts,
                types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
                False,
                "imagen_studio",
            )
            img_bytes = extract_image_bytes(resp)

    elif action == "upscale":
        if not source_image_path:
            raise ValueError("source_image_path is required for action='upscale'.")
        model_used = "imagen-3.0-upscale-001"
        src_path = resolve_path(source_image_path)
        try:
            resp = await asyncio.to_thread(
                client.models.upscale_image,
                model=model_used,
                image=types.Image.from_file(location=str(src_path)),
                upscale_factor=upscale_factor,
            )
            img_bytes = extract_image_bytes(resp)
            record_api_usage(
                tool_name="imagen_studio",
                model=model_used,
                images_generated=1,
                note=f"upscale {upscale_factor} -> {out_file.name}",
            )
        except Exception as exc:
            logger.info("Imagen upscale_image fallback to Pillow Lanczos (%s)", exc)
            with Image.open(src_path) as im:
                scale = 4 if "4" in upscale_factor else 2
                up_im = im.resize((im.width * scale, im.height * scale), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                up_im.save(buf, format="PNG")
                img_bytes = buf.getvalue()
            model_used = "imagen-3.0-upscale-001 (lanczos-fallback)"

    if not img_bytes:
        raise RuntimeError(f"imagen_studio ({action}) returned no image bytes.")

    out_file.write_bytes(img_bytes)
    return {
        "status": "success",
        "action": action,
        "model": model_used,
        "output_path": str(out_file),
        "bytes_written": len(img_bytes),
    }


def register(mcp: Any) -> None:
    """Register image tools on the MCP server instance."""
    mcp.tool()(gemini_image_fusion)
    mcp.tool()(gemini_image_edit)
    mcp.tool()(imagen_studio)
