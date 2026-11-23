"""Gemini Decisions API tool (`gemini-decision-1`) for zero-output-token structured judgments."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any, Optional

from gemini_omni_mcp.client import api_retry, get_client
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.media import guess_mime
from gemini_omni_mcp.pricing import record_api_usage

VALID_QUESTION_TYPES = frozenset({"noul", "choice", "score"})


def _validate_questions(questions: dict[str, Any]) -> None:
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a non-empty dict mapping question_id -> spec.")
    if len(questions) > 1000:
        raise ValueError("Decisions API supports at most 1,000 questions per request.")

    for qid, spec in questions.items():
        if not isinstance(spec, dict):
            raise ValueError(f"Question {qid!r} must be a dict.")
        qtype = spec.get("type")
        if qtype not in VALID_QUESTION_TYPES:
            raise ValueError(
                f"Question {qid!r} has invalid type {qtype!r}; expected one of {sorted(VALID_QUESTION_TYPES)}."
            )
        instructions = spec.get("instructions")
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError(f"Question {qid!r} must include non-empty string 'instructions'.")
        if qtype == "choice":
            criteria = spec.get("criteria")
            if not isinstance(criteria, dict) or not (2 <= len(criteria) <= 255):
                raise ValueError(
                    f"Choice question {qid!r} must provide a 'criteria' dict with 2 to 255 options."
                )
        elif qtype == "score":
            criteria = spec.get("criteria")
            if (
                not isinstance(criteria, (list, tuple))
                or not (2 <= len(criteria) <= 255)
                or any(not isinstance(item, str) or not item.strip() for item in criteria)
            ):
                raise ValueError(
                    f"Score question {qid!r} must provide a 'criteria' list of 2 to 255 non-empty level descriptions."
                )


def _normalize_answer(raw_ans: Any) -> dict[str, Any]:
    if hasattr(raw_ans, "model_dump"):
        return raw_ans.model_dump(exclude_none=True)
    if isinstance(raw_ans, dict):
        return {k: v for k, v in raw_ans.items() if v is not None}
    out: dict[str, Any] = {}
    for attr in ("type", "noul", "choice", "score", "probabilities", "legend", "confidence"):
        val = getattr(raw_ans, attr, None)
        if val is not None:
            out[attr] = val
    return out


async def gemini_decide(
    questions: dict[str, dict[str, Any]],
    input_text: Optional[str] = None,
    media_paths: list[str] = [],
    model: str = "gemini-decision-1",
) -> dict[str, Any]:
    """Evaluate 1–1,000 typed questions (`noul`, `choice`, `score`) with zero output tokens.

    Uses `client.decisions.create` on `v1beta` (`gemini-decision-1`, $0.10 / 1M input tokens,
    $0.00 output tokens) across shared text, JSON, PDF, image, audio, or video inputs.

    Question formats:
      - `{"type": "noul", "instructions": "..."}` -> yes/no probability `0.01..0.99` + `confidence`
      - `{"type": "choice", "instructions": "...", "criteria": {"a": "...", "b": "..."}}` -> `choice` + `probabilities`
      - `{"type": "score", "instructions": "...", "criteria": ["low ...", "high ..."]}` -> weighted `score` + `probabilities`
    """
    _validate_questions(questions)
    has_text = bool(input_text and input_text.strip())
    if not has_text and not media_paths:
        raise ValueError("Provide at least one of `input_text` or `media_paths`.")

    client = get_client(context="gemini_decide", api_version="v1beta")
    if not hasattr(client, "decisions"):
        raise RuntimeError(
            "Decisions API (`client.decisions`) requires `google-genai>=3.2.0`."
        )

    payload_input: Any
    if has_text and not media_paths:
        payload_input = str(input_text)
    else:
        blocks: list[dict[str, Any]] = []
        for mp in media_paths:
            fpath = resolve_path(mp)
            if not fpath.is_file():
                raise FileNotFoundError(f"Decision media file not found: {fpath}")
            mime = guess_mime(fpath)
            file_size = fpath.stat().st_size

            if mime == "application/pdf" or fpath.suffix.lower() == ".pdf":
                if file_size > 20 * 1024 * 1024:
                    up = await asyncio.to_thread(client.files.upload, file=str(fpath))
                    blocks.append({"type": "document", "uri": up.uri, "mime_type": "application/pdf"})
                else:
                    b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
                    blocks.append({"type": "document", "data": b64, "mime_type": "application/pdf"})
            elif mime.startswith("image/"):
                b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
                blocks.append({"type": "image", "data": b64, "mime_type": mime})
            elif mime.startswith("audio/"):
                b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
                blocks.append({"type": "audio", "data": b64, "mime_type": mime})
            elif mime.startswith("video/"):
                if file_size > 15 * 1024 * 1024:
                    up = await asyncio.to_thread(client.files.upload, file=str(fpath))
                    while (
                        getattr(up, "state", None)
                        and getattr(up.state, "name", str(up.state)) == "PROCESSING"
                    ):
                        await asyncio.sleep(2.0)
                        up = await asyncio.to_thread(client.files.get, name=up.name)
                    blocks.append({"type": "video", "uri": up.uri, "mime_type": mime})
                else:
                    b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
                    blocks.append({"type": "video", "data": b64, "mime_type": mime})
            else:
                text_data = fpath.read_text(encoding="utf-8", errors="replace")
                blocks.append({"type": "text", "text": f"=== {fpath.name} ===\n{text_data}\n"})

        if has_text:
            blocks.append({"type": "text", "text": str(input_text)})
        payload_input = blocks

    @api_retry
    def _call_decisions() -> Any:
        return client.decisions.create(
            model=model,
            input=payload_input,
            questions=questions,
        )

    result = await asyncio.to_thread(_call_decisions)

    raw_answers = getattr(result, "answers", None) or {}
    answers_out: dict[str, dict[str, Any]] = {}
    if isinstance(raw_answers, dict):
        for qid, ans in raw_answers.items():
            answers_out[str(qid)] = _normalize_answer(ans)

    usage = getattr(result, "usage", None) or getattr(result, "usage_metadata", None)
    in_tokens = 0
    if usage is not None:
        in_tokens = int(
            getattr(usage, "total_input_tokens", None)
            or getattr(usage, "input_tokens", None)
            or getattr(usage, "prompt_token_count", None)
            or 0
        )
    if in_tokens == 0:
        in_tokens = max(
            50,
            len(json.dumps(questions)) // 4 + len(input_text or "") // 4 + len(media_paths) * 512,
        )

    cost_entry = record_api_usage(
        tool_name="gemini_decide",
        model=model,
        tier="standard",
        input_tokens=in_tokens,
        output_tokens=0,
        note=f"{len(questions)} decision question(s)",
    )

    return {
        "status": "success",
        "model": model,
        "question_count": len(questions),
        "answers": answers_out,
        "input_tokens": in_tokens,
        "output_tokens": 0,
        "cost_usd": cost_entry["cost_usd"],
    }


def register(mcp: Any) -> None:
    """Register Gemini Decisions API tools on the MCP server instance."""
    mcp.tool()(gemini_decide)
