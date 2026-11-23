"""Gemini TTS, Custom Voices API, and Lyria 3.5 music generation tools."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Literal, Optional

from google.genai import types

from gemini_omni_mcp.client import generate_content_with_retry, get_client
from gemini_omni_mcp.config import logger, resolve_path
from gemini_omni_mcp.media import (
    extract_audio_bytes,
    guess_mime,
    save_pcm_or_audio_bytes,
)
from gemini_omni_mcp.pricing import record_api_usage


async def gemini_audio_studio(
    mode: Literal[
        "tts",
        "music",
        "voice_design",
        "voice_remix",
        "voice_replicate",
        "voice_list",
        "voice_get",
        "voice_delete",
    ] = "tts",
    prompt_or_text: str = "",
    output_audio_path: str = "output/gemini_audio.wav",
    voice_style_prompt: Optional[str] = None,
    voice_name: str = "Charon",
    tts_model: Literal["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"] = "gemini-3.8-flash-tts",
    speakers: Optional[list[dict[str, str]]] = None,
    dialogue_turns: Optional[list[dict[str, str]]] = None,
    voice_config_params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Voice synthesis (`gemini-3.8-flash-tts`), Voices API (`design`/`remix`/`replicate`), & Lyria 3.5 music.

    - `mode="tts"`: Uses Interactions API `speech_metadata` annotations so stage directions are
      never spoken aloud; supports single-speaker (`voice_name`) and multi-speaker (`speakers` + `dialogue_turns`).
    - `mode="voice_design"` / `"voice_remix"` / `"voice_replicate"`: Creates custom persistent voices.
    - `mode="voice_list"` / `"voice_get"` / `"voice_delete"`: Manages the Voice Library.
    - `mode="music"`: Composes audio via `lyria-3.5` / `lyria-3-pro-preview` / `lyria-3-clip-preview`.
    """
    client = get_client(context=f"gemini_audio_studio:{mode}")
    out_file = (
        resolve_path(output_audio_path)
        if output_audio_path
        else resolve_path("output/gemini_audio.wav")
    )
    vparams = voice_config_params or {}

    if mode == "voice_list":
        filter_kwargs: dict[str, Any] = {"page_size": int(vparams.get("page_size", 25))}
        for k in (
            "language_code",
            "region_code",
            "accent",
            "gender",
            "pitch",
            "persona",
            "contexts",
            "type_",
            "search",
        ):
            val = vparams.get(k)
            if val is not None:
                if k != "search" and isinstance(val, str):
                    val = [val]
                filter_kwargs[k] = val
        resp = await asyncio.to_thread(client.voices.list, **filter_kwargs)
        voices_out = []
        for v in getattr(resp, "voices", None) or []:
            if hasattr(v, "model_dump"):
                voices_out.append(v.model_dump(exclude_none=True))
            else:
                voices_out.append(
                    {
                        "id": getattr(v, "id", None) or getattr(v, "name", None),
                        "display_name": getattr(v, "display_name", None),
                        "type": str(getattr(v, "type", "")),
                        "gender": str(getattr(v, "gender", "")),
                        "pitch": str(getattr(v, "pitch", "")),
                        "language_code": getattr(v, "language_code", None),
                        "persona": getattr(v, "persona", None),
                        "description": getattr(v, "description", None),
                    }
                )
        return {
            "status": "success",
            "mode": "voice_list",
            "count": len(voices_out),
            "voices": voices_out,
        }

    if mode == "voice_get":
        target_name = vparams.get("id") or vparams.get("name") or voice_name
        v = await asyncio.to_thread(client.voices.get, target_name)
        v_dict = (
            v.model_dump(exclude_none=True)
            if hasattr(v, "model_dump")
            else {"id": getattr(v, "id", target_name)}
        )
        v_dict.pop("sample_audio", None)
        return {"status": "success", "mode": "voice_get", "voice": v_dict}

    if mode == "voice_delete":
        target_name = vparams.get("id") or vparams.get("name") or voice_name
        await asyncio.to_thread(client.voices.delete, target_name)
        return {"status": "success", "mode": "voice_delete", "deleted": target_name}

    if mode in ("voice_design", "voice_remix", "voice_replicate"):
        store_flag = bool(vparams.get("store", True))
        voice_payload: dict[str, Any] = {
            "model": tts_model,
            "display_name": vparams.get("display_name", "Custom Studio Voice"),
            "language_code": vparams.get("language_code", "en-US"),
        }
        if vparams.get("gender"):
            voice_payload["gender"] = vparams["gender"]
        if vparams.get("sample_text"):
            voice_payload["sample_text"] = vparams["sample_text"]

        if mode in ("voice_design", "voice_remix"):
            voice_payload["type"] = "prompted"
            prompted_cfg: dict[str, Any] = {
                "input": prompt_or_text
                or vparams.get("input", "Warm, natural storytelling voice.")
            }
            if mode == "voice_remix" or vparams.get("base_voice"):
                prompted_cfg["base_voice"] = vparams.get("base_voice", voice_name)
            voice_payload["prompted"] = prompted_cfg
        else:
            voice_payload["type"] = "replicated"
            src_p = resolve_path(vparams["source_audio_path"])
            con_p = resolve_path(vparams["consent_audio_path"])
            voice_payload["replicated"] = {
                "source_audio": {
                    "data": base64.b64encode(src_p.read_bytes()).decode("ascii"),
                    "mime_type": guess_mime(src_p),
                },
                "consent_audio": {
                    "data": base64.b64encode(con_p.read_bytes()).decode("ascii"),
                    "mime_type": guess_mime(con_p),
                },
            }

        v_resp = await asyncio.to_thread(
            client.voices.create,
            store=store_flag,
            voice=voice_payload,
        )
        created_voice_id = (
            getattr(v_resp, "id", None)
            or getattr(v_resp, "name", None)
            or getattr(v_resp, "voice_key", None)
        )
        sample_saved = None
        sample_aud = getattr(v_resp, "sample_audio", None)
        if sample_aud and getattr(sample_aud, "data", None):
            raw_s = sample_aud.data
            s_bytes = base64.b64decode(raw_s) if isinstance(raw_s, str) else bytes(raw_s)
            s_mime = getattr(sample_aud, "mime_type", "audio/wav") or "audio/wav"
            await asyncio.to_thread(save_pcm_or_audio_bytes, s_bytes, s_mime, out_file)
            sample_saved = str(out_file)

        return {
            "status": "success",
            "mode": mode,
            "model": tts_model,
            "voice_id": created_voice_id,
            "display_name": getattr(
                v_resp, "display_name", voice_payload.get("display_name")
            ),
            "sample_text": getattr(v_resp, "sample_text", None),
            "sample_audio_path": sample_saved,
        }

    if not prompt_or_text.strip() and not dialogue_turns:
        raise ValueError("prompt_or_text (or dialogue_turns) cannot be empty.")

    if mode == "tts":
        model_id = tts_model
        try:
            content_blocks: list[dict[str, Any]] = []
            if dialogue_turns:
                for turn in dialogue_turns:
                    ann: dict[str, Any] = {"type": "speech_metadata"}
                    if turn.get("speaker"):
                        ann["speaker"] = turn["speaker"]
                    if turn.get("style"):
                        ann["style"] = turn["style"]
                    content_blocks.append(
                        {
                            "type": "text",
                            "text": turn.get("text", ""),
                            "annotations": [ann],
                        }
                    )
            else:
                text_block: dict[str, Any] = {"type": "text", "text": prompt_or_text}
                if voice_style_prompt:
                    text_block["annotations"] = [
                        {"type": "speech_metadata", "style": voice_style_prompt}
                    ]
                content_blocks.append(text_block)

            if speakers:
                speech_cfg: Any = {"speakers": speakers}
            else:
                speech_cfg = [{"voice": voice_name}]

            interaction = await asyncio.to_thread(
                client.interactions.create,
                model=model_id,
                input=[{"type": "user_input", "content": content_blocks}],
                response_format={"type": "audio"},
                generation_config={"speech_config": speech_cfg},
            )
            out_aud = getattr(interaction, "output_audio", None)
            raw_a = getattr(out_aud, "data", None) if out_aud else None
            if raw_a:
                audio_bytes = (
                    base64.b64decode(raw_a) if isinstance(raw_a, str) else bytes(raw_a)
                )
                mime = getattr(out_aud, "mime_type", "audio/wav") or "audio/wav"
                await asyncio.to_thread(
                    save_pcm_or_audio_bytes, audio_bytes, mime, out_file
                )
                dur_est = max(1.0, out_file.stat().st_size / 48000.0)
                cost_entry = record_api_usage(
                    tool_name="gemini_audio_studio",
                    model=model_id,
                    tier="standard",
                    input_tokens=max(20, len(prompt_or_text) // 4),
                    audio_seconds=round(dur_est, 2),
                    note=f"tts ({voice_name}) -> {out_file.name}",
                )
                return {
                    "status": "success",
                    "mode": "tts",
                    "api": "interactions",
                    "model": model_id,
                    "voice_name": voice_name,
                    "output_audio_path": str(out_file),
                    "bytes_written": out_file.stat().st_size,
                    "cost_usd": cost_entry["cost_usd"],
                }
        except Exception as inter_exc:
            logger.info("Interactions TTS fallback to generate_content (%s)", inter_exc)

        tts_text = (
            f"{voice_style_prompt}: {prompt_or_text}"
            if voice_style_prompt
            else prompt_or_text
        )
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        )
        resp = await asyncio.to_thread(
            generate_content_with_retry,
            client,
            model_id,
            [types.Part.from_text(text=tts_text)],
            config,
            False,
            "gemini_audio_studio",
        )
        audio_bytes, mime = extract_audio_bytes(resp)
        if not audio_bytes:
            raise RuntimeError(f"{model_id} did not return audio bytes.")
        await asyncio.to_thread(save_pcm_or_audio_bytes, audio_bytes, mime, out_file)
        return {
            "status": "success",
            "mode": "tts",
            "api": "generate_content",
            "model": model_id,
            "voice_name": voice_name,
            "output_audio_path": str(out_file),
            "bytes_written": out_file.stat().st_size,
        }

    # mode == "music" (`lyria-3.5` / `lyria-3-pro-preview` / `lyria-3-clip-preview`)
    music_model = str(vparams.get("music_model", "lyria-3.5"))
    candidate_models = [music_model] + [
        m
        for m in ("lyria-3.5", "lyria-3-pro-preview", "lyria-3-clip-preview")
        if m != music_model
    ]
    last_err: Optional[Exception] = None
    for candidate_model in candidate_models:
        try:
            interaction = await asyncio.to_thread(
                client.interactions.create,
                model=candidate_model,
                input=prompt_or_text,
            )
            out_aud = getattr(interaction, "output_audio", None)
            raw_a = getattr(out_aud, "data", None) if out_aud else None
            if not raw_a and hasattr(interaction, "steps"):
                for step in getattr(interaction, "steps", []) or []:
                    for part in getattr(step, "content", []) or []:
                        if getattr(part, "type", "") == "audio" and getattr(
                            part, "data", None
                        ):
                            raw_a = part.data
                            out_aud = part
                            break
            if raw_a:
                audio_bytes = (
                    base64.b64decode(raw_a) if isinstance(raw_a, str) else bytes(raw_a)
                )
                mime = getattr(out_aud, "mime_type", "audio/mp3") or "audio/mp3"
                await asyncio.to_thread(
                    save_pcm_or_audio_bytes, audio_bytes, mime, out_file
                )
                cost_entry = record_api_usage(
                    tool_name="gemini_audio_studio",
                    model=candidate_model,
                    tier="standard",
                    songs_generated=1,
                    note=f"music ({candidate_model}) -> {out_file.name}",
                )
                return {
                    "status": "success",
                    "mode": "music",
                    "api": "interactions",
                    "model": candidate_model,
                    "output_audio_path": str(out_file),
                    "bytes_written": out_file.stat().st_size,
                    "structure_or_lyrics": getattr(interaction, "output_text", None),
                    "cost_usd": cost_entry["cost_usd"],
                }
        except Exception as inter_exc:
            last_err = inter_exc

        try:
            config = types.GenerateContentConfig(response_modalities=["AUDIO", "TEXT"])
            resp = await asyncio.to_thread(
                generate_content_with_retry,
                client,
                candidate_model,
                [types.Part.from_text(text=prompt_or_text)],
                config,
                False,
                "gemini_audio_studio",
            )
            audio_bytes, mime = extract_audio_bytes(resp)
            if audio_bytes:
                await asyncio.to_thread(
                    save_pcm_or_audio_bytes, audio_bytes, mime, out_file
                )
                return {
                    "status": "success",
                    "mode": "music",
                    "api": "generate_content",
                    "model": candidate_model,
                    "output_audio_path": str(out_file),
                    "bytes_written": out_file.stat().st_size,
                }
        except Exception as exc:
            last_err = exc
            continue

    raise RuntimeError(f"Music generation with Lyria 3.5 models failed: {last_err}")


def register(mcp: Any) -> None:
    """Register audio tools on the MCP server instance."""
    mcp.tool()(gemini_audio_studio)
