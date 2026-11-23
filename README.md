<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP v2.1

**All-in-one Google GenAI Multimodal, Decisions, Analyze & Live Docs MCP Server**

*Live Docs Puller · Gemini 4 (`Carbon`, `Neon`, `Hydrogen`) & Gemma 4 · YouTube/PDF Analyze · 48h Files API · Decisions API (`gemini-decision-1`) · Deep Research · Multimodal Embeddings · Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · SRT Transcribe & Expressive TTS · Lyria 3.5 Music · Real-Time USD Budget Guard*

**English** | [Türkçe](README.tr.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D3.2.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![4-IDE Plugin](https://img.shields.io/badge/Plugin-Antigravity%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-orange.svg)](#connecting-to-your-ai-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Why MCP instead of a Standalone CLI?

Opening a separate CLI app alongside your IDE forces constant window switching, stale context, and manual file wrangling. Note that Google's legacy `google-gemini/gemini-cli` is now scoped for enterprise Code Assist and is **not** tuned for Gemini 4+, while `google-gemini/gemini-api-cli` requires shell invocations.

**`gemini-omni-mcp` embeds Google's entire November 2026 GenAI stack — *plus* a zero-cost Live Docs Puller — directly inside any MCP-compatible coding agent** (Antigravity, Claude Code, Cursor, Codex, VS Code, Claude Desktop):

| Capability | Separate CLI Window | `gemini-omni-mcp` v2.1 |
| --- | --- | --- |
| **Live Official Docs** | Manual browser tabs or separate MCP setup | Built-in `gemini_search_docs` + `gemini_fetch_doc` (`gemini-api-docs-mcp.dev` + `llms.txt` fallback) |
| **Gemini 4 & Gemma 4** | Single prompt per shell call | Full `gemini-4-carbon`, `gemini-4-neon`, `gemini-4-hydrogen`, `gemma-4-31b-it` + up to **64 parallel async workers** |
| **YouTube, PDF & Files API** | Repeated manual CLI flags | `gemini_analyze` (YouTube URLs, PDFs, video, code) + `gemini_files` (48h upload/list/get/delete) |
| **Zero-Token Decisions** | Slow text generation + brittle JSON parsing | Native `gemini_decide` (`client.decisions.create`) evaluating up to 1,000 `noul`/`choice`/`score` questions with 0 output tokens |
| **Multimodal Deliverables** | Copy-paste text outputs manually | Saves PNGs, MP4s, WAV/MP3s, `.srt`/`.md`/`.json` transcripts, reports, and contact sheets directly to workspace |
| **API Spend Safety** | No built-in USD kill-switch | Real-time usage ledger + automatic `OMNI_HARD_STOP_LIMIT_USD` lock |

---

## Tool Matrix (18 Tools: 15 Core + 3 Optional 3D/CAD)

### Core Tools (Always Enabled)

| Category | Tool | Model(s) / Upstream | Capabilities |
| --- | --- | --- | --- |
| **Live Docs** | `gemini_search_docs` | `gemini-api-docs-mcp.dev` + `llms.txt` | Search latest Google Gemini API & SDK docs by `language`, `scope`, `source`, `api` ($0.00 cost) |
| **Live Docs** | `gemini_fetch_doc` | `gemini-api-docs-mcp.dev` + `aistudio.google.com` | Fetch doc chunks by `chunk_id` or clean `.md` pages by slug/allowlisted HTTPS URL ($0.00 cost) |
| **Analyze** | `gemini_analyze` | `gemini-4-hydrogen`, `gemini-4-neon`, `gemini-4-carbon` | Single-shot Q&A over PDFs, images, audio, video, code/CSV, `files/<id>` URIs, & YouTube URLs with optional JSON Schema & Google Search |
| **Files API** | `gemini_files` | Gemini Files API (48h) | `upload` (with `PROCESSING` polling), `list`, `get`, and `delete` reusable large media & PDFs |
| **Decisions** | `gemini_decide` | `gemini-decision-1` | Single forward-pass `noul` (yes/no), `choice`, and `score` evaluations over text, PDFs, audio, images, video (0 output tokens) |
| **Agents** | `gemini_deep_research` | `deep-research-preview-04-2026`, `deep-research-max-preview-04-2026`, `antigravity-preview-09-2026` | `start`, `status`, `run_and_wait`, `cancel`, & `delete` background research tasks and save Markdown reports |
| **Embeddings** | `gemini_embed` | `gemini-embedding-2` | Unified multimodal embeddings for text, images, audio, video & PDFs + pairwise cosine similarity matrix |
| **Images** | `gemini_image_fusion` | `gemini-nano-banana-2.1`, `gemini-3.1-flash-image`, `gemini-3-pro-image` | Multi-reference fusion (up to 14 refs + 1 style anchor), turnaround/architectural/sprite presets, `0.5K`–`4K` `ImageConfig` |
| **Images** | `gemini_image_edit` | `gemini-nano-banana-2.1` | Localized editing, masked `inpaint`/`outpaint`, & `2x`/`4x` AI upscaling (with Lanczos fallback; replaces shut-down Imagen) |
| **Video** | `gemini_video_studio` | `gemini-omni-1.2-flash`, `gemini-omni-1.1-flash` | Stateful `3s`–`15s` video generation, `extend`, `edit`, `seamless_loop`, two-frame interpolation, auto URI delivery for `1080p`/`4k` |
| **Audio & STT** | `gemini_audio_studio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, `lyria-3.5` | Expressive TTS (`speech_metadata`), audio/video STT (`text`, `md`, `json`, `.srt` captions, diarization, `smart`, `custom_vocabulary`), Voices API, & Lyria 3.5 music |
| **Context** | `gemini_context_cache` | `gemini-4-carbon`, `gemini-4-hydrogen`, Gemini 3.x | Deterministic implicit prefix bundles for Gemini 4 (95% read discount) & explicit `client.caches.create` for 3.x |
| **Swarm** | `gemini_async_swarm` | `gemini-4-hydrogen`, `gemini-4-neon`, `gemini-4-carbon` | Up to 64 parallel async workers with `thinking_level` (`minimal`..`xhigh`), Code Execution, Google Search, & JSON Schema |
| **Vision QA** | `gemini_curate_refs` | `gemini-4-hydrogen` | Builds a numbered Pillow JPEG contact grid and ranks the sharpest `top_k` references in one pass |
| **FinOps & Models** | `gemini_cost_and_budget` | Offline FinOps + Live API | Real-time `summary`, 26-model `pricing_table` (incl. Gemma 4), `live_models` (`client.models.list`/`get`), `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` |

### Optional 3D / CAD RLAIF Suite (Enabled by Default; Toggleable)

Set `GEMINI_OMNI_ENABLE_3D_TOOLS=false` or pass `--no-3d-tools` to run in lean **15-tool mode**.

| Tool | Primary Model(s) | Capabilities |
| --- | --- | --- |
| `vision_extract_3d_spec` | `gemini-4-hydrogen` + PIL | Deterministic pixel region HEX sampling + structured PBR material palette, 3D proportions & triangle budget spec |
| `vision_rlaif_3d_critic` | `gemini-4-hydrogen` | Multi-angle render evaluation against references & custom `spec_rules` with concrete coordinate/mesh fixes |
| `gemini_3d_judge_and_autopatch` | `gemini-4-carbon` + `gemini-4-hydrogen` | Supreme 3D visual & script auditor; patches `.py` scripts with `ast.parse` guard, runs Blender/custom render, rolls back on error, 5-attempt circuit breaker |

---

## Live Docs Puller & Official Google Agent Setup

`gemini-omni-mcp` already integrates live documentation search (`gemini_search_docs`) and Markdown page fetching (`gemini_fetch_doc`) directly into your MCP toolset — with **zero API key required** and automatic fallback to `https://aistudio.google.com/llms.txt`.

If you also want Google's standalone official agent ecosystem tools alongside `gemini-omni-mcp`:

```bash
# Official standalone Gemini Docs MCP server
npx add-mcp "https://gemini-api-docs-mcp.dev"

# Official Gemini API coding agent skills (SDK rules & syntax)
npx skills add google-gemini/gemini-skills --skill gemini-api-dev

# Antigravity single-command plugin install (official skills + docs MCP)
agy plugin install https://github.com/google-gemini/gemini-skills

# Official zero-dependency Go CLI for direct terminal Gemini API calls
curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash
```

---

## Quickstart & Client Setup

### Prerequisites
- Python **3.11+** (or [`uv`](https://docs.astral.sh/uv/))
- `google-genai>=3.2.0` (installed automatically via `uv` or `pip`)
- A **Gemini Developer API key** (`GEMINI_API_KEY` or `GOOGLE_API_KEY`) for generation calls (Docs Puller works with no key!)

### Option A: Zero-Install via `uvx` / `uv` (Recommended)

```bash
# Run directly from GitHub with uvx
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp

# Or from a local clone
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv run gemini-omni-mcp --list-tools
```

### Option B: Install with `pip`

```bash
pip install git+https://github.com/Remilya/gemini-omni-mcp.git
gemini-omni-mcp --version
```

---

## Connecting to Your AI Agent

This repository ships with native plugin manifests for **all 4 major agent ecosystems** (`plugin.json` for Antigravity, `.claude-plugin/plugin.json` for Claude Code, `.cursor-plugin/plugin.json` for Cursor, `.codex-plugin/plugin.json` for Codex) plus `mcp_config.json` and `skills/gemini-omni/SKILL.md`.

<details open>
<summary><strong>Antigravity (Plugin Bundle or MCP Config)</strong></summary>

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

Every call's token, image, video, audio, and cache usage is recorded locally into `<workspace>/.gemini-omni/usage_ledger.json`:

- **Default limit:** `$50.00 USD` (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Automatic lock:** Reaching the cap locks the ledger, purges in-memory API keys, and raises `HardBudgetStopError` before additional calls execute.
- **FinOps controls:**
  - `gemini_cost_and_budget(action="summary")`
  - `gemini_cost_and_budget(action="live_models", model_filter="gemini-4")`
  - `gemini_cost_and_budget(action="estimate_batch", model="gemini-4-hydrogen", num_items=100, ...)`
  - `gemini_cost_and_budget(action="set_budget_limit", new_budget_limit_usd=100.0)` (pass `0` to disable)

---

## Configuration & CLI Flags

| Variable | Default | Description |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini Developer API key (or `GOOGLE_API_KEY`) |
| `OMNI_HARD_STOP_LIMIT_USD` | `50.0` | Hard USD cap; set `0` to disable |
| `GEMINI_OMNI_WORKSPACE` | Current working directory | Base directory for relative paths, cache bundles, and usage ledger |
| `GEMINI_OMNI_LEDGER_PATH` | `<workspace>/.gemini-omni/usage_ledger.json` | Custom path for the USD spend ledger JSON |
| `GEMINI_OMNI_ENABLE_3D_TOOLS` | `true` | Set `false` to run lean 15-tool mode |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Route calls through Google Cloud Vertex AI |
| `GOOGLE_CLOUD_PROJECT` | — | GCP Project ID for Vertex AI mode |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP Region for Vertex AI mode |
| `BLENDER_PATH` | Auto-detected | Blender executable path for `gemini_3d_judge_and_autopatch` |

```bash
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
