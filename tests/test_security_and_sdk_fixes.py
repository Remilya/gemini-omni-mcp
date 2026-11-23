"""Offline tests for v3.0 security guardrails and google-genai >= 3.2 SDK fixes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from gemini_omni_mcp.client import build_thinking_config, normalize_thinking_level
from gemini_omni_mcp.config import resolve_path
from gemini_omni_mcp.tools import audio as audio_mod
from gemini_omni_mcp.tools import cad_3d as cad_mod
from gemini_omni_mcp.tools import research as research_mod
from gemini_omni_mcp.tools import video as video_mod


def test_workspace_sandbox_blocks_traversal_and_external_paths(tmp_path, monkeypatch):
    # Inside workspace succeeds
    inside = resolve_path("nested/asset.png")
    assert inside == (tmp_path / "nested" / "asset.png").resolve()

    # Relative path traversal outside workspace fails by default
    with pytest.raises(PermissionError, match="outside workspace"):
        resolve_path("../outside_secret.txt")

    # External absolute path fails by default
    external_dir = tmp_path.parent / "external_dir"
    with pytest.raises(PermissionError, match="outside workspace"):
        resolve_path(str(external_dir / "file.txt"))

    # Explicit env opt-in permits outside workspace
    monkeypatch.setenv("GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE", "true")
    resolved_ext = resolve_path(str(external_dir / "file.txt"))
    assert resolved_ext == (external_dir / "file.txt").resolve()


def test_thinking_level_normalization_across_models():
    # Gemini 4 clamps minimal -> low, preserves xhigh for Neon & Hydrogen
    assert normalize_thinking_level("gemini-4-neon", "minimal") == "low"
    assert normalize_thinking_level("gemini-4-neon", "xhigh") == "xhigh"
    assert normalize_thinking_level("gemini-4-hydrogen", "minimal") == "low"
    assert normalize_thinking_level("gemini-4-hydrogen", "XHIGH") == "xhigh"

    # Carbon & Argon max at high
    assert normalize_thinking_level("gemini-4-carbon", "xhigh") == "high"
    assert normalize_thinking_level("gemini-4-argon", "xhigh") == "high"
    assert normalize_thinking_level("gemini-4-carbon", "minimal") == "low"

    # Older Gemini 3.x clamps xhigh -> high, allows minimal
    assert normalize_thinking_level("gemini-3.5-flash-lite", "minimal") == "minimal"
    assert normalize_thinking_level("gemini-3.5-flash-lite", "xhigh") == "high"

    # Gemma 4 omits ThinkingConfig entirely
    assert normalize_thinking_level("gemma-4-31b-it", "high") is None
    assert build_thinking_config("gemma-4-31b-it", "high") is None

    # Off/none returns None
    assert build_thinking_config("gemini-4-neon", "none") is None
    cfg = build_thinking_config("gemini-4-neon", "minimal")
    assert cfg is not None and str(cfg.thinking_level).endswith("LOW")

    with pytest.raises(ValueError, match="Unsupported thinking_level"):
        normalize_thinking_level("gemini-4-neon", "galaxy_brain")


def test_v1beta_routing_for_video_audio_and_research(tmp_path, monkeypatch):
    seen_api_versions: list[tuple[str, str | None]] = []

    class FakeClient:
        def __init__(self) -> None:
            self.voices = SimpleNamespace(list=lambda **kw: SimpleNamespace(voices=[]))
            self.interactions = SimpleNamespace(
                create=lambda **kw: SimpleNamespace(
                    id="inter-1",
                    status="completed",
                    output_video=SimpleNamespace(data=b"FAKE_MP4"),
                    output_audio=SimpleNamespace(data=b"RIFF" + b"\x00" * 40, mime_type="audio/wav"),
                    outputs=[],
                ),
                cancel=lambda tid: None,
            )

    fake_client = FakeClient()

    def fake_get_client(*, estimated_next_cost_usd=0.0, context="", api_version=None):
        seen_api_versions.append((context, api_version))
        return fake_client

    monkeypatch.setattr(video_mod, "get_client", fake_get_client)
    monkeypatch.setattr(audio_mod, "get_client", fake_get_client)
    monkeypatch.setattr(research_mod, "get_client", fake_get_client)

    asyncio.run(video_mod.gemini_video(prompt="Neon shrine", output_mp4_path="out/v.mp4"))
    asyncio.run(audio_mod.gemini_audio(mode="voice_list"))
    asyncio.run(audio_mod.gemini_audio(mode="tts", prompt_or_text="Hello world", output_audio_path="out/a.wav"))
    asyncio.run(research_mod.gemini_deep_research(action="start", prompt="Compare Gemini 4 models"))

    assert seen_api_versions == [
        ("gemini_video:generate", "v1beta"),
        ("gemini_audio:voice_list", "v1beta"),
        ("gemini_audio:tts", "v1beta"),
        ("gemini_deep_research:start", "v1beta"),
    ]


def test_custom_render_command_blocked_by_default_and_uses_shell_false(tmp_path, monkeypatch):
    script = tmp_path / "build.py"
    script.write_text("x = 1\n", encoding="utf-8")
    render = tmp_path / "render.png"
    Image.new("RGB", (32, 32), (120, 120, 120)).save(render, format="PNG")

    # Blocked upfront when GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD is off
    with pytest.raises(PermissionError, match="GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD"):
        asyncio.run(
            cad_mod.gemini_3d_judge_and_autopatch(
                subject_id="test_obj",
                render_image_path=str(render),
                reference_image_paths=[],
                cad_script_path=str(script),
                render_command="blender -b -P build.py",
            )
        )

    # When enabled, runs with shell=False and list args
    monkeypatch.setenv("GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD", "true")
    sub_calls: list[tuple[object, bool]] = []

    class FakeAioModels:
        async def generate_content(self, *, model, contents, config):
            if "Patch" in str(contents[-1]) or model == "gemini-4-hydrogen":
                return SimpleNamespace(text="x = 2\n")
            return SimpleNamespace(
                text='{"score": 60, "passed": false, "rear_view_verdict": "ok", "geometry_and_topology_audit": "needs bevel", "visual_bugs": ["sharp edge"], "rewritten_script": null}'
            )

    fake_client = SimpleNamespace(aio=SimpleNamespace(models=FakeAioModels()))
    monkeypatch.setattr(cad_mod, "get_client", lambda **kw: fake_client)

    def fake_run(cmd_args, *, shell, cwd, capture_output, text, timeout):
        sub_calls.append((cmd_args, shell))
        return SimpleNamespace(returncode=0, stdout="rendered ok", stderr="")

    monkeypatch.setattr(cad_mod.subprocess, "run", fake_run)

    res = asyncio.run(
        cad_mod.gemini_3d_judge_and_autopatch(
            subject_id="test_obj",
            render_image_path=str(render),
            reference_image_paths=[],
            cad_script_path=str(script),
            render_command="blender -b -P build.py",
            max_judge_iterations=1,
        )
    )
    assert res["iterations_run"] == 1
    assert sub_calls == [(["blender", "-b", "-P", "build.py"], False)]
