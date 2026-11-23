"""Offline unit tests for v2.1.0 additions: Analyze, Files API, SRT Transcribe, Cancel/Delete, Gemma 4, Live Models."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from gemini_omni_mcp.pricing import get_pricing_rates
from gemini_omni_mcp.tools.analyze import _validate_youtube_url, gemini_analyze
from gemini_omni_mcp.tools.audio import (
    _build_srt,
    _format_srt_timestamp,
    _format_transcript_output,
)
from gemini_omni_mcp.tools.budget import gemini_cost_and_budget
from gemini_omni_mcp.tools.files import gemini_files
from gemini_omni_mcp.tools.research import gemini_deep_research


def test_gemma4_pricing_free_tier():
    g31 = get_pricing_rates("gemma-4-31b-it", "standard")
    g26 = get_pricing_rates("gemma-4-26b-a4b-it", "standard")
    assert g31["model"] == "gemma-4-31b-it"
    assert g31["free_tier_only"] is True
    assert g31["input_per_1m"] == 0.0
    assert g31["output_per_1m"] == 0.0
    assert g26["model"] == "gemma-4-26b-a4b-it"
    assert g26["input_per_1m"] == 0.0


def test_youtube_url_validation():
    assert _validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ").startswith("https://")
    assert _validate_youtube_url("https://youtu.be/dQw4w9WgXcQ").startswith("https://")
    with pytest.raises(ValueError, match="Unsupported YouTube URL"):
        _validate_youtube_url("https://evil.example.com/watch?v=123")
    with pytest.raises(ValueError, match="missing video path"):
        _validate_youtube_url("https://youtube.com/")


def test_gemini_analyze_mocked_with_file_and_youtube(tmp_path, monkeypatch):
    notes = tmp_path / "notes.md"
    notes.write_text("# Spec\nUse Gemini 4 Hydrogen.", encoding="utf-8")
    out_report = tmp_path / "out" / "analysis.md"

    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured["model"] = model
            captured["parts_count"] = len(contents)
            return SimpleNamespace(
                text="Summary: Validated spec and video.",
                usage_metadata=SimpleNamespace(
                    prompt_token_count=200,
                    candidates_token_count=40,
                    cached_content_token_count=0,
                    thoughts_token_count=0,
                ),
            )

    monkeypatch.setattr(
        "gemini_omni_mcp.tools.analyze.get_client",
        lambda **kwargs: SimpleNamespace(models=FakeModels()),
    )

    res = asyncio.run(
        gemini_analyze(
            prompt="Summarize the spec and video.",
            input_paths=[str(notes)],
            youtube_urls=["https://www.youtube.com/watch?v=abc123"],
            output_file=str(out_report),
        )
    )
    assert res["status"] == "success"
    assert res["inputs_count"] == 1
    assert res["youtube_count"] == 1
    assert out_report.is_file()
    assert "Validated spec" in out_report.read_text(encoding="utf-8")
    assert captured["parts_count"] == 3  # text file + youtube uri + prompt


def test_gemini_files_actions_mocked(tmp_path, monkeypatch):
    sample = tmp_path / "doc.pdf"
    sample.write_bytes(b"%PDF-1.4\n%%EOF\n")

    fake_file = SimpleNamespace(
        name="files/abc123",
        display_name="doc.pdf",
        uri="https://generativelanguage.googleapis.com/v1beta/files/abc123",
        mime_type="application/pdf",
        size_bytes=16,
        state=SimpleNamespace(name="ACTIVE"),
        create_time="2026-11-23T08:00:00Z",
        expiration_time="2026-11-25T08:00:00Z",
    )

    class FakeFiles:
        def upload(self, file, config=None):
            return fake_file

        def list(self):
            return [fake_file]

        def get(self, name):
            return fake_file

        def delete(self, name):
            return None

    monkeypatch.setattr(
        "gemini_omni_mcp.tools.files.get_client",
        lambda **kwargs: SimpleNamespace(files=FakeFiles()),
    )

    up = asyncio.run(gemini_files(action="upload", file_path=str(sample), display_name="doc.pdf"))
    assert up["file"]["name"] == "files/abc123"
    assert up["file"]["state"] == "ACTIVE"

    ls = asyncio.run(gemini_files(action="list"))
    assert ls["count"] == 1
    assert ls["files"][0]["mime_type"] == "application/pdf"

    got = asyncio.run(gemini_files(action="get", file_name="files/abc123"))
    assert got["file"]["uri"].endswith("files/abc123")

    deleted = asyncio.run(gemini_files(action="delete", file_name="files/abc123"))
    assert deleted["deleted"] == "files/abc123"

    with pytest.raises(ValueError, match="file_name is required"):
        asyncio.run(gemini_files(action="get"))


def test_srt_formatting_and_transcript_outputs():
    assert _format_srt_timestamp(0.0) == "00:00:00,000"
    assert _format_srt_timestamp(65.432) == "00:01:05,432"

    srt_from_words = _build_srt(
        "Hello world from Gemini.",
        word_timings=[
            {"word": "Hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.4, "end": 0.9},
            {"word": "from", "start": 0.9, "end": 1.2},
            {"word": "Gemini.", "start": 1.2, "end": 1.8},
        ],
    )
    assert "00:00:00,000 --> 00:00:01,800" in srt_from_words
    assert "Hello world from Gemini." in srt_from_words

    srt_fallback = _build_srt("First sentence here. Second sentence follows!")
    assert srt_fallback.startswith("1\n00:00:00,000 --> ")
    assert "2\n" in srt_fallback

    md_out = _format_transcript_output("Hello!", "md", "clip.mp4")
    assert md_out.startswith("# Transcript: clip.mp4")

    json_out = json.loads(_format_transcript_output("Hello!", "json", "clip.mp4"))
    assert json_out["transcript"] == "Hello!"
    assert json_out["input"] == "clip.mp4"


def test_deep_research_cancel_and_delete_mocked(monkeypatch):
    calls = []

    class FakeInteractions:
        def cancel(self, iid):
            calls.append(("cancel", iid))

        def delete(self, iid):
            calls.append(("delete", iid))

    monkeypatch.setattr(
        "gemini_omni_mcp.tools.research.get_client",
        lambda **kwargs: SimpleNamespace(interactions=FakeInteractions()),
    )

    c_res = asyncio.run(gemini_deep_research(action="cancel", interaction_id="int_123"))
    assert c_res["status"] == "cancelled"
    assert calls[0] == ("cancel", "int_123")

    d_res = asyncio.run(gemini_deep_research(action="delete", interaction_id="int_123"))
    assert d_res["status"] == "deleted"
    assert calls[1] == ("delete", "int_123")

    with pytest.raises(ValueError, match="interaction_id is required"):
        asyncio.run(gemini_deep_research(action="cancel"))


def test_live_models_catalog_mocked(monkeypatch):
    fake_models = [
        SimpleNamespace(
            name="models/gemini-4-hydrogen",
            display_name="Gemini 4 Hydrogen",
            description="Fast everyday Gemini 4 model.",
            input_token_limit=1_000_000,
            output_token_limit=65_536,
            supported_actions=["generateContent", "interactions"],
        ),
        SimpleNamespace(
            name="models/gemini-4-carbon",
            display_name="Gemini 4 Carbon",
            description="Strongest reasoning model.",
            input_token_limit=1_000_000,
            output_token_limit=65_536,
            supported_actions=["generateContent", "interactions"],
        ),
    ]

    class FakeModelsApi:
        def list(self):
            return fake_models

        def get(self, model):
            return fake_models[0]

    monkeypatch.setattr(
        "gemini_omni_mcp.tools.budget.get_client",
        lambda **kwargs: SimpleNamespace(models=FakeModelsApi()),
    )

    filtered = asyncio.run(
        gemini_cost_and_budget(action="live_models", model_filter="hydrogen")
    )
    assert filtered["count"] == 1
    assert filtered["models"][0]["name"] == "models/gemini-4-hydrogen"

    single = asyncio.run(
        gemini_cost_and_budget(action="live_models", model_id="models/gemini-4-hydrogen")
    )
    assert single["model"]["input_token_limit"] == 1_000_000
