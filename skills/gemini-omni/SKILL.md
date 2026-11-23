---
name: gemini-omni
description: Lean, hardened Google GenAI workflow across Gemini 4 (Neon, Hydrogen, opt-in Carbon), Gemma 4, Live Docs Puller, Nano Banana 2.1 images, Omni Video, Audio/Transcribe/Voices/Lyria 3.5, and FinOps USD budget guardrails.
---

# Gemini Omni MCP — Agent Operating Guide

`gemini-omni-mcp` exposes **6 lean core tools** by default to minimize context-window overhead, plus modular opt-in toolsets (`swarm`, `research`, `3d`, or `all` for 13 tools).

## 1. Default Core Toolset (6 Tools)

| Tool | Purpose & Default Model | Notes |
| --- | --- | --- |
| `gemini_image` | `gemini-nano-banana-2.1` | `action="generate"` (text-to-image + up to 14 refs & presets) or `"edit"` / `"inpaint"` / `"outpaint"` / `"upscale"` |
| `gemini_video` | `gemini-omni-1.2-flash` (`v1beta`) | Stateful video `generate`, `extend`, `edit`, `seamless_loop` (`3s`–`15s`, `360p`–`4k`) |
| `gemini_audio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, Voices API, `lyria-3.5` (`v1beta`) | TTS speech synthesis, audio/video transcription (`text`, `md`, `json`, `srt`), voice cloning/design, music |
| `gemini_analyze` | `gemini-4-hydrogen` | PDFs, images, audio, video, code/CSV, `files/<id>`, YouTube URLs, Search/Code Execution, structured JSON |
| `gemini_docs` | Zero API key (`$0.00`) | `action="search"` (`gemini-api-docs-mcp.dev` + `llms.txt` fallback) or `"fetch"` (chunk ID or HTTPS doc slug) |
| `gemini_budget` | FinOps ledger & `models.list` | `summary`, `pricing_table`, `live_models`, `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` |

## 2. Opt-In Toolsets (`--toolsets` / `GEMINI_OMNI_TOOLSETS`)

- **`swarm`** (`+3` tools): `gemini_async_swarm`, `gemini_context_cache`, `gemini_files`
- **`research`** (`+1` tool): `gemini_deep_research` (`deep-research-preview-04-2026`, `antigravity-preview-09-2026`)
- **`3d`** (`+3` tools, **OFF by default**): `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `gemini_3d_judge_and_autopatch` (`gemini-4-neon` judge)

Enable at startup with:
```bash
uv run gemini-omni-mcp --toolsets core,swarm,research
```

## 3. Model Selection & FinOps Best Practices

- **Default Frontier:** Use `gemini-4-neon` (fast, reasoning, multimodal) or `gemini-4-hydrogen` (cost-efficient workhorse). Reserve `gemini-4-carbon` strictly for explicit user requests requiring maximum frontier depth.
- **Open Weights:** Use `gemma-4-31b-it` (or `gemma-4-26b-a4b-it`) for ultra-low-cost classification and extraction; `thinking_config` is omitted automatically on Gemma models.
- **Thinking Levels:** `thinking_level` is normalized safely across models (`minimal` -> `low` on Gemini 4; `xhigh` -> `high` on Carbon/Argon/3.x).
- **Check Live Docs Before Coding:** Call `gemini_docs(action="search", query=...)` and `gemini_docs(action="fetch", slug_or_url=...)` first at zero API cost.
- **Check Spend:** Use `gemini_budget(action="summary")` during multi-step media or swarm runs (`OMNI_HARD_STOP_LIMIT_USD` defaults to `$50.0`). Set a hard billing cap in Google Cloud / AI Studio as well.
- **Workspace Sandbox:** File paths are restricted to `GEMINI_OMNI_WORKSPACE` by default (`GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false`). Keep all outputs and inputs inside the workspace unless explicitly opted in.
