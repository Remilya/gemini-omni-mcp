"""Optional 3D/CAD vision spec extraction, RLAIF render critique, and script autopatching tools."""

from __future__ import annotations

import ast
import asyncio
import json
import re
import shutil
import subprocess
from typing import Any, Literal, Optional

from google.genai import types
from PIL import Image

from gemini_omni_mcp.client import generate_content_with_retry, get_client
from gemini_omni_mcp.config import get_workspace_root, logger, resolve_path
from gemini_omni_mcp.media import (
    extract_json_text,
    find_blender_executable,
    load_media_part,
)
from gemini_omni_mcp.pricing import record_api_usage
from gemini_omni_mcp.schemas import (
    ArgonJudgeEvaluation,
    Asset3DSpecResponse,
    RLAIF3DCriticResponse,
)

HARD_MAX_ARGON_RETRIES = 5


async def vision_extract_3d_spec(
    image_paths: list[str],
    subject_name: str,
    entity_type: Literal[
        "character", "prop", "architecture", "environment", "vehicle", "other"
    ] = "prop",
    triangle_budget_limit: int = 10000,
) -> dict[str, Any]:
    """Extract a structured PBR `#RRGGBB` palette and 3D proportion spec from reference images.

    Combines deterministic PIL pixel median sampling with `gemini-3.8-flash` vision reasoning.
    """
    if not image_paths:
        raise ValueError("image_paths cannot be empty.")

    parts: list[types.Part] = [load_media_part(p, max_dim=896) for p in image_paths[:4]]

    sampled_regions: dict[str, str] = {}
    try:
        first_p = resolve_path(image_paths[0])
        with Image.open(first_p) as im:
            rgb_im = im.convert("RGB")
            w, h = rgb_im.size
            crops = {
                "upper_region": (int(w * 0.30), int(h * 0.08), int(w * 0.70), int(h * 0.28)),
                "upper_center": (int(w * 0.38), int(h * 0.22), int(w * 0.62), int(h * 0.38)),
                "mid_region": (int(w * 0.30), int(h * 0.38), int(w * 0.70), int(h * 0.58)),
                "lower_region": (int(w * 0.28), int(h * 0.58), int(w * 0.72), int(h * 0.80)),
            }
            for cname, box in crops.items():
                sub = rgb_im.crop(box).resize((24, 24))
                pxs = [
                    p
                    for p in sub.getdata()
                    if not (p[0] > 232 and p[1] > 228 and p[2] > 220)
                    and not (p[0] < 20 and p[1] < 20 and p[2] < 20)
                ]
                if pxs:
                    r_med = sorted(p[0] for p in pxs)[len(pxs) // 2]
                    g_med = sorted(p[1] for p in pxs)[len(pxs) // 2]
                    b_med = sorted(p[2] for p in pxs)[len(pxs) // 2]
                    sampled_regions[cname] = f"#{r_med:02X}{g_med:02X}{b_med:02X}"
    except Exception:
        pass

    prompt = (
        f"You are an Agentic Vision 3D Spec Extractor for `{subject_name}` (entity_type='{entity_type}').\n"
        f"Pre-sampled PIL region median HEX telemetry from the primary image: {json.dumps(sampled_regions)}\n"
        "Combine these pixel measurements with visual inspection of the attached reference image(s) to extract:\n"
        "1. Canonical `#RRGGBB` HEX codes, roughness, metallic, and emissive flags for all major parts.\n"
        "2. Realistic 3D dimensions and elevation centers in meters.\n"
        f"3. Enforce target triangle_budget_limit={int(triangle_budget_limit)}.\n"
        "4. Include explicit anti-Z-fighting offset rules (>= 0.01m) for coplanar/overlapping surfaces."
    )
    parts.append(types.Part.from_text(text=prompt))

    client = get_client(context="vision_extract_3d_spec")
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        response_mime_type="application/json",
        response_schema=Asset3DSpecResponse,
        temperature=0.1,
    )

    response = await asyncio.to_thread(
        generate_content_with_retry,
        client,
        "gemini-3.8-flash",
        parts,
        config,
        False,
        "vision_extract_3d_spec",
    )
    spec = Asset3DSpecResponse.model_validate_json(extract_json_text(response))
    return spec.model_dump()


async def vision_rlaif_3d_critic(
    render_image_path: str,
    reference_image_paths: list[str],
    spec_rules: str,
) -> dict[str, Any]:
    """Inspect a multi-angle 3D render against reference images using Gemini 3.8 Flash.

    Returns structured per-angle scores, visual bug list, and concrete coordinate/mesh fixes.
    """
    parts: list[types.Part] = [load_media_part(render_image_path, max_dim=1280)]
    for rp in reference_image_paths[:4]:
        parts.append(load_media_part(rp, max_dim=1024))

    prompt = (
        "You are an Agentic Vision 3D RLAIF Critic inspecting a multi-angle 3D render (Image #1)\n"
        "against the attached reference images or blueprints.\n\n"
        "Inspect every visible angle in Image #1, checking:\n"
        "1. Silhouette, symmetry, and proportions across all views (including rear/side views).\n"
        "2. Material and color fidelity against the references.\n"
        "3. Missing or floating geometry, unintended mesh intersections, or Z-fighting.\n"
        f"4. Specific Spec Rules:\n{spec_rules}"
    )
    parts.append(types.Part.from_text(text=prompt))

    client = get_client(context="vision_rlaif_3d_critic")
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        response_mime_type="application/json",
        response_schema=RLAIF3DCriticResponse,
        temperature=0.1,
    )

    response = await asyncio.to_thread(
        generate_content_with_retry,
        client,
        "gemini-3.8-flash",
        parts,
        config,
        False,
        "vision_rlaif_3d_critic",
    )
    critic = RLAIF3DCriticResponse.model_validate_json(extract_json_text(response))
    return critic.model_dump()


async def argon_judge_and_autopatch(
    subject_id: str,
    render_image_path: str,
    reference_image_paths: list[str],
    cad_script_path: str,
    render_command: Optional[str] = None,
    cached_content_name: Optional[str] = None,
    auto_rewrite_script_if_failed: bool = True,
    max_argon_iterations: int = 3,
    reset_retry_counter: bool = False,
) -> dict[str, Any]:
    """Supreme visual + code judge (`gemini-4-argon`) and autonomous 3D script autopatcher.

    Audits the rendered views and 3D generator script, synthesizes targeted code fixes if
    `score < 95`, validates Python syntax (`ast.parse`) before writing, executes headless
    Blender (or custom `render_command`), and enforces a hard circuit breaker of 5 attempts.
    """
    script_file = resolve_path(cad_script_path)
    render_file = resolve_path(render_image_path)
    if not script_file.is_file():
        raise FileNotFoundError(f"CAD script not found: {script_file}")
    if not render_file.is_file():
        raise FileNotFoundError(f"Render image not found: {render_file}")

    clamped_max_iters = max(1, min(int(max_argon_iterations), HARD_MAX_ARGON_RETRIES))
    verdict_file = render_file.parent / "argon_verdict.json"
    cumulative_attempts = 0
    prior_history: list[dict[str, Any]] = []

    if verdict_file.is_file() and not reset_retry_counter:
        try:
            prev_data = json.loads(verdict_file.read_text(encoding="utf-8"))
            cumulative_attempts = int(
                prev_data.get("cumulative_attempts", prev_data.get("iterations_run", 0))
            )
            prior_history = list(prev_data.get("history", []))
            if cumulative_attempts >= HARD_MAX_ARGON_RETRIES and not prev_data.get("passed", False):
                prev_data["retry_limit_reached"] = True
                prev_data["max_retries_limit"] = HARD_MAX_ARGON_RETRIES
                prev_data["circuit_breaker_message"] = (
                    f"Hard Argon retry limit ({HARD_MAX_ARGON_RETRIES}/{HARD_MAX_ARGON_RETRIES}) reached for '{subject_id}'. "
                    "Loop halted to prevent infinite retries. Inspect manually or pass reset_retry_counter=True."
                )
                return prev_data
        except Exception as exc:
            logger.warning("Could not read prior argon_verdict.json at %s: %s", verdict_file, exc)

    remaining_budget = max(1, HARD_MAX_ARGON_RETRIES - cumulative_attempts)
    effective_iters = min(clamped_max_iters, remaining_budget)

    client = get_client(context=f"argon_judge_and_autopatch:{subject_id}")
    workspace = get_workspace_root()
    history_log: list[dict[str, Any]] = list(prior_history)
    retry_limit_reached = False
    circuit_breaker_message: Optional[str] = None

    for iteration in range(1, effective_iters + 1):
        cumulative_attempts += 1
        current_code = script_file.read_text(encoding="utf-8")
        parts: list[types.Part] = [load_media_part(str(render_file), max_dim=1024)]
        for rp in reference_image_paths[:2]:
            parts.append(load_media_part(rp, max_dim=896))

        quad_stats: dict[str, Any] = {}
        try:
            with Image.open(render_file) as rim:
                rgb_r = rim.convert("RGB")
                rw, rh = rgb_r.size
                quads = {
                    "top_left": (0, 0, rw // 2, rh // 2),
                    "top_right": (rw // 2, 0, rw, rh // 2),
                    "bottom_left": (0, rh // 2, rw // 2, rh),
                    "bottom_right": (rw // 2, rh // 2, rw, rh),
                }
                for qn, qbox in quads.items():
                    qsub = rgb_r.crop(qbox).resize((48, 48))
                    qpx = list(qsub.getdata())
                    fg = [
                        p
                        for p in qpx
                        if abs(p[0] - 242) + abs(p[1] - 239) + abs(p[2] - 233) > 24
                    ]
                    quad_stats[qn] = {
                        "fg_coverage_pct": round(100.0 * len(fg) / max(1, len(qpx)), 1)
                    }
        except Exception:
            pass

        prompt = (
            f"You are `gemini-4-argon`, the Supreme 3D CAD & RLAIF Judge for asset `{subject_id}` "
            f"(Attempt {cumulative_attempts}/{HARD_MAX_ARGON_RETRIES}).\n"
            "Attached Media:\n"
            f"- Image #1: Current 3D render (`{render_file.name}`). Pre-computed quadrant foreground coverage: {json.dumps(quad_stats)}\n"
            "- Remaining Images: Reference Sheet(s) / Blueprints.\n\n"
            f"Current 3D Generator Script (`{script_file.name}`):\n"
            f"```python\n{current_code}\n```\n\n"
            "SUPREME JUDGE AUDIT CHECKLIST:\n"
            "1. Inspect all rendered angles in Image #1 — pay close attention to rear/back and side views.\n"
            "2. Check 3D proportions, silhouette clarity, and material colors against the references.\n"
            "3. Verify clean topology: material separation, applied transforms, triangle budget, and >= 0.01m Z-fighting offsets.\n"
            "4. Pass only if `score >= 95` (`passed: true`).\n"
            "5. Leave `rewritten_script` null in this JSON audit (code synthesis runs in Step 2 using your bug list)."
        )
        parts.append(types.Part.from_text(text=prompt))

        cfg_kwargs: dict[str, Any] = {
            "thinking_config": types.ThinkingConfig(thinking_level="LOW"),
            "response_mime_type": "application/json",
            "response_schema": ArgonJudgeEvaluation,
            "max_output_tokens": 4096,
            "temperature": 0.1,
        }
        if cached_content_name and str(cached_content_name).startswith("cachedContents/"):
            cfg_kwargs["cached_content"] = cached_content_name

        config = types.GenerateContentConfig(**cfg_kwargs)
        response = await client.aio.models.generate_content(
            model="gemini-4-argon",
            contents=parts,
            config=config,
        )
        await asyncio.to_thread(
            record_api_usage,
            "argon_judge_and_autopatch",
            "gemini-4-argon",
            "standard",
            response,
        )
        verdict = ArgonJudgeEvaluation.model_validate_json(extract_json_text(response))
        verdict.passed = bool(verdict.score >= 95 and verdict.passed)

        iter_entry: dict[str, Any] = {
            "iteration": iteration,
            "cumulative_attempt": cumulative_attempts,
            "score": verdict.score,
            "passed": verdict.passed,
            "rear_view_verdict": verdict.rear_view_verdict,
            "geometry_and_topology_audit": verdict.geometry_and_topology_audit,
            "visual_bugs": verdict.visual_bugs,
            "script_rewritten": False,
            "rerender_executed": False,
        }

        if verdict.passed or not auto_rewrite_script_if_failed:
            history_log.append(iter_entry)
            break

        if cumulative_attempts >= HARD_MAX_ARGON_RETRIES:
            retry_limit_reached = True
            circuit_breaker_message = (
                f"Hard Argon retry limit ({HARD_MAX_ARGON_RETRIES}/{HARD_MAX_ARGON_RETRIES}) reached for '{subject_id}'. "
                "Stopping further autopatches to prevent an infinite loop."
            )
            history_log.append(iter_entry)
            break

        patched_code = (verdict.rewritten_script or "").strip()
        if not patched_code:
            try:
                bugs_str = "\n".join(f"- {b}" for b in (verdict.visual_bugs or []))
                patch_prompt = (
                    f"Fix all 3D geometry, proportion, material, and placement bugs in `{script_file.name}` for `{subject_id}` "
                    f"identified by Supreme Judge `gemini-4-argon` (score={verdict.score}/100):\n\n"
                    f"Rear/Back Critique:\n{verdict.rear_view_verdict}\n\n"
                    f"Geometry & Topology Audit:\n{verdict.geometry_and_topology_audit}\n\n"
                    f"Exact Visual Bugs to Fix:\n{bugs_str}\n\n"
                    "STRICT RULES:\n"
                    "1. Preserve existing imports, helper interfaces, and CLI/entry points.\n"
                    "2. Output ONLY the complete, valid, directly executable script (no markdown commentary).\n\n"
                    f"Current `{script_file.name}`:\n```\n{current_code}\n```"
                )
                patch_parts = [load_media_part(str(render_file), max_dim=1024)]
                if reference_image_paths:
                    patch_parts.append(load_media_part(reference_image_paths[0], max_dim=1024))
                patch_parts.append(types.Part.from_text(text=patch_prompt))

                patch_resp = await client.aio.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=patch_parts,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                        max_output_tokens=16384,
                        temperature=0.1,
                    ),
                )
                await asyncio.to_thread(
                    record_api_usage,
                    "argon_judge_autopatch_code",
                    "gemini-3.8-flash",
                    "standard",
                    patch_resp,
                )
                patched_code = (getattr(patch_resp, "text", None) or "").strip()
            except Exception as patch_exc:
                logger.warning("Autopatch code synthesis failed for %s: %s", subject_id, patch_exc)

        if patched_code.startswith("```"):
            patched_code = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", patched_code)
            patched_code = re.sub(r"\s*```$", "", patched_code)

        if not patched_code or patched_code == current_code.strip():
            circuit_breaker_message = (
                f"No new script patch returned at attempt {cumulative_attempts}; halting loop."
            )
            history_log.append(iter_entry)
            break

        if script_file.suffix.lower() == ".py":
            try:
                ast.parse(patched_code)
            except SyntaxError as syn_err:
                circuit_breaker_message = (
                    f"Synthesized Python patch failed syntax validation at attempt {cumulative_attempts}: {syn_err}"
                )
                history_log.append(iter_entry)
                break

        backup_path = script_file.with_suffix(f".bak.iter{cumulative_attempts}{script_file.suffix}")
        shutil.copy2(script_file, backup_path)
        script_file.write_text(patched_code, encoding="utf-8")
        iter_entry["script_rewritten"] = True
        iter_entry["backup_script_path"] = str(backup_path)

        cmd_to_run = render_command
        if not cmd_to_run:
            blender_exe = find_blender_executable()
            cmd_to_run = f'"{blender_exe}" -b -P "{script_file}"'

        proc = await asyncio.to_thread(
            subprocess.run,
            cmd_to_run,
            shell=True,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=180,
        )
        iter_entry["rerender_executed"] = True
        iter_entry["rerender_returncode"] = proc.returncode
        iter_entry["rerender_stdout_tail"] = (proc.stdout or "")[-600:]
        if proc.returncode != 0:
            iter_entry["rerender_stderr_tail"] = (proc.stderr or "")[-600:]
            shutil.copy2(backup_path, script_file)
            iter_entry["rolled_back_broken_patch"] = True
            circuit_breaker_message = (
                f"Autopatch at attempt {cumulative_attempts} failed render command "
                f"(returncode={proc.returncode}); rolled back to backup and halted loop."
            )
            history_log.append(iter_entry)
            break

        history_log.append(iter_entry)

    final_entry = history_log[-1]
    result_payload: dict[str, Any] = {
        "model": "gemini-4-argon",
        "subject_id": subject_id,
        "final_score": final_entry["score"],
        "passed": final_entry["passed"],
        "iterations_run": len(history_log),
        "cumulative_attempts": cumulative_attempts,
        "max_retries_limit": HARD_MAX_ARGON_RETRIES,
        "retry_limit_reached": retry_limit_reached
        or (cumulative_attempts >= HARD_MAX_ARGON_RETRIES and not final_entry["passed"]),
        "circuit_breaker_message": circuit_breaker_message,
        "cad_script_path": str(script_file),
        "render_image_path": str(render_file),
        "history": history_log,
    }
    try:
        verdict_file.write_text(
            json.dumps(result_payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Failed to persist argon_verdict.json at %s: %s", verdict_file, exc)
    return result_payload


def register(mcp: Any) -> None:
    """Register optional 3D/CAD vision and autopatching tools on the MCP server instance."""
    mcp.tool()(vision_extract_3d_spec)
    mcp.tool()(vision_rlaif_3d_critic)
    mcp.tool()(argon_judge_and_autopatch)
