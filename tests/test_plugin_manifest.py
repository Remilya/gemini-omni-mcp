"""Validation tests for all 4 IDE plugin manifests, mcp_config, and SKILL.md."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PLUGIN_TOP_LEVEL_KEYS = {
    "name",
    "displayName",
    "version",
    "description",
    "logo",
    "suggestedPrompts",
    "author",
    "homepage",
    "repository",
    "disabled",
}


def test_antigravity_plugin_json_strict_schema():
    plugin_path = REPO_ROOT / "plugin.json"
    assert plugin_path.is_file()
    data = json.loads(plugin_path.read_text(encoding="utf-8"))

    unknown_keys = set(data.keys()) - ALLOWED_PLUGIN_TOP_LEVEL_KEYS
    assert not unknown_keys, f"Unsupported top-level keys in plugin.json: {unknown_keys}"
    assert data["name"] == "gemini-omni"
    assert data["version"] == "2.1.0"
    assert isinstance(data["description"], str) and len(data["description"]) > 10
    assert isinstance(data["suggestedPrompts"], list)
    assert 1 <= len(data["suggestedPrompts"]) <= 3

    logo_path = REPO_ROOT / data["logo"]
    assert logo_path.is_file(), f"Missing plugin logo: {logo_path}"


def test_cross_ide_plugin_manifests():
    for rel_path, expects_skills in (
        (".claude-plugin/plugin.json", False),
        (".cursor-plugin/plugin.json", True),
        (".codex-plugin/plugin.json", True),
    ):
        p = REPO_ROOT / rel_path
        assert p.is_file(), f"Missing manifest: {p}"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["name"] == "gemini-omni"
        assert data["version"] == "2.1.0"
        assert data["license"] == "MIT"
        assert data["repository"] == "https://github.com/Remilya/gemini-omni-mcp"
        if expects_skills:
            assert data.get("skills") == "./skills"


def test_mcp_config_json_valid():
    cfg_path = REPO_ROOT / "mcp_config.json"
    assert cfg_path.is_file()
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert "gemini-omni" in data["mcpServers"]
    server_cfg = data["mcpServers"]["gemini-omni"]
    assert "command" in server_cfg and "args" in server_cfg


def test_skill_markdown_frontmatter():
    skill_path = REPO_ROOT / "skills" / "gemini-omni" / "SKILL.md"
    assert skill_path.is_file()
    content = skill_path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    parts = content.split("---", 2)
    assert len(parts) >= 3
    frontmatter = parts[1]
    assert "name: gemini-omni" in frontmatter
    assert "description:" in frontmatter
