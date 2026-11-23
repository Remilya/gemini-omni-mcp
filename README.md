<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP

**All-in-one Google GenAI Multimodal & Agentic MCP Server**

*Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · Gemini 3.8 Flash Async Swarm · Gemini 4 Argon · Imagen 3 · Expressive TTS & Voices API · Lyria 3.5 Music · Context Caching · Real-Time USD Hard-Stop Budget Guard*

**English** | [Türkçe](README.tr.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D2.21.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Why MCP instead of Gemini CLI?

Google teams often recommend opening **Gemini CLI** alongside your editor — which means switching windows, maintaining a separate interactive prompt session, and manually copying outputs back into your repo.

**`gemini-omni-mcp` puts Google's entire multimodal & high-concurrency GenAI stack directly inside any MCP-compatible AI agent** (Antigravity, Claude Code, Cursor, Codex, VS Code, Claude Desktop) so your coding agent calls Gemini autonomously inside the same workflow:

| Capability | Separate Gemini CLI App | `gemini-omni-mcp` |
| --- | --- | --- |
| **Workflow Integration** | Separate terminal window & manual context switching | Native tool calls inside Antigravity, Claude Code, Cursor, Codex, VS Code |
| **Multimodal Output** | Mostly text/code chat loop | Saves PNGs, MP4s, WAV/MP3s, contact sheets & JSON directly to your workspace |
| **Video & Audio Studio** | Manual scripts or separate studio tools | Stateful `gemini-omni-1.2-flash` video (`extend`/`edit`/`loop`), TTS, Voice Design & Lyria 3.5 |
| **High-Concurrency Fan-Out** | Single interactive prompt at a time | `gemini_async_swarm` runs up to **64 parallel async workers** with Context Caching |
| **API Spend Safety** | No built-in USD kill-switch | Real-time usage ledger + automatic `OMNI_HARD_STOP_LIMIT_USD` lock |
| **Structured 3D / Vision QA** | Ad-hoc prompting | Strict Pydantic v2 schemas, PIL pixel sampling, & optional Blender RLAIF autopatcher |

---

## Tool Matrix (12 Tools: 9 Core + 3 Optional 3D/CAD)

### Core Multimodal, Swarm & FinOps Tools (Always Enabled)

| Tool | Primary Model(s) | Capabilities |
| --- | --- | --- |
| `gemini_image_fusion` | `gemini-nano-banana-2.1`, `gemini-3-pro-image` | Multi-reference fusion (up to 14 refs + 1 style anchor), `freeform` / `character_sheet` / `architectural_sheet` / `story_scene` / `pixel_sprite` presets, `0.5K`–`4K` `ImageConfig` |
| `gemini_image_edit` | `gemini-nano-banana-2.1` | Localized conversational image editing with up to 6 extra reference images while keeping unmentioned areas intact |
| `imagen_studio` | `imagen-3.0-generate-002`, `imagen-3.0-capability-001`, `imagen-3.0-upscale-001` | Generation, masked inpainting/outpainting, and 2x/4x upscaling with automatic Gemini / Lanczos fallback on Developer API keys |
| `gemini_video_studio` | `gemini-omni-1.2-flash`, `gemini-omni-1.1-flash` | Stateful video generation (`3s`–`15s`), extension, conversational editing, seamless loops, two-frame interpolation (`start_frame_path` → `end_frame_path`), auto URI delivery for `1080p`/`4k` |
| `gemini_audio_studio` | `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`, `lyria-3.5` | Expressive single/multi-speaker TTS via Interactions `speech_metadata`, Voices API (`voice_design`, `voice_remix`, `voice_replicate`, `voice_list`), & Lyria 3.5 music generation |
| `gemini_context_cache` | `gemini-4-argon`, `gemini-3.8-flash` | Explicit Context Caching (`client.caches.create`) for up to 95% input token savings + deterministic implicit prefix fallback bundle |
| `gemini_async_swarm` | `gemini-3.8-flash` (or any model) | Parallel `asyncio.Semaphore` worker pool (up to 64 concurrent tasks) with Code Execution, Google Search, JSON Schema, & direct `output_file` saving |
| `gemini_curate_refs` | `gemini-3.8-flash` | Builds a numbered Pillow JPEG contact grid and selects/ranks the sharpest `top_k` references in one pass |
| `gemini_cost_and_budget` | Offline FinOps Engine | Real-time spend `summary`, full 19-model `pricing_table`, `calculate_call`, `estimate_batch` (Standard vs Batch), `set_budget_limit`, `reset_ledger` |

### Optional 3D / CAD RLAIF Suite (Enabled by Default; Toggleable)

Set `GEMINI_OMNI_ENABLE_3D_TOOLS=false` or pass `--no-3d-tools` to run in lean **9-tool mode**.

| Tool | Primary Model(s) | Capabilities |
| --- | --- | --- |
| `vision_extract_3d_spec` | `gemini-3.8-flash` + PIL | Deterministic pixel region HEX sampling + structured PBR material palette, 3D proportions & triangle budget spec |
| `vision_rlaif_3d_critic` | `gemini-3.8-flash` | Multi-angle render evaluation against references & custom `spec_rules` with concrete coordinate/mesh fix items |
| `argon_judge_and_autopatch` | `gemini-4-argon` + `gemini-3.8-flash` | Supreme 3D visual & script auditor; rewrites `.py` generator scripts, validates syntax (`ast.parse`), runs headless Blender / custom `render_command`, rolls back on errors, and stops at 5 attempts |

---

## Quickstart & Client Setup

### Prerequisites
- Python **3.11+** (or [`uv`](https://docs.astral.sh/uv/))
- A **Gemini Developer API key** (`GEMINI_API_KEY` or `GOOGLE_API_KEY`) — or Vertex AI credentials

### Option A: Zero-Install via `uvx` / `uv` (Recommended)

Run straight from GitHub (or your local clone):

```bash
# Run from GitHub with uvx
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp

# Or run from a local clone
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv run gemini-omni-mcp --list-tools
```

### Option B: Install with `pip` / `pipx`

```bash
pip install git+https://github.com/Remilya/gemini-omni-mcp.git
# Or editable local install
pip install -e .

gemini-omni-mcp --version
```

---

## Connecting to Your AI Agent

<details open>
<summary><strong>Antigravity (Plugin Bundle or MCP Config)</strong></summary>

This repository ships as a ready-to-use **Antigravity Plugin** (`plugin.json`, `mcp_config.json`, `assets/logo.svg`, and `skills/gemini-omni/SKILL.md`).

Or add it directly to `~/.gemini/antigravity/mcp_config.json`:

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
        "OMNI_HARD_STOP_LIMIT_USD": "50.0",
        "GEMINI_OMNI_ENABLE_3D_TOOLS": "true"
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
<summary><strong>Cursor / Claude Desktop / Windsurf (`mcp.json`)</strong></summary>

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
<summary><strong>Codex CLI (`~/.codex/config.toml`)</strong></summary>

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
<summary><strong>VS Code / GitHub Copilot (`.vscode/mcp.json`)</strong></summary>

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

## Real-Time USD Spend Tracker & Hard-Stop Kill-Switch

Running parallel swarms or generating 1080p/4K video clips without guardrails can burn API credits fast. `gemini-omni-mcp` tracks token, image, video, audio, and cache usage on every call into `<workspace>/.gemini-omni/usage_ledger.json`:

- **Default limit:** `$50.00 USD` (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Automatic lock:** Once cumulative spend reaches the limit (or an estimated call would exceed it), `gemini-omni-mcp` marks the ledger locked, purges in-memory API keys, and raises `HardBudgetStopError` before any extra network call runs.
- **Live control via tool:**
  - Check spend & per-model breakdown: `gemini_cost_and_budget(action="summary")`
  - Forecast a batch job first: `gemini_cost_and_budget(action="estimate_batch", model="gemini-3.8-flash", num_items=100, ...)`
  - Raise or unlock budget: `gemini_cost_and_budget(action="set_budget_limit", new_budget_limit_usd=100.0)`
  - Disable hard stop: set `OMNI_HARD_STOP_LIMIT_USD=0` or pass `--budget-limit 0`

---

## Configuration Reference

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini Developer API key (or `GOOGLE_API_KEY`) |
| `OMNI_HARD_STOP_LIMIT_USD` | `50.0` | Hard USD cap; set `0` to disable |
| `GEMINI_OMNI_WORKSPACE` | Current working directory | Base directory for relative paths, cache bundles, and usage ledger |
| `GEMINI_OMNI_LEDGER_PATH` | `<workspace>/.gemini-omni/usage_ledger.json` | Custom path for the USD spend ledger JSON |
| `GEMINI_OMNI_ENABLE_3D_TOOLS` | `true` | Set `false` to disable the 3 optional 3D/CAD tools |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Set `true` to route calls through Google Cloud Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | — | GCP Project ID for Vertex AI mode |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP Region for Vertex AI mode |
| `BLENDER_PATH` | Auto-detected | Path to Blender executable for `argon_judge_and_autopatch` |

---

## CLI Flags

```bash
gemini-omni-mcp --help
gemini-omni-mcp --list-tools
gemini-omni-mcp --no-3d-tools --list-tools
gemini-omni-mcp --workspace /path/to/project --budget-limit 25.0
gemini-omni-mcp --transport streamable-http
```

---

## Development & Testing

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync --extra dev

# Run offline unit tests (no API key required)
uv run --extra dev pytest -v

# Verify tool registration
uv run gemini-omni-mcp --list-tools
```

---

## License

MIT License — see [LICENSE](LICENSE).
