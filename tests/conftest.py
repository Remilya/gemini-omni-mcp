"""Shared pytest fixtures for offline testing."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    """Isolate every test to a clean temporary workspace and deterministic env vars."""
    monkeypatch.setenv("GEMINI_OMNI_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("OMNI_WORKSPACE_DIR", raising=False)
    monkeypatch.delenv("GEMINI_OMNI_LEDGER_PATH", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OMNI_HARD_STOP_LIMIT_USD", raising=False)
    monkeypatch.delenv("GEMINI_OMNI_TOOLSETS", raising=False)
    monkeypatch.delenv("GEMINI_OMNI_ENABLE_3D_TOOLS", raising=False)
    monkeypatch.delenv("GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE", raising=False)
    monkeypatch.delenv("GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    return tmp_path
