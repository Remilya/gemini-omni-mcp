"""Offline unit tests for v2.0.0 tools: Docs Puller, Decisions API, Transcribe, and Embeddings."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from gemini_omni_mcp.config import get_ledger_path
from gemini_omni_mcp.tools.audio import gemini_audio_studio
from gemini_omni_mcp.tools.decisions import gemini_decide
from gemini_omni_mcp.tools.docs import (
    _normalize_doc_url,
    _parse_mcp_sse_json,
    gemini_fetch_doc,
    gemini_search_docs,
)
from gemini_omni_mcp.tools.embeddings import cosine_similarity


def test_parse_mcp_sse_json_handles_sse_and_plain_json():
    sse_payload = (
        "event: message\n"
        'data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\\"hits\\":[{\\"chunk_id\\":\\"c1\\"}]}"}]}}\n\n'
    )
    parsed_sse = _parse_mcp_sse_json(sse_payload)
    assert "result" in parsed_sse

    plain = _parse_mcp_sse_json('{"jsonrpc":"2.0","id":2,"result":{"ok":true}}')
    assert plain["result"]["ok"] is True


def test_normalize_doc_url_and_ssrf_guard():
    assert _normalize_doc_url("pricing") == "https://aistudio.google.com/docs/pricing.md"
    assert _normalize_doc_url("/docs/decisions-api") == "https://aistudio.google.com/docs/decisions-api.md"
    assert _normalize_doc_url("llms.txt") == "https://aistudio.google.com/llms.txt"
    assert (
        _normalize_doc_url("https://aistudio.google.com/docs/latest-model")
        == "https://aistudio.google.com/docs/latest-model.md"
    )

    with pytest.raises(ValueError, match="Disallowed doc host"):
        _normalize_doc_url("https://evil.example.com/secret.md")

    with pytest.raises(ValueError, match="Disallowed doc host"):
        _normalize_doc_url("http://aistudio.google.com/docs/pricing.md")

    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(gemini_fetch_doc(chunk_id="a", slug_or_url="pricing"))

    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(gemini_fetch_doc())


def test_gemini_search_docs_primary_and_llms_fallback(monkeypatch):
    # 1. Mock primary Streamable HTTP response
    class PrimaryClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            inner = {"hits": [{"chunk_id": "decisions.md#top", "heading": "Decisions API"}], "next_cursor": None}
            sse = f'event: message\ndata: {{"jsonrpc":"2.0","id":1,"result":{{"content":[{{"type":"text","text":{__import__("json").dumps(__import__("json").dumps(inner))}}}]}}}}\n\n'
            return httpx.Response(200, text=sse, request=httpx.Request("POST", url))

    monkeypatch.setattr("gemini_omni_mcp.tools.docs.httpx.AsyncClient", PrimaryClient)
    res = asyncio.run(gemini_search_docs("decisions", language="python", limit=5))
    assert res["status"] == "ok"
    assert res["hits"][0]["chunk_id"] == "decisions.md#top"

    # 2. Mock primary failure + fallback to llms.txt
    class FallbackClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            raise httpx.ConnectError("offline")

        async def get(self, url):
            body = (
                "- [Decisions API](https://aistudio.google.com/docs/decisions-api.md): Typed yes/no and choice questions.\n"
                "- [Audio TTS](https://aistudio.google.com/docs/speech-generation.md): TTS overview.\n"
            )
            return httpx.Response(200, text=body, request=httpx.Request("GET", url))

    monkeypatch.setattr("gemini_omni_mcp.tools.docs.httpx.AsyncClient", FallbackClient)
    fb = asyncio.run(gemini_search_docs("decisions choice", limit=3))
    assert fb["status"] == "fallback_llms_txt"
    assert fb["hits"][0]["title"] == "Decisions API"


def test_gemini_decide_validation_and_mocked_call(monkeypatch):
    with pytest.raises(ValueError, match="non-empty dict"):
        asyncio.run(gemini_decide(questions={}, input_text="hi"))

    with pytest.raises(ValueError, match="invalid type"):
        asyncio.run(
            gemini_decide(
                questions={"q1": {"type": "bogus", "instructions": "Check"}},
                input_text="hi",
            )
        )

    with pytest.raises(ValueError, match="2 to 255 options"):
        asyncio.run(
            gemini_decide(
                questions={"q1": {"type": "choice", "instructions": "Pick", "criteria": {"only_one": "desc"}}},
                input_text="hi",
            )
        )

    with pytest.raises(ValueError, match="2 to 255 non-empty level"):
        asyncio.run(
            gemini_decide(
                questions={"q1": {"type": "score", "instructions": "Rate", "criteria": ["one level"]}},
                input_text="hi",
            )
        )

    with pytest.raises(ValueError, match="Provide at least one"):
        asyncio.run(
            gemini_decide(questions={"q1": {"type": "noul", "instructions": "Damaged?"}})
        )

    class FakeDecisions:
        def create(self, model, input, questions):
            return SimpleNamespace(
                answers={
                    "is_damaged": SimpleNamespace(type="noul", noul=0.98, confidence=0.97),
                    "queue": SimpleNamespace(
                        type="choice",
                        choice="replacements",
                        probabilities={"replacements": 0.96, "billing": 0.04},
                        confidence=0.96,
                    ),
                },
                usage=SimpleNamespace(total_input_tokens=1_000_000),
            )

    monkeypatch.setattr(
        "gemini_omni_mcp.tools.decisions.get_client",
        lambda **kwargs: SimpleNamespace(decisions=FakeDecisions()),
    )

    out = asyncio.run(
        gemini_decide(
            input_text="Cracked mug arrived today.",
            questions={
                "is_damaged": {"type": "noul", "instructions": "Is the item damaged?"},
                "queue": {
                    "type": "choice",
                    "instructions": "Route ticket",
                    "criteria": {"replacements": "Damaged goods", "billing": "Invoices"},
                },
            },
        )
    )
    assert out["status"] == "success"
    assert out["output_tokens"] == 0
    assert out["cost_usd"] == pytest.approx(0.10, rel=1e-4)
    assert out["answers"]["is_damaged"]["noul"] == 0.98
    assert out["answers"]["queue"]["choice"] == "replacements"

    saved = json.loads(get_ledger_path().read_text(encoding="utf-8"))
    assert saved["totals"]["total_cost_usd"] == pytest.approx(0.10, rel=1e-4)


def test_transcribe_validation_rules(tmp_path):
    wav_p = tmp_path / "sample.wav"
    wav_p.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")

    with pytest.raises(ValueError, match="input_audio_path is required"):
        asyncio.run(gemini_audio_studio(mode="transcribe"))

    with pytest.raises(ValueError, match="custom_vocabulary cannot be combined"):
        asyncio.run(
            gemini_audio_studio(
                mode="transcribe",
                input_audio_path=str(wav_p),
                enable_diarization=True,
                custom_vocabulary=["Gemini"],
            )
        )

    with pytest.raises(ValueError, match="require transcription_mode='verbatim'"):
        asyncio.run(
            gemini_audio_studio(
                mode="transcribe",
                input_audio_path=str(wav_p),
                transcription_mode="smart",
                enable_word_timestamps=True,
            )
        )


def test_cosine_similarity_math():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])
