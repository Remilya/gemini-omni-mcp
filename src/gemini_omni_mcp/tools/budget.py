"""Real-time USD spend ledger, pricing calculator, live model catalog, and budget kill-switch."""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional

from gemini_omni_mcp.client import get_client
from gemini_omni_mcp.config import get_ledger_path, load_dotenv_if_present
from gemini_omni_mcp.pricing import (
    PRICING_SOURCE_URL,
    PRICING_VERSION,
    calculate_call_cost,
    get_active_key_fingerprint,
    get_hard_stop_limit_usd,
    get_pricing_rates,
    load_usage_ledger,
    recompute_ledger_totals,
    record_api_usage,
    reset_usage_ledger,
    set_budget_limit,
)

SUPPORTED_MODELS = (
    "gemini-4-carbon",
    "gemini-4-neon",
    "gemini-4-hydrogen",
    "gemini-4-argon",
    "gemini-3.5-flash-lite",
    "gemini-decision-1",
    "gemini-nano-banana-2.1",
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-lite-image",
    "gemini-3-pro-image",
    "gemini-omni-1.2-flash",
    "gemini-omni-1.1-flash",
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.5-transcribe",
    "gemini-3.5-transcribe-live",
    "gemini-3.8-live",
    "gemini-3.8-live-extended-thinking",
    "gemini-embedding-2",
    "lyria-3.5",
    "lyria-3-clip-preview",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.1-pro-preview",
)


def _serialize_model_info(m: Any) -> dict[str, Any]:
    actions = (
        getattr(m, "supported_actions", None)
        or getattr(m, "supported_generation_methods", None)
        or []
    )
    return {
        "name": getattr(m, "name", None),
        "display_name": getattr(m, "display_name", None),
        "description": getattr(m, "description", None),
        "input_token_limit": getattr(m, "input_token_limit", None),
        "output_token_limit": getattr(m, "output_token_limit", None),
        "supported_actions": list(actions) if actions else [],
    }


async def gemini_cost_and_budget(
    action: Literal[
        "summary",
        "pricing_table",
        "live_models",
        "calculate_call",
        "estimate_batch",
        "set_budget_limit",
        "reset_ledger",
    ] = "summary",
    model: str = "gemini-4-hydrogen",
    tier: Literal["standard", "batch", "flex", "priority", "contributor"] = "standard",
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    images_generated: int = 0,
    image_resolution: Literal["0.5k", "1k", "2k", "4k"] = "2k",
    video_seconds: float = 0.0,
    video_resolution: Literal["360p", "720p", "1080p", "4k"] = "720p",
    audio_seconds: float = 0.0,
    songs_generated: int = 0,
    num_items: int = 10,
    avg_input_tokens: int = 4000,
    avg_cached_tokens: int = 0,
    avg_output_tokens: int = 1500,
    images_per_item: int = 0,
    video_seconds_per_item: float = 0.0,
    audio_seconds_per_item: float = 0.0,
    songs_per_item: int = 0,
    new_budget_limit_usd: Optional[float] = None,
    record_to_ledger: bool = False,
    note: str = "",
    model_filter: Optional[str] = None,
    model_id: Optional[str] = None,
    page_size: int = 50,
) -> dict[str, Any]:
    """Gemini API price calculator, batch estimator, live model catalog, & USD budget kill-switch.

    Actions:
      - `summary`: Return cumulative session spend, breakdowns (`by_model`, `by_tool`), and recent entries.
      - `pricing_table`: Return standard and batch rates across all 26 Gemini 4, Gemma 4, Decisions, and media models.
      - `live_models`: Query `client.models.list()` / `client.models.get()` for live API model metadata & token limits.
      - `calculate_call`: Compute exact USD cost for a single API call (optionally recording to ledger).
      - `estimate_batch`: Compare Standard vs Batch/Flex costs for `num_items` workloads.
      - `set_budget_limit`: Update `hard_stop_limit_usd` (`0` disables hard stop; raising above current spend unlocks).
      - `reset_ledger`: Clear the local usage ledger JSON.
    """
    if action == "reset_ledger":
        ledger = reset_usage_ledger()
        return {
            "status": "reset",
            "ledger_path": str(get_ledger_path()),
            "totals": ledger["totals"],
        }

    if action == "set_budget_limit":
        if new_budget_limit_usd is None:
            raise ValueError("new_budget_limit_usd is required for action='set_budget_limit'.")
        ledger = set_budget_limit(new_budget_limit_usd)
        return {
            "status": ledger["status"],
            "ledger_path": str(get_ledger_path()),
            "hard_stop_limit_usd": ledger["hard_stop_limit_usd"],
            "hard_stop_triggered": bool(ledger["hard_stop_triggered"]),
            "totals": ledger["totals"],
        }

    if action == "live_models":
        client = get_client(context="gemini_cost_and_budget:live_models")
        if model_id and model_id.strip():
            m_obj = await asyncio.to_thread(client.models.get, model=model_id.strip())
            return {"status": "success", "model": _serialize_model_info(m_obj)}

        cap = max(1, min(int(page_size), 200))
        needle = (model_filter or "").strip().lower()

        def _fetch_models() -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for m_obj in client.models.list():
                info = _serialize_model_info(m_obj)
                if needle:
                    hay = f"{info.get('name') or ''} {info.get('display_name') or ''}".lower()
                    if needle not in hay:
                        continue
                out.append(info)
                if len(out) >= cap:
                    break
            return out

        models_list = await asyncio.to_thread(_fetch_models)
        return {
            "status": "success",
            "count": len(models_list),
            "filter": model_filter,
            "models": models_list,
        }

    if action == "pricing_table":
        table = {
            m: {
                "standard": get_pricing_rates(m, "standard"),
                "batch": get_pricing_rates(m, "batch"),
            }
            for m in SUPPORTED_MODELS
        }
        return {
            "pricing_version": PRICING_VERSION,
            "source_url": PRICING_SOURCE_URL,
            "models": table,
        }

    if action == "calculate_call":
        if record_to_ledger:
            entry = record_api_usage(
                tool_name="manual_calculated_call",
                model=model,
                tier=tier,
                input_tokens=input_tokens,
                cached_tokens=cached_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                images_generated=images_generated,
                image_resolution=image_resolution,
                video_seconds=video_seconds,
                video_resolution=video_resolution,
                audio_seconds=audio_seconds,
                songs_generated=songs_generated,
                note=note or "Manual calculator entry",
            )
            return {"recorded": True, "entry": entry}
        return {
            "recorded": False,
            "calculation": calculate_call_cost(
                model=model,
                tier=tier,
                input_tokens=input_tokens,
                cached_tokens=cached_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                images_generated=images_generated,
                image_resolution=image_resolution,
                video_seconds=video_seconds,
                video_resolution=video_resolution,
                audio_seconds=audio_seconds,
                songs_generated=songs_generated,
            ),
        }

    if action == "estimate_batch":
        n = max(1, int(num_items))
        std_calc = calculate_call_cost(
            model=model,
            tier="standard",
            input_tokens=int(avg_input_tokens) * n,
            cached_tokens=int(avg_cached_tokens) * n,
            output_tokens=int(avg_output_tokens) * n,
            images_generated=int(images_per_item) * n,
            image_resolution=image_resolution,
            video_seconds=float(video_seconds_per_item) * n,
            video_resolution=video_resolution,
            audio_seconds=float(audio_seconds_per_item) * n,
            songs_generated=int(songs_per_item) * n,
        )
        batch_calc = calculate_call_cost(
            model=model,
            tier="batch",
            input_tokens=int(avg_input_tokens) * n,
            cached_tokens=int(avg_cached_tokens) * n,
            output_tokens=int(avg_output_tokens) * n,
            images_generated=int(images_per_item) * n,
            image_resolution=image_resolution,
            video_seconds=float(video_seconds_per_item) * n,
            video_resolution=video_resolution,
            audio_seconds=float(audio_seconds_per_item) * n,
            songs_generated=int(songs_per_item) * n,
        )
        std_usd = float(std_calc["cost_usd"])
        batch_usd = float(batch_calc["cost_usd"])
        return {
            "model": std_calc["model"],
            "num_items": n,
            "standard_tier": std_calc,
            "batch_tier": batch_calc,
            "per_item_standard_usd": round(std_usd / n, 6),
            "per_item_batch_usd": round(batch_usd / n, 6),
            "estimated_savings_usd": round(max(0.0, std_usd - batch_usd), 6),
        }

    # Default action == "summary"
    load_dotenv_if_present(override=False)
    ledger = load_usage_ledger()
    recompute_ledger_totals(ledger)
    totals = ledger.get("totals") or {}
    return {
        "pricing_version": ledger.get("pricing_version"),
        "ledger_path": str(get_ledger_path()),
        "updated_at": ledger.get("updated_at"),
        "api_key_fingerprint": ledger.get("api_key_fingerprint", get_active_key_fingerprint()),
        "status": ledger.get("status", "ACTIVE"),
        "hard_stop_limit_usd": ledger.get("hard_stop_limit_usd", get_hard_stop_limit_usd()),
        "hard_stop_triggered": bool(ledger.get("hard_stop_triggered", False)),
        "total_cost_usd": totals.get("total_cost_usd", 0.0),
        "remaining_budget_usd": totals.get("remaining_budget_usd"),
        "totals": totals,
        "recent_entries": ledger.get("entries", [])[-15:],
    }


def register(mcp: Any) -> None:
    """Register cost, budget, and live model catalog tools on the MCP server instance."""
    mcp.tool()(gemini_cost_and_budget)
