<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP

**All-in-One Google GenAI Multimodal, Agentic & Live Docs MCP Server**

*Live Docs Puller · Gemini 4 (`Neon`, `Hydrogen`, opt-in `Carbon`) & Gemma 4 · YouTube/PDF Analyze · Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · SRT Transcribe, TTS & Voices API · Lyria 3.5 Music · Modular Swarm, Research & 3D Toolsets · Real-Time USD Budget Guard*

**English** | [Türkçe](README.tr.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D3.2.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![4-IDE Plugin](https://img.shields.io/badge/Plugin-Antigravity%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-orange.svg)](#connecting-to-your-ai-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Why MCP instead of a Standalone CLI?

Opening a separate CLI app alongside your IDE forces constant window switching, stale context, and manual file wrangling. Google's official `google-gemini/gemini-cli` focuses on enterprise Code Assist chat rather than agent-callable Nano Banana image fusion, stateful Omni video loops, or automated FinOps guardrails, while `google-gemini/gemini-api-cli` requires manual shell invocations.

**`gemini-omni-mcp` embeds Google's late-2026 GenAI stack — *plus* a zero-cost Live Docs Puller — directly inside any MCP-compatible coding agent** with a lean **6-tool default surface** (`--toolsets core`) that keeps context windows clean, plus opt-in `swarm`, `research`, and `3d` packs:

| Capability | Separate CLI Window | `gemini-omni-mcp` |
| --- | --- | --- |
| **Live Official Docs** | Manual browser tabs or extra MCP setup | Built-in `gemini_docs` (`gemini-api-docs-mcp.dev` + `llms.txt` fallback + SSRF host allowlist, `$0.00`) |
| **Gemini 4 & Gemma 4** | Single prompt per shell invocation | `gemini_analyze` with `gemini-4-hydrogen`, `gemini-4-neon`, opt-in `gemini-4-carbon`, `gemma-4-31b-it` + opt-in **64-worker async swarm** |
| **Lean Context Footprint** | Heavy all-in tool dumps | **6 core tools** loaded by default; load `swarm` (`+3`), `research` (`+1`), or `3d` (`+3`) only when needed |
| **Multimodal Deliverables** | Copy-paste outputs manually | Writes PNGs, MP4s, WAV/MP3s, `.srt`/`.md`/`.json` transcripts, and reports directly inside the sandboxed workspace |
| **SDK & Security Guardrails** | Unbounded disk access / raw SDK pitfalls | Workspace path sandbox, `shell=False` Blender subprocesses, explicit `v1beta` routing, and automatic `thinking_level` clamping |
| **API Spend Safety** | No local USD kill-switch | Real-time ledger (`usage_ledger.json`) + automatic `OMNI_HARD_STOP_LIMIT_USD` lock + live `models.list` inspector |

---

## Tool Architecture (6 Default Core Tools + Modular Opt-In Toolsets)

By default, `gemini-omni-mcp` registers **6 consolidated core tools** to keep agent token overhead minimal. Enable specialized modules anytime via `--toolsets` or `GEMINI_OMNI_TOOLSETS` (`all` exposes all **13 tools**).

### Core Toolset (Default — 6 Tools)

| Category | Tool | Model(s) / Upstream | Capabilities |
| --- | --- | --- | --- |
| **Image Studio** | `gemini_image` | `gemini-nano-banana-2.1` | `action="generate"` (text-to-image + up to 14 refs + style anchor + `freeform`, `character_sheet`, `architectural_sheet`, `story_scene`, `pixel_sprite` presets) or `edit`, `inpaint`, `outpaint`, `upscale` (with Pillow Lanczos fallback) |
| **Video Studio** | `gemini_video` | `gemini-omni-1.2-flash` (`v1beta` Interactions) | Stateful `generate`, `extend`, `edit`, and `seamless_loop` (`3s`–`15s`, `360p`–`4k`, start/end frame interpolation, auto URI delivery) |
| **Audio & Voice** | `gemini_audio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, Voices API, `lyria-3.5` (`v1beta`) | Multi-speaker `tts` (`speech_metadata`), `transcribe` (`text`/`md`/`json`/`srt` + speaker diarization + word timestamps), custom `voice_design`/`remix`/`replicate`/`list`/`get`/`delete`, and `music` |
| **Analyze** | `gemini_analyze` | `gemini-4-hydrogen` (default), `gemini-4-neon`, opt-in `gemini-4-carbon`, `gemma-4-31b-it` | Single-shot analysis of PDFs, images, audio, video, code/CSV, `files/<id>` URIs, and YouTube URLs with Google Search, Code Execution, and structured JSON output |
| **Live Docs** | `gemini_docs` | `gemini-api-docs-mcp.dev` + `aistudio.google.com` | `action="search"` (live SDK/API search with automatic `llms.txt` fallback) & `action="fetch"` (chunk ID or HTTPS doc slug; zero API key required, `$0.00` cost) |
| **FinOps & Models** | `gemini_budget` | Local Ledger + `client.models` | `summary`, `pricing_table`, `live_models` (`models.list`/`get`), `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` |

### Modular Opt-In Toolsets (`--toolsets` / `GEMINI_OMNI_TOOLSETS`)

| Toolset | Tools Included | Capabilities | Enable Command |
| --- | --- | --- | --- |
| **`swarm`** (`+3`) | `gemini_async_swarm`, `gemini_context_cache`, `gemini_files` | Up to 64 parallel Gemini 4 workers, deterministic implicit 95%-discount prefix bundles / explicit caching, and 48h Files API upload/list/get/delete | `--toolsets core,swarm` |
| **`research`** (`+1`) | `gemini_deep_research` | Managed background research agents (`deep-research-preview-04-2026`, `antigravity-preview-09-2026`) with `start`, `status`, `run_and_wait`, `cancel`, `delete` over `v1beta` | `--toolsets core,research` |
| **`3d`** (`+3`, **OFF by default**) | `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `gemini_3d_judge_and_autopatch` | PBR `#RRGGBB` + 3D proportion extraction, multi-angle RLAIF critique, and `gemini-4-neon` judge + `shell=False` headless Blender autopatcher (5-retry circuit breaker) | `--toolsets core,3d` |
| **`all`** (`13` total) | All toolsets above | Loads `core` + `swarm` + `research` + `3d` together | `--toolsets all` |

---

## Live Docs Puller & Official Google Companion Tools

`gemini_docs` pulls live Google Gemini API & SDK documentation **without an API key** (`$0.00` cost), automatically falling back to `https://aistudio.google.com/llms.txt` keyword ranking if the upstream Docs MCP is unreachable, while blocking disallowed schemes/hosts and open-redirect SSRF targets.

You can also install Google's standalone developer tools alongside `gemini-omni-mcp`:

```bash
# Search live docs with the standalone MCP server
npx add-mcp "https://gemini-api-docs-mcp.dev"

# Add official Gemini API agent skills (current SDK syntax & rules)
npx skills add google-gemini/gemini-skills --skill gemini-api-dev

# In Antigravity, install both with one plugin
agy plugin install https://github.com/google-gemini/gemini-skills

# Call the Gemini API from the terminal via Google's standalone CLI
curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash
```

---

## Quick Start

### Option A: Zero-Install Run with `uvx` (Recommended)

```bash
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp --list-tools
```

### Option B: Run From Local Clone with `uv`

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync

# Default lean mode (6 core tools)
uv run gemini-omni-mcp --list-tools

# Include swarm & research toolsets (+4 -> 10 tools)
uv run gemini-omni-mcp --toolsets core,swarm,research --list-tools

# Enable all 13 tools (including optional 3D/CAD suite)
uv run gemini-omni-mcp --toolsets all --list-tools
```

### Option C: Install with `pip`

```bash
pip install git+https://github.com/Remilya/gemini-omni-mcp.git
gemini-omni-mcp --version
```

---

## Connecting to Your AI Agent

This repository ships with native plugin manifests for **all 4 major agent ecosystems** (`plugin.json` for Antigravity, `.claude-plugin/plugin.json` for Claude Code, `.cursor-plugin/plugin.json` for Cursor, `.codex-plugin/plugin.json` for Codex) plus `mcp_config.json` and `skills/gemini-omni/SKILL.md`.

> To load opt-in toolsets alongside the 6 default core tools, add `"--toolsets", "core,swarm,research"` (or `"--toolsets", "all"`) to `args`, or set `"GEMINI_OMNI_TOOLSETS": "core,swarm,research"` in `env`.

<details open>
<summary><strong>Antigravity (Plugin Bundle or <code>mcp_config.json</code>)</strong></summary>

Add directly to `~/.gemini/antigravity/mcp_config.json`:

```json
{
  "mcpServers": {
    "gemini-omni": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY",
        "GEMINI_OMNI_WORKSPACE": "/path/to/your/workspace",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0",
        "GEMINI_OMNI_TOOLSETS": "core"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code (CLI)</strong></summary>

```bash
claude mcp add gemini-omni \
  -e GEMINI_API_KEY="YOUR_GEMINI_API_KEY" \
  -e OMNI_HARD_STOP_LIMIT_USD="50.0" \
  -- uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp
```

</details>

<details>
<summary><strong>Cursor / Claude Desktop / Windsurf (<code>mcp.json</code>)</strong></summary>

```json
{
  "mcpServers": {
    "gemini-omni": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Remilya/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Codex CLI (<code>~/.codex/config.toml</code>)</strong></summary>

```toml
[mcp_servers.gemini-omni]
command = "uvx"
args = ["--from", "git+https://github.com/Remilya/gemini-omni-mcp", "gemini-omni-mcp"]

[mcp_servers.gemini-omni.env]
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
OMNI_HARD_STOP_LIMIT_USD = "50.0"
```

</details>

<details>
<summary><strong>VS Code / GitHub Copilot (<code>.vscode/mcp.json</code>)</strong></summary>

```json
{
  "servers": {
    "gemini-omni": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Remilya/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "${input:gemini_api_key}",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "gemini_api_key",
      "description": "Google Gemini API Key",
      "password": true
    }
  ]
}
```

</details>

---

## Real-Time USD Spend Tracker & Security Guardrails

### FinOps Kill-Switch

Every call's token, image, video, audio, and cache usage is recorded locally into `<workspace>/.gemini-omni/usage_ledger.json`:

- **Default limit:** `$50.00` USD (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Automatic lock:** Reaching the cap locks the ledger, purges in-memory API keys, and raises `HardBudgetStopError` before additional calls run.
- **FinOps controls:** `gemini_budget(action="summary")`, `live_models`, `estimate_batch`, `set_budget_limit` (pass `0` to disable), and `reset_ledger`.
- **Cloud safety recommendation:** Always pair local ledger tracking with an official monthly billing cap in Google Cloud / Google AI Studio.

### Built-In Security & SDK Hardening

- **Workspace Path Sandbox:** `resolve_path()` restricts file reads and writes to `GEMINI_OMNI_WORKSPACE` by default (`GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false`), blocking `../` traversal and external paths unless explicitly opted in.
- **Subprocess Hardening (`3d` toolset):** `gemini_3d_judge_and_autopatch` runs headless Blender with `shell=False` argument lists, and rejects custom `render_command` execution unless `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=true` is explicitly set.
- **`google-genai >= 3.2.0` (`3.6.1+`) Compatibility:** Routes `interactions` and `voices` calls explicitly through `api_version="v1beta"` and normalizes `thinking_level` per model (`minimal` -> `low` on Gemini 4; `xhigh` -> `high` on Carbon/Argon/3.x; `ThinkingConfig` omitted cleanly on Gemma 4).

---

## Configuration & CLI Flags

Copy [`.env.example`](.env.example) to `.env` in your workspace (or pass via your MCP client's `env` block):

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini Developer API key (or `GOOGLE_API_KEY`) |
| `OMNI_HARD_STOP_LIMIT_USD` | `50.0` | Hard USD cap; set `0` to disable |
| `GEMINI_OMNI_TOOLSETS` | `core` | Comma-separated toolsets: `core`, `swarm`, `research`, `3d`, `all` |
| `GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE` | `false` | Set `true` to allow reads/writes outside `GEMINI_OMNI_WORKSPACE` |
| `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD` | `false` | Set `true` to allow custom `render_command` in `gemini_3d_judge_and_autopatch` |
| `GEMINI_OMNI_WORKSPACE` | Current working directory | Base workspace directory for relative paths, caches, and usage ledger |
| `GEMINI_OMNI_LEDGER_PATH` | `<workspace>/.gemini-omni/usage_ledger.json` | Custom path for the USD spend ledger JSON |
| `GEMINI_OMNI_ENABLE_3D_TOOLS` | `false` | Legacy compatibility flag (superseded by `GEMINI_OMNI_TOOLSETS`) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Route calls through Google Cloud Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | — | GCP Project ID for Vertex AI mode |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP Region for Vertex AI mode |
| `BLENDER_PATH` | Auto-detected | Blender executable path for `gemini_3d_judge_and_autopatch` |

```bash
gemini-omni-mcp --list-tools
gemini-omni-mcp --toolsets core,swarm,research --list-tools
gemini-omni-mcp --toolsets all --list-tools
gemini-omni-mcp --workspace /path/to/project --budget-limit 25.0
gemini-omni-mcp --allow-outside-workspace --transport streamable-http
```

---

## Development & Testing

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync --extra dev

# Run offline unit tests (all network/API calls mocked; no API key required)
uv run --extra dev pytest -v

# Verify tool registration
uv run gemini-omni-mcp --list-tools
```

---

## License

MIT License — see [LICENSE](LICENSE).
