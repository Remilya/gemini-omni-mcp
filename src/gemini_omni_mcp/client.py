"""Unified Google GenAI client initialization and exponential-backoff retry helpers."""

from __future__ import annotations

import os
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from gemini_omni_mcp.config import load_dotenv_if_present
from gemini_omni_mcp.pricing import (
    HardBudgetStopError,
    enforce_hard_budget_limit,
    record_api_usage,
)


def get_client(
    estimated_next_cost_usd: float = 0.0,
    context: str = "",
    api_version: Optional[str] = None,
) -> genai.Client:
    """Create a `google.genai.Client` after enforcing the hard-stop USD budget limit.

    Supports both:
      - Gemini Developer API (`GOOGLE_API_KEY` or `GEMINI_API_KEY`)
      - Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true/1/yes`)
    Pass `api_version="v1beta"` for beta APIs such as Decisions, Transcribe, and Deep Research.
    """
    load_dotenv_if_present(override=False)
    enforce_hard_budget_limit(estimated_next_cost_usd, context=context)

    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    api_key = (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()

    http_opts_kwargs: dict[str, Any] = {"timeout": 75_000}
    if api_version:
        http_opts_kwargs["api_version"] = api_version
    http_opts = types.HttpOptions(**http_opts_kwargs)
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        if project:
            return genai.Client(
                vertexai=True,
                project=project,
                location=location,
                http_options=http_opts,
            )
        if api_key:
            return genai.Client(vertexai=True, api_key=api_key, http_options=http_opts)
        return genai.Client(vertexai=True, http_options=http_opts)

    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY or GOOGLE_API_KEY environment variable "
            "(and GOOGLE_GENAI_USE_VERTEXAI is not enabled)."
        )
    return genai.Client(api_key=api_key, http_options=http_opts)


def is_retryable_exception(exc: BaseException) -> bool:
    """Return True for HTTP 429/500/502/503/504 or transient network errors; never retries HardBudgetStopError."""
    if isinstance(exc, HardBudgetStopError):
        return False
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, genai_errors.APIError):
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code in (429, 500, 502, 503, 504):
            return True
    msg = str(exc).upper()
    if "HARD STOP LIMIT" in msg:
        return False
    return any(
        token in msg
        for token in (
            "429",
            "503",
            "RESOURCE_EXHAUSTED",
            "UNAVAILABLE",
            "DEADLINE_EXCEEDED",
            "RATE_LIMIT",
            "TOO MANY REQUESTS",
        )
    )


api_retry = retry(
    retry=retry_if_exception(is_retryable_exception),
    wait=wait_exponential(multiplier=1.5, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)


@api_retry
def generate_content_with_retry(
    client: genai.Client,
    model: str,
    contents: Any,
    config: types.GenerateContentConfig,
    enable_long_decode: bool = False,
    tool_name: str = "generate_content",
) -> Any:
    """Execute `client.models.generate_content` with retry backoff and ledger recording.

    When `enable_long_decode=True`, continues generation up to 3 times if `MAX_TOKENS` is hit.
    """
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    record_api_usage(
        tool_name=tool_name,
        model=model,
        tier="standard",
        response_obj=response,
    )
    if not enable_long_decode:
        return response

    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return response

    finish_reason = str(getattr(candidates[0], "finish_reason", ""))
    if "MAX_TOKENS" not in finish_reason:
        return response

    accumulated_text = getattr(response, "text", "") or ""
    conv_contents = list(contents) if isinstance(contents, list) else [contents]
    for _ in range(3):
        conv_contents.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=accumulated_text[-4000:])],
            )
        )
        conv_contents.append(
            types.Part.from_text(
                text="Continue outputting the exact remaining content from where you stopped, without repeating previous lines."
            )
        )
        cont_resp = client.models.generate_content(
            model=model,
            contents=conv_contents,
            config=config,
        )
        record_api_usage(
            tool_name=f"{tool_name}_long_decode_cont",
            model=model,
            tier="standard",
            response_obj=cont_resp,
        )
        chunk = getattr(cont_resp, "text", "") or ""
        accumulated_text += chunk
        cands = getattr(cont_resp, "candidates", None) or []
        if not cands or "MAX_TOKENS" not in str(getattr(cands[0], "finish_reason", "")):
            break

    try:
        if response.candidates and response.candidates[0].content.parts:
            response.candidates[0].content.parts = [
                types.Part.from_text(text=accumulated_text)
            ]
    except Exception:
        pass
    return response
