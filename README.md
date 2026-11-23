# gemini-omni-mcp v3.0

**Lean, hardened all-in-one Google GenAI Multimodal & Agentic MCP Server** built for Claude Code, Cursor, Codex, Antigravity, and any Model Context Protocol client.

- **English** | [Türkçe (README.tr.md)](README.tr.md)

---

## What Changed in v3.0.0

1. **Lean 6-Tool Core by Default (`--toolsets core`):** Slashed default tool bloat from 18 tools down to **6 high-impact core tools** (`gemini_image`, `gemini_video`, `gemini_audio`, `gemini_analyze`, `gemini_docs`, `gemini_budget`) to keep agent context windows fast and focused.
2. **Modular Opt-In Toolsets:** Load heavy automation (`swarm`: `+3`), managed agents (`research`: `+1`), or Blender/3D CAD RLAIF (`3d`: `+3`, **OFF by default**) only when needed via `--toolsets` or `GEMINI_OMNI_TOOLSETS` (`all` loads all 13 tools).
3. **`google-genai >= 3.2.0` (`3.6.1+`) SDK Hardening:**
   - Explicit `api_version="v1beta"` routing for `interactions` and `voices` endpoints (`gemini_video`, `gemini_audio`, `gemini_deep_research`).
   - Model-aware `thinking_level` clamping (`normalize_thinking_level` / `build_thinking_config`): clamps `minimal -> low` on Gemini 4, `xhigh -> high` on Carbon/Argon/3.x, and omits `ThinkingConfig` on Gemma 4.
4. **Security-by-Default Guardrails:**
   - **Workspace Path Sandbox:** `resolve_path()` blocks reads/writes outside `GEMINI_OMNI_WORKSPACE` by default (`GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false`).
   - **Subprocess Hardening:** `gemini_3d_judge_and_autopatch` uses `shell=False` list-arg execution for headless Blender, and blocks arbitrary custom `render_command` strings unless `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=true` is explicitly enabled.
   - **Zero-Cost Docs & SSRF Protection:** `gemini_docs` works with zero API key (`gemini-api-docs-mcp.dev` + `llms.txt` fallback) and restricts fetches & redirects to allowlisted Google/GitHub HTTPS hosts.

---

## Why Use `gemini-omni-mcp` Instead of Manual CLI Wrappers?

Official CLI tools (`gemini-cli`) focus on enterprise code-assist chat sessions rather than agent-callable Nano Banana 2.1 image synthesis, stateful Gemini Omni video loops, `gemini-3.5-transcribe` SRT captions, custom Voices/Lyria 3.5 audio, or real-time FinOps spend caps inside your IDE agent.

`gemini-omni-mcp` gives any MCP client direct, single-tool access to Google's late-2026 multimodal stack — defaulting to `gemini-4-neon` (fast frontier) and `gemini-4-hydrogen` (workhorse), keeping expensive `gemini-4-carbon` strictly opt-in.

---

## Tool Architecture (6 Default Core + Opt-In Toolsets)

### Core Toolset (Default — 6 Tools)

| Tool | Primary Models & APIs | Capabilities |
| --- | --- | --- |
| `gemini_image` | `gemini-nano-banana-2.1` | `action="generate"` (text-to-image + up to 14 refs + style anchor + `freeform`, `character_sheet`, `architectural_sheet`, `story_scene`, `pixel_sprite` presets) or `edit` / `inpaint` / `outpaint` / `upscale` (with Pillow Lanczos fallback) |
| `gemini_video` | `gemini-omni-1.2-flash` (`v1beta` Interactions) | `generate`, `extend`, `edit`, `seamless_loop` (`3s`–`15s`, `360p`–`4K`, start/end frame interpolation, auto URI delivery) |
| `gemini_audio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, Voices API, `lyria-3.5` (`v1beta`) | Multi-speaker `tts` (`speech_metadata`), `transcribe` (`text`/`md`/`json`/`srt` + diarization + word timestamps), `voice_design`/`remix`/`replicate`/`list`/`get`/`delete`, and `music` |
| `gemini_analyze` | `gemini-4-hydrogen` (default), `gemini-4-neon`, opt-in `gemini-4-carbon`, `gemma-4-31b-it` | Single-shot analysis of PDFs, images, audio, video, code/CSV, `files/<id>`, and YouTube URLs with Google Search, Code Execution, and structured JSON output |
| `gemini_docs` | `gemini-api-docs-mcp.dev` (`$0.00` cost) | `action="search"` (live SDK/API search with automatic `aistudio.google.com/llms.txt` fallback) & `action="fetch"` (chunk ID or HTTPS doc slug) |
| `gemini_budget` | FinOps Ledger + `client.models` | `summary`, `pricing_table`, `live_models`, `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` with `OMNI_HARD_STOP_LIMIT_USD` kill-switch |

### Opt-In Toolsets (`--toolsets` / `GEMINI_OMNI_TOOLSETS`)

| Toolset | Tools Included | Enable Flag |
| --- | --- | --- |
| `swarm` (`+3`) | `gemini_async_swarm` (up to 64 parallel workers), `gemini_context_cache` (Gemini 4 implicit 95% cache + explicit cache), `gemini_files` (48h upload/list/get/delete) | `--toolsets core,swarm` |
| `research` (`+1`) | `gemini_deep_research` (`deep-research-preview-04-2026`, `antigravity-preview-09-2026`) | `--toolsets core,research` |
| `3d` (`+3`, **OFF by default**) | `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `gemini_3d_judge_and_autopatch` (`gemini-4-neon` judge + `shell=False` headless Blender loop) | `--toolsets core,3d` |
| `all` (`13` total) | Enables `core` + `swarm` + `research` + `3d` | `--toolsets all` |

---

## Quick Start

### 1. Install with `uv`

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync
```

Inspect registered tools without an API key:

```bash
# Default lean mode (6 core tools)
uv run gemini-omni-mcp --list-tools

# Include swarm & research (+4 -> 10 tools)
uv run gemini-omni-mcp --toolsets core,swarm,research --list-tools

# Enable all 13 tools (including 3D/CAD suite)
uv run gemini-omni-mcp --toolsets all --list-tools
```

### 2. Configure `.env` or Client Env Block

Copy [`.env.example`](.env.example) to `.env` in your project workspace:

```dotenv
GEMINI_API_KEY=your-gemini-api-key-here
OMNI_HARD_STOP_LIMIT_USD=50.0
GEMINI_OMNI_TOOLSETS=core
GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false
GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=false
```

> **FinOps Safety Note:** Always pair `OMNI_HARD_STOP_LIMIT_USD` with a hard monthly spend limit in your Google Cloud / Google AI Studio billing console. Local ledger tracking protects per-workspace sessions, while billing caps protect your account globally.

### 3. Wire Into Your IDE (`mcp_config.json` / Claude / Cursor / Codex / Antigravity)

Default 6-tool config:

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
        "GEMINI_API_KEY": "your-gemini-api-key",
        "GEMINI_OMNI_WORKSPACE": "/path/to/your/workspace",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0"
      }
    }
  }
}
```

Pass `--toolsets core,swarm,research` (or `--toolsets all`) in `args` whenever you want additional toolsets loaded.

---

## Development & Tests

```bash
uv sync --extra dev
uv run --extra dev pytest -v
```

All API/network calls in the test suite run against clean local mocks so `pytest` passes completely offline.

---

## License

MIT — see [LICENSE](LICENSE).
