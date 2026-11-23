"""Gemini TTS, Custom Voices API, Gemini 3.5 Transcribe STT, and Lyria 3.5 music generation."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any, Literal, Optional

from google.genai import types

from gemini_omni_mcp.client import api_retry, generate_content_with_retry, get_client
from gemini_omni_mcp.config import logger, resolve_path
from gemini_omni_mcp.media import (
    extract_audio_bytes,
    guess_mime,
    save_pcm_or_audio_bytes,
)
from gemini_omni_mcp.pricing import record_api_usage


def _format_srt_timestamp(seconds: float) -> str:
    """Format non-negative seconds as an SRT timestamp (`HH:MM:SS,mmm`)."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _parse_offset_seconds(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip().lower()
        if s.endswith("s"):
            s = s[:-1]
        try:
            return float(s)
        except ValueError:
            return None
    secs = getattr(val, "seconds", None)
    nanos = getattr(val, "nanos", None)
    if secs is not None or nanos is not None:
        return float(secs or 0) + float(nanos or 0) / 1_000_000_000.0
    return None


def _extract_word_timings(interaction: Any) -> list[dict[str, Any]]:
    timings: list[dict[str, Any]] = []
    for out_item in getattr(interaction, "outputs", None) or []:
        for ann in getattr(out_item, "annotations", None) or []:
            word = getattr(ann, "word", None) or getattr(ann, "text", None)
            start = _parse_offset_seconds(
                getattr(ann, "start_offset", None)
                or getattr(ann, "start_time", None)
                or getattr(ann, "start", None)
            )
            end = _parse_offset_seconds(
                getattr(ann, "end_offset", None)
                or getattr(ann, "end_time", None)
                or getattr(ann, "end", None)
            )
            if word and start is not None and end is not None:
                timings.append({"word": str(word).strip(), "start": start, "end": end})
    return timings


def _wrap_caption_chunks(text: str, max_chars: int = 42) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    cur: list[str] = []
    for w in words:
        candidate = " ".join(cur + [w])
        if cur and len(candidate) > max_chars:
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _build_srt(
    transcript: str,
    word_timings: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Build valid SubRip (`.srt`) captions from word timings or estimated sentence pacing."""
    cues: list[tuple[float, float, str]] = []

    if word_timings:
        cur_words: list[str] = []
        cue_start: Optional[float] = None
        cue_end: float = 0.0
        for wt in word_timings:
            w = str(wt.get("word", "")).strip()
            if not w:
                continue
            w_start = float(wt.get("start", cue_end))
            w_end = max(w_start + 0.1, float(wt.get("end", w_start + 0.35)))
            candidate = " ".join(cur_words + [w])
            if cur_words and (len(candidate) > 42 or (w_end - (cue_start or 0.0)) > 4.0):
                cues.append((cue_start or 0.0, cue_end, " ".join(cur_words)))
                cur_words = [w]
                cue_start = w_start
                cue_end = w_end
            else:
                if cue_start is None:
                    cue_start = w_start
                cur_words.append(w)
                cue_end = w_end
        if cur_words:
            cues.append((cue_start or 0.0, cue_end, " ".join(cur_words)))
    else:
        clean = transcript.strip()
        if not clean:
            return ""
        sentences = [s.strip() for s in re.split(r"\n+|(?<=[.!?])\s+", clean) if s.strip()]
        cursor = 0.0
        for sent in sentences:
            for chunk in _wrap_caption_chunks(sent, max_chars=42):
                dur = max(1.2, round(len(chunk.split()) / 2.8, 3))
                cues.append((cursor, round(cursor + dur, 3), chunk))
                cursor = round(cursor + dur, 3)

    blocks = [
        f"{idx}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{text}"
        for idx, (start, end, text) in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _format_transcript_output(
    transcript: str,
    output_format: str,
    input_label: str,
    word_timings: Optional[list[dict[str, Any]]] = None,
) -> str:
    fmt = output_format.strip().lower()
    if fmt == "md":
        return f"# Transcript: {input_label}\n\n{transcript}\n"
    if fmt == "json":
        return json.dumps(
            {
                "model": "gemini-3.5-transcribe",
                "input": input_label,
                "transcript": transcript,
                "word_timings": word_timings or [],
            },
            indent=2,
            ensure_ascii=False,
        )
    if fmt == "srt":
        return _build_srt(transcript, word_timings)
    return transcript


async def gemini_audio_studio(
    mode: Literal[
        "tts",
        "transcribe",
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
    input_audio_path: Optional[str] = None,
    transcription_mode: Literal["verbatim", "smart"] = "verbatim",
    enable_diarization: bool = False,
    enable_word_timestamps: bool = False,
    custom_vocabulary: Optional[list[str]] = None,
    language_codes: Optional[list[str]] = None,
    output_format: Literal["text", "md", "json", "srt"] = "text",
    output_transcript_path: Optional[str] = None,
) -> dict[str, Any]:
    """Voice synthesis, audio/video transcription (Text/MD/JSON/SRT), Voices API, & Lyria 3.5 music.

    - `mode="tts"`: Uses `gemini-3.8-flash-tts` Interactions API `speech_metadata` annotations
      so stage directions are never spoken aloud; supports single/multi-speaker dialogue.
    - `mode="transcribe"`: Uses `gemini-3.5-transcribe` on local audio/video files or `files/<id>` URIs;
      outputs `text`, `md`, `json`, or `.srt` captions and optionally writes `output_transcript_path`.
    - `mode="voice_design"` / `"voice_remix"` / `"voice_replicate"` / `"voice_list"` / `"voice_get"` / `"voice_delete"`:
      Manages custom vocal personas via `client.voices`.
    - `mode="music"`: Composes audio via `lyria-3.5` / `lyria-3-pro-preview` / `lyria-3-clip-preview`.
    """
    if mode == "transcribe":
        if not input_audio_path or not input_audio_path.strip():
            raise ValueError("input_audio_path is required for mode='transcribe'.")
        if custom_vocabulary and (enable_diarization or enable_word_timestamps):
            raise ValueError(
                "custom_vocabulary cannot be combined with enable_diarization or enable_word_timestamps."
            )
        if transcription_mode == "smart" and (enable_diarization or enable_word_timestamps):
            raise ValueError(
                "enable_diarization and enable_word_timestamps require transcription_mode='verbatim'."
            )

        raw_in = input_audio_path.strip()
        is_files_uri = raw_in.startswith("files/")
        in_path = None if is_files_uri else resolve_path(raw_in)
        if in_path is not None and not in_path.is_file():
            raise FileNotFoundError(f"Audio/video file not found: {in_path}")

        client = get_client(context="gemini_audio_studio:transcribe", api_version="v1beta")
        if is_files_uri:
            uploaded = await asyncio.to_thread(client.files.get, name=raw_in)
            input_label = raw_in
            source_ref = raw_in
            size_bytes = int(getattr(uploaded, "size_bytes", None) or 100_000)
        else:
            assert in_path is not None
            uploaded = await asyncio.to_thread(client.files.upload, file=str(in_path))
            while (
                getattr(uploaded, "state", None)
                and getattr(uploaded.state, "name", str(uploaded.state)) == "PROCESSING"
            ):
                await asyncio.sleep(1.5)
                uploaded = await asyncio.to_thread(client.files.get, name=uploaded.name)
            input_label = in_path.name
            source_ref = str(in_path)
            size_bytes = in_path.stat().st_size

        mode_cfg: dict[str, Any] = {"type": transcription_mode}
        if enable_diarization:
            mode_cfg["diarization_mode"] = "speaker"
        if enable_word_timestamps:
            mode_cfg["timestamp_granularities"] = ["word"]

        t_cfg: dict[str, Any] = {"mode": mode_cfg}
        if custom_vocabulary:
            t_cfg["custom_vocabulary"] = list(custom_vocabulary)[:1000]
        if language_codes is not None:
            t_cfg["language_codes"] = list(language_codes)

        @api_retry
        def _call_transcribe() -> Any:
            return client.interactions.create(
                model="gemini-3.5-transcribe",
                input=[uploaded],
                generation_config={"transcription_config": t_cfg},
            )

        interaction = await asyncio.to_thread(_call_transcribe)
        transcript = (getattr(interaction, "output_text", None) or "").strip()
        if not transcript:
            for out_item in getattr(interaction, "outputs", None) or []:
                t = getattr(out_item, "text", None)
                if isinstance(t, str) and t.strip():
                    transcript = t.strip()
                    break

        word_timings = _extract_word_timings(interaction)
        formatted = _format_transcript_output(
            transcript=transcript,
            output_format=output_format,
            input_label=input_label,
            word_timings=word_timings,
        )

        saved_transcript_path: Optional[str] = None
        if output_transcript_path:
            out_t = resolve_path(output_transcript_path)
            out_t.parent.mkdir(parents=True, exist_ok=True)
            out_t.write_text(formatted, encoding="utf-8")
            saved_transcript_path = str(out_t)

        usage = getattr(interaction, "usage", None) or getattr(interaction, "usage_metadata", None)
        in_tok = int(getattr(usage, "total_input_tokens", None) or getattr(usage, "input_tokens", None) or 0) if usage else 0
        out_tok = int(getattr(usage, "total_output_tokens", None) or getattr(usage, "output_tokens", None) or 0) if usage else 0
        if in_tok == 0:
            in_tok = max(100, size_bytes // 1000)
        if out_tok == 0:
            out_tok = max(20, len(transcript) // 4)

        cost_entry = record_api_usage(
            tool_name="gemini_audio_studio",
            model="gemini-3.5-transcribe",
            tier="standard",
            input_tokens=in_tok,
            output_tokens=out_tok,
            note=f"transcribe ({transcription_mode}, {output_format}) <- {input_label}",
        )
        return {
            "status": "success",
            "mode": "transcribe",
            "model": "gemini-3.5-transcribe",
            "transcription_mode": transcription_mode,
            "output_format": output_format,
            "input_audio_path": source_ref,
            "output_transcript_path": saved_transcript_path,
            "transcript": transcript,
            "formatted_output": formatted if output_format != "text" else None,
            "cost_usd": cost_entry["cost_usd"],
        }

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
    """Register audio, TTS, Voices, STT transcription, and Lyria tools on the MCP server."""
    mcp.tool()(gemini_audio_studio)
