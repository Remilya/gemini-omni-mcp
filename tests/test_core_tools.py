"""Offline tests for v3.0 core tools (`gemini_docs`, `gemini_image`, `gemini_audio`, `gemini_analyze`, `gemini_budget`) and opt-in tools."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from gemini_omni_mcp.tools import analyze as analyze_mod
from gemini_omni_mcp.tools import audio as audio_mod
from gemini_omni_mcp.tools import budget as budget_mod
from gemini_omni_mcp.tools import docs as docs_mod
from gemini_omni_mcp.tools import files as files_mod
from gemini_omni_mcp.tools import image as image_mod
from gemini_omni_mcp.tools import research as research_mod


class _MockHttpClient:
    def __init__(self, post_fn=None, get_fn=None):
        self._post_fn = post_fn
        self._get_fn = get_fn

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        return self._post_fn(url, **kwargs)

    async def get(self, url, **kwargs):
        return self._get_fn(url, **kwargs)


def test_gemini_docs_search_fallback_fetch_and_ssrf(monkeypatch):
    # 1) Search success over remote MCP SSE/JSON
    sse_body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{\\"hits\\":[{\\"title\\":\\"Gemini 4\\",\\"url\\":\\"https://ai.google.dev/gemini-api/docs/models\\"}]}"}]}}\n\n'
    monkeypatch.setattr(
        docs_mod.httpx,
        "AsyncClient",
        lambda **kw: _MockHttpClient(
            post_fn=lambda url, **kw2: SimpleNamespace(
                text=sse_body, raise_for_status=lambda: None
            )
        ),
    )
    res_search = asyncio.run(docs_mod.gemini_docs(action="search", query="Gemini 4"))
    assert res_search["status"] == "ok"
    assert res_search["hits"][0]["title"] == "Gemini 4"

    # 2) Search fallback to llms.txt on remote failure
    def fail_post(url, **kw):
        raise RuntimeError("remote MCP timeout")

    llms_txt = "- [Interactions API](https://ai.google.dev/gemini-api/docs/interactions): Stateful agents\n"
    monkeypatch.setattr(
        docs_mod.httpx,
        "AsyncClient",
        lambda **kw: _MockHttpClient(
            post_fn=fail_post,
            get_fn=lambda url, **kw2: SimpleNamespace(
                text=llms_txt, raise_for_status=lambda: None
            ),
        ),
    )
    res_fallback = asyncio.run(docs_mod.gemini_docs(action="search", query="interactions"))
    assert res_fallback["status"] == "fallback_llms_txt"
    assert len(res_fallback["hits"]) == 1

    # 3) Fetch slug & SSRF block
    monkeypatch.setattr(
        docs_mod.httpx,
        "AsyncClient",
        lambda **kw: _MockHttpClient(
            get_fn=lambda url, **kw2: SimpleNamespace(
                text="# Pricing", url=url, raise_for_status=lambda: None
            )
        ),
    )
    res_fetch = asyncio.run(docs_mod.gemini_docs(action="fetch", slug_or_url="pricing"))
    assert res_fetch["status"] == "ok"
    assert res_fetch["url"] == "https://aistudio.google.com/docs/pricing.md"

    with pytest.raises(ValueError, match="Disallowed doc host"):
        asyncio.run(docs_mod.gemini_docs(action="fetch", slug_or_url="https://evil.example/payload.md"))

    with pytest.raises(ValueError, match="Provide exactly one"):
        asyncio.run(docs_mod.gemini_docs(action="fetch"))


def test_gemini_image_generate_and_upscale_fallback(tmp_path, monkeypatch):
    src = tmp_path / "src.png"
    Image.new("RGB", (32, 32), (10, 120, 220)).save(src, format="PNG")
    out_gen = tmp_path / "gen.png"
    out_up = tmp_path / "up.png"

    fake_client = SimpleNamespace()
    monkeypatch.setattr(image_mod, "get_client", lambda **kw: fake_client)

    def fake_generate(client, model, contents, config, enable_long_decode, tool_name):
        if "Sharpen" in str(contents[-1]) or "upscale" in str(contents[-1]):
            raise RuntimeError("transient image error triggers lanczos fallback")
        return SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[
                            SimpleNamespace(
                                inline_data=SimpleNamespace(
                                    data=b"\x89PNG\r\n\x1a\nFAKE",
                                    mime_type="image/png",
                                )
                            )
                        ]
                    )
                )
            ],
            text="",
        )

    monkeypatch.setattr(image_mod, "generate_content_with_retry", fake_generate)

    gen_res = asyncio.run(
        image_mod.gemini_image(
            action="generate",
            prompt="Watercolor lantern card",
            output_path=str(out_gen),
            preset="story_scene",
        )
    )
    assert gen_res["status"] == "success"
    assert gen_res["action"] == "generate"
    assert out_gen.read_bytes().startswith(b"\x89PNG")

    up_res = asyncio.run(
        image_mod.gemini_image(
            action="upscale",
            source_image_path=str(src),
            output_path=str(out_up),
            upscale_factor="x2",
        )
    )
    assert up_res["status"] == "success"
    assert "lanczos-fallback" in up_res["model"]
    with Image.open(out_up) as up_im:
        assert up_im.size == (64, 64)


def test_gemini_audio_transcribe_validation_and_srt(tmp_path, monkeypatch):
    aud = tmp_path / "clip.wav"
    aud.write_bytes(b"RIFF" + b"\x00" * 44)
    srt_out = tmp_path / "captions.srt"

    with pytest.raises(ValueError, match="custom_vocabulary cannot be combined"):
        asyncio.run(
            audio_mod.gemini_audio(
                mode="transcribe",
                input_audio_path=str(aud),
                custom_vocabulary=["Gemini"],
                enable_diarization=True,
            )
        )

    fake_inter = SimpleNamespace(
        output_text="Hello Gemini 4.",
        word_timings=[
            {"word": "Hello", "start_sec": 0.0, "end_sec": 0.5},
            {"word": "Gemini", "start_sec": 0.5, "end_sec": 1.0},
            {"word": "4.", "start_sec": 1.0, "end_sec": 1.5},
        ],
    )
    fake_client = SimpleNamespace(
        files=SimpleNamespace(
            upload=lambda file: SimpleNamespace(name="files/a1", uri="https://x/files/a1", state="ACTIVE"),
            get=lambda name: SimpleNamespace(name=name, state="ACTIVE", size_bytes=48),
        ),
        interactions=SimpleNamespace(create=lambda **kw: fake_inter),
    )
    monkeypatch.setattr(audio_mod, "get_client", lambda **kw: fake_client)

    res = asyncio.run(
        audio_mod.gemini_audio(
            mode="transcribe",
            input_audio_path=str(aud),
            enable_word_timestamps=True,
            output_format="srt",
            output_transcript_path=str(srt_out),
        )
    )
    assert res["status"] == "success"
    assert res["output_transcript_path"] == str(srt_out)
    srt_text = srt_out.read_text(encoding="utf-8")
    assert "00:00:00,000 -->" in srt_text
    assert "Hello Gemini 4." in srt_text


def test_gemini_analyze_and_gemma_thinking_omission(tmp_path, monkeypatch):
    note = tmp_path / "notes.md"
    note.write_text("# Spec\nUse Gemini 4 Neon.\n", encoding="utf-8")
    seen_configs: list[object] = []

    monkeypatch.setattr(analyze_mod, "get_client", lambda **kw: SimpleNamespace())

    def fake_generate(client, model, contents, config, enable_long_decode, tool_name):
        seen_configs.append((model, config.thinking_config))
        return SimpleNamespace(text="Summary OK")

    monkeypatch.setattr(analyze_mod, "generate_content_with_retry", fake_generate)

    res1 = asyncio.run(
        analyze_mod.gemini_analyze(
            prompt="Summarize",
            input_paths=[str(note)],
            model="gemini-4-hydrogen",
            thinking_level="minimal",
        )
    )
    assert res1["text"] == "Summary OK"
    assert str(seen_configs[0][1].thinking_level).endswith("LOW")

    res2 = asyncio.run(
        analyze_mod.gemini_analyze(
            prompt="Summarize",
            input_paths=[str(note)],
            model="gemma-4-31b-it",
            thinking_level="high",
        )
    )
    assert res2["text"] == "Summary OK"
    assert seen_configs[1][1] is None

    with pytest.raises(ValueError, match="Unsupported YouTube URL"):
        asyncio.run(
            analyze_mod.gemini_analyze(
                prompt="Check video",
                youtube_urls=["https://notyoutube.example/watch?v=123"],
            )
        )


def test_gemini_budget_live_models_and_optin_files_research(tmp_path, monkeypatch):
    fake_models = [
        SimpleNamespace(name="models/gemini-4-neon", display_name="Gemini 4 Neon", supported_generation_methods=["generateContent"]),
        SimpleNamespace(name="models/gemma-4-31b-it", display_name="Gemma 4 31B", supported_generation_methods=["generateContent"]),
    ]
    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            list=lambda: fake_models,
            get=lambda model: fake_models[0],
        ),
        files=SimpleNamespace(
            list=lambda: [SimpleNamespace(name="files/f1", display_name="demo.txt", mime_type="text/plain", size_bytes=12, state="ACTIVE", uri="https://x/f1")],
        ),
        interactions=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(id="dr-1", status="in_progress"),
            get=lambda iid: SimpleNamespace(id=iid, status="completed", output_text="# Research Report"),
            cancel=lambda iid: None,
            delete=lambda iid: None,
        ),
    )

    monkeypatch.setattr(budget_mod, "get_client", lambda **kw: fake_client)
    monkeypatch.setattr(files_mod, "get_client", lambda **kw: fake_client)
    monkeypatch.setattr(research_mod, "get_client", lambda **kw: fake_client)

    live_res = asyncio.run(budget_mod.gemini_budget(action="live_models", model_filter="neon"))
    assert live_res["count"] == 1
    assert live_res["models"][0]["name"] == "models/gemini-4-neon"

    files_res = asyncio.run(files_mod.gemini_files(action="list"))
    assert files_res["count"] == 1

    report_out = tmp_path / "report.md"
    dr_res = asyncio.run(
        research_mod.gemini_deep_research(
            action="status",
            interaction_id="dr-1",
            output_markdown_path=str(report_out),
        )
    )
    assert dr_res["status"] == "completed"
    assert report_out.read_text(encoding="utf-8") == "# Research Report"
