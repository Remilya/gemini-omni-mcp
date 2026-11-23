"""Image, audio, response extraction, and Blender lookup helpers."""

from __future__ import annotations

import base64
import io
import mimetypes
import os
import re
import shutil
import wave
from pathlib import Path
from typing import Any, Optional

from google.genai import types
from PIL import Image

from gemini_omni_mcp.config import resolve_path


def guess_mime(path: Path) -> str:
    """Infer MIME type from a file path with reliable media fallbacks."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
    }.get(ext, "application/octet-stream")


def load_media_part(path_str: str, max_dim: Optional[int] = None) -> types.Part:
    """Load an image or media file into a `types.Part`, optionally downscaling large images."""
    path = resolve_path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Media file not found: {path}")
    mime = guess_mime(path)
    if max_dim and mime.startswith("image/"):
        with Image.open(path) as im:
            im_conv = im.convert("RGBA" if mime == "image/png" else "RGB")
            if max(im_conv.size) > max_dim:
                im_conv.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            fmt = "PNG" if mime == "image/png" else "JPEG"
            im_conv.save(buf, format=fmt, quality=92)
            return types.Part.from_bytes(data=buf.getvalue(), mime_type=mime)
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def extract_json_text(response: Any) -> str:
    """Extract a JSON object string from a `GenerateContentResponse`, stripping markdown fences."""
    if getattr(response, "text", None):
        txt = response.text.strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```(?:json|python)?\s*", "", txt)
            txt = re.sub(r"\s*```$", "", txt)
        first_brace = txt.find("{")
        last_brace = txt.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return txt[first_brace : last_brace + 1]
        return txt

    chunks: list[str] = []
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            if getattr(part, "text", None):
                chunks.append(part.text)
    combined = "\n".join(chunks).strip()
    if combined.startswith("```"):
        combined = re.sub(r"^```(?:json|python)?\s*", "", combined)
        combined = re.sub(r"\s*```$", "", combined)
    first_brace = combined.find("{")
    last_brace = combined.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return combined[first_brace : last_brace + 1]
    return combined


def extract_image_bytes(response: Any) -> Optional[bytes]:
    """Extract generated image bytes from `generate_content` or `generate_images` responses."""
    if hasattr(response, "generated_images") and response.generated_images:
        img_obj = response.generated_images[0].image
        if hasattr(img_obj, "image_bytes") and img_obj.image_bytes:
            return img_obj.image_bytes

    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return bytes(data)
    return None


def extract_audio_bytes(response: Any) -> tuple[Optional[bytes], str]:
    """Extract inline audio bytes and MIME type from a `generate_content` response."""
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                mime = getattr(inline, "mime_type", "audio/wav") or "audio/wav"
                raw = base64.b64decode(data) if isinstance(data, str) else bytes(data)
                return raw, mime
    return None, "audio/wav"


def save_pcm_or_audio_bytes(raw_bytes: bytes, mime_type: str, out_path: Path) -> None:
    """Save audio bytes to `out_path`, wrapping raw L16 PCM in a 24kHz mono WAV header if needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if (
        "pcm" in mime_type.lower()
        or "l16" in mime_type.lower()
        or (out_path.suffix.lower() == ".wav" and not raw_bytes.startswith(b"RIFF"))
    ):
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(raw_bytes)
    else:
        out_path.write_bytes(raw_bytes)


def find_blender_executable() -> str:
    """Locate a local Blender executable across Windows, macOS, and Linux."""
    env_blender = os.environ.get("BLENDER_PATH") or os.environ.get("BLENDER_EXE")
    if env_blender and Path(env_blender).is_file():
        return env_blender

    which_b = shutil.which("blender")
    if which_b:
        return which_b

    mac_app = Path("/Applications/Blender.app/Contents/MacOS/Blender")
    if mac_app.is_file():
        return str(mac_app)

    bf_dir = Path(r"C:\Program Files\Blender Foundation")
    if bf_dir.is_dir():
        exes = sorted(bf_dir.glob("Blender*/blender.exe"), reverse=True)
        if exes:
            return str(exes[0])

    steam_blender = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe")
    if steam_blender.is_file():
        return str(steam_blender)

    return "blender"
