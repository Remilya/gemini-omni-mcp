---
name: gemini-omni
description: Route live Gemini API docs lookup, multimodal YouTube/PDF/media analysis, 48h Files API management, Gemini 4 (Carbon/Neon/Hydrogen) & Gemma 4 async swarms, zero-output-token Decisions API, Deep Research (start/poll/cancel/delete), embeddings, Nano Banana 2.1, Omni video studio, SRT/MD/JSON Transcribe, TTS/Voices/Lyria 3.5, live model catalog, budget guard, and optional 3D/CAD RLAIF tools through gemini-omni MCP.
---

# Gemini Omni MCP Skill (v2.1.0)

Use `gemini-omni` MCP tools directly inside your coding agent workflow instead of opening a separate CLI session whenever you need live Gemini API docs, Gemini 4 swarms, YouTube/PDF analysis, structured Decisions, multimodal media generation, or strict USD budget enforcement.

## Docs-First Rule (Zero Cost)

Before writing or refactoring Google GenAI SDK code, **always pull live documentation first**:
1. Call `gemini_search_docs(query=..., language="python")` (queries `https://gemini-api-docs-mcp.dev` with automatic `aistudio.google.com/llms.txt` fallback).
2. Read the exact guide or chunk via `gemini_fetch_doc(chunk_id=...)` or `gemini_fetch_doc(slug_or_url="decisions-api")` before generating code.
3. Always target `google-genai>=3.2.0` (`from google import genai`) and prefer `client.interactions` (never deprecated `google-generativeai` or shut-down Imagen models).

## Gemini 4, Gemma 4 & Specialized Model Selection Guide

| Tier / Model | Best For | Thinking Levels | Paid Rates (per 1M) |
| --- | --- | --- | --- |
| `gemini-4-carbon` | Deepest coding, architecture & 3D judge | `low`, `medium` (default), `high` | `$2.00` / `$10.00` intro thru Nov 30 (`$4.00` / `$20.00` after) |
| `gemini-4-neon` | Fast frontier coding & complex science | `low`, `medium`, `high` (default), `xhigh` | `$3.00` / `$15.00` |
| `gemini-4-hydrogen` | Everyday coding, analyze, swarms, vision QA (Free + Paid) | `low`, `medium`, `high` (default), `xhigh` | `$1.50` / `$7.50` |
| `gemini-3.5-flash-lite` | Ultra-fast high-volume classification/drafts | `minimal` (default), `low`, `medium`, `high` | `$0.30` / `$2.50` |
| `gemma-4-31b-it` / `gemma-4-26b-a4b-it` | Lightweight open-weight inference (Free Tier) | — | Free (`$0.00`) |
| `gemini-decision-1` | Zero-output-token `noul`/`choice`/`score` routing | Forward-pass calibrated probabilities | `$0.10` input / `$0.00` output |
| `gemini-3.5-transcribe` | Audio & video transcription (`text`, `md`, `json`, `srt`) | — | `$2.00` audio in / `$12.00` text out (~`$0.005`/min) |
| `gemini-embedding-2` | Text, image, audio, video & PDF embeddings | — | `$0.20` text / `$0.45` img / `$6.50` audio / `$12.00` video |

## Full 18-Tool Reference

### Core Tools (15 Always Enabled)
- **Live Docs Puller ($0.00):** `gemini_search_docs`, `gemini_fetch_doc`
- **Single-Shot Analysis & Reusable Files:** `gemini_analyze` (PDFs, images, audio, video, code, `files/<id>` URIs, & YouTube URLs), `gemini_files` (`upload`, `list`, `get`, `delete` with 48h retention)
- **Decisions & Agents:** `gemini_decide` (`noul` / `choice` / `score` up to 1,000 questions/call), `gemini_deep_research` (`start`, `status`, `run_and_wait`, `cancel`, `delete`), `gemini_embed` (unified multimodal vectors + similarity matrix)
- **Nano Banana 2.1 Images (Imagen replaced):** `gemini_image_fusion` (up to 14 refs + style anchor), `gemini_image_edit` (`edit`, `inpaint`, `outpaint`, `upscale` 2x/4x)
- **Video & Audio Studio:** `gemini_video_studio` (`gemini-omni-1.2-flash`, `3s`–`15s`, extend/edit/loop, auto URI delivery), `gemini_audio_studio` (`tts`, `transcribe` with `text`/`md`/`json`/`srt` + video/Files URI support, `music` via Lyria 3.5, `voice_design`/`voice_remix`/`voice_replicate`/`voice_list`)
- **Context & Swarms:** `gemini_context_cache` (Gemini 4 deterministic implicit prefix bundles + explicit caching for 3.x), `gemini_async_swarm` (up to 64 parallel workers on `gemini-4-hydrogen`), `gemini_curate_refs`
- **FinOps & Live Catalog:** `gemini_cost_and_budget` (`summary`, `pricing_table`, `live_models`, `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger`)

### Optional 3D/CAD RLAIF Suite (Disable with `--no-3d-tools` or `GEMINI_OMNI_ENABLE_3D_TOOLS=false`)
- `vision_extract_3d_spec` (`gemini-4-hydrogen` + PIL HEX telemetry)
- `vision_rlaif_3d_critic` (`gemini-4-hydrogen` multi-angle critique)
- `gemini_3d_judge_and_autopatch` (`gemini-4-carbon` judge + `gemini-4-hydrogen` patcher with `ast.parse` guard and 5-retry circuit breaker)
