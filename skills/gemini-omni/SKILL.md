---
name: gemini-omni
description: Route multimodal image generation/editing, stateful Omni video studio, TTS/custom voices/Lyria music, 30-50x Flash async swarms, Context Caching, cost estimation/hard-stop budget checks, and optional 3D/CAD RLAIF verification through the gemini-omni MCP server.
---

# Gemini Omni MCP Skill

Use the `gemini-omni` MCP tools instead of launching a separate Gemini CLI session whenever an agent needs Google GenAI multimodal synthesis, high-concurrency batch processing, or cost-controlled Gemini 3.8 / Gemini 4 Argon execution.

## Tool Selection Guide

| Need | Tool | Key Notes |
| --- | --- | --- |
| Multi-ref image synthesis (up to 14 refs), style anchor, character/arch sheets | `gemini_image_fusion` | Defaults to `gemini-nano-banana-2.1`. Set `preset` (`freeform`, `character_sheet`, `architectural_sheet`, `story_scene`, `pixel_sprite`), `aspect_ratio`, and `image_size`. |
| Targeted regional image edit | `gemini_image_edit` | Modifies `source_image_path` using `edit_instruction` and up to 6 `extra_ref_paths` while preserving unmentioned regions. |
| Imagen 3 generate / masked inpaint / outpaint / 4x upscale | `imagen_studio` | Automatically falls back to Gemini image models or Pillow Lanczos if Vertex-only Imagen endpoints are unavailable on Developer API keys. |
| Stateful video gen, extend, edit, seamless loop | `gemini_video_studio` | Powered by `gemini-omni-1.2-flash` via `client.interactions.create`. Supports `start_frame_path` + `end_frame_path`, up to 6 `ref_media_paths`, `previous_interaction_id`, and `delivery="auto"`. |
| Expressive TTS, custom voices, & Lyria 3.5 BGM | `gemini_audio_studio` | `mode="tts"` uses `speech_metadata` annotations so stage directions are never spoken aloud. Also supports `voice_design`, `voice_remix`, `voice_replicate`, `voice_list`, and `music`. |
| Cache codebase, docs, or image anchors (up to 95% discount) | `gemini_context_cache` | Creates explicit cache (`cachedContents/...`) and writes a deterministic implicit prefix fallback in `.gemini-omni/cache/`. |
| Run 10–100+ parallel AI tasks | `gemini_async_swarm` | Concurrency-limited `asyncio` swarm on `gemini-3.8-flash` (or any model), supporting `cached_content_name`, `response_json_schema`, and direct `output_file` writing. |
| Filter 15–30 candidate images in one shot | `gemini_curate_refs` | Builds a numbered Pillow contact sheet and ranks top-k sharp, uncropped references with `CuratedRefsResponse`. |
| Check spend, pricing table, estimate batch cost, set hard stop | `gemini_cost_and_budget` | Offline FinOps control (`summary`, `pricing_table`, `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger`). |
| *(Optional)* 3D/CAD palette, spec, RLAIF critique & autopatch | `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `argon_judge_and_autopatch` | Enabled by default; disable with `GEMINI_OMNI_ENABLE_3D_TOOLS=false` or `--no-3d-tools`. `argon_judge_and_autopatch` includes a 5-attempt circuit breaker and syntax validation. |

## Recommended Workflows

1. **Pre-Flight Cost Check & Budget Safety**:
   - Before running a large `gemini_async_swarm` or multi-clip `gemini_video_studio` batch, call `gemini_cost_and_budget(action="estimate_batch", ...)` and `gemini_cost_and_budget(action="summary")`.
   - Respect `OMNI_HARD_STOP_LIMIT_USD` (default `50.0` USD). If a hard stop triggers, inform the user before calling `set_budget_limit`.
2. **Cache-First Swarms**:
   - When multiple workers share a spec, style guide, or codebase, call `gemini_context_cache` once, then pass the returned `cached_content_name` into `gemini_async_swarm` or `argon_judge_and_autopatch`.
3. **Stateful Multi-Turn Video Production**:
   - Start with `gemini_video_studio(action="generate", ...)` and reuse the returned `interaction_id` as `previous_interaction_id` for `action="extend"` or `action="edit"`.
   - Use `delivery="auto"` (default) so `1080p`, `4k`, or `>10s` clips switch cleanly to URI download instead of hitting inline payload limits.
4. **3D RLAIF Loop**:
   - Extract spec with `vision_extract_3d_spec`, run fast intermediate checks with `vision_rlaif_3d_critic`, and invoke `argon_judge_and_autopatch` as the final Supreme Judge (`score >= 95`).
