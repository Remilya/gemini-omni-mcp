"""Gemini Developer API pricing engine, usage ledger, and real-time USD budget kill-switch."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from gemini_omni_mcp.config import (
    LEDGER_LOCK,
    get_ledger_path,
    logger,
)

DEFAULT_HARD_STOP_LIMIT_USD = 50.0
PRICING_VERSION = "2026-11-23 (Official Google Gemini Developer API Pricing)"
PRICING_SOURCE_URL = "https://ai.google.dev/gemini-api/docs/pricing"


class HardBudgetStopError(RuntimeError):
    """Raised when cumulative API spend reaches or exceeds the configured USD hard stop limit."""


def get_pricing_rates(
    model: str,
    tier: str = "standard",
    as_of: Optional[datetime] = None,
) -> dict[str, Any]:
    """Return per-1M-token (or per-unit) USD rates for the specified model and tier.

    Applies date-based promotional pricing windows:
      - `gemini-4-carbon` / `gemini-4-argon`: promotional rates through 2026-11-30 UTC.
      - `gemini-3.8-flash` / `gemini-3.6-flash` / `gemini-3.8-flash-tts` / `gemini-3.8-flash-lite-tts`:
        promotional rates through 2026-12-31 UTC.
    """
    now_utc = as_of or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    else:
        now_utc = now_utc.astimezone(timezone.utc)

    is_g4_promo = (now_utc.year, now_utc.month, now_utc.day) <= (2026, 11, 30)
    is_flash38_promo = (now_utc.year, now_utc.month, now_utc.day) <= (2026, 12, 31)

    m = model.strip().lower()
    t = tier.strip().lower()

    tier_mult = {
        "standard": 1.0,
        "batch": 0.5,
        "flex": 0.5,
        "contributor": 0.5,
        "priority": 1.8,
    }.get(t, 1.0)

    if "gemini-4-carbon" in m or "gemini-4-argon" in m:
        base_in = 2.00 if is_g4_promo else 4.00
        base_out = 10.00 if is_g4_promo else 20.00
        base_cache = 0.10 if is_g4_promo else 0.20
        canonical = "gemini-4-carbon" if "carbon" in m else "gemini-4-argon"
        return {
            "model": canonical,
            "tier": t,
            "promo_active": is_g4_promo,
            "promo_until": "2026-11-30",
            "input_per_1m": round(base_in * tier_mult, 4),
            "output_per_1m": round(base_out * tier_mult, 4),
            "cache_per_1m": round(base_cache * tier_mult, 4),
            "cache_storage_per_1m_hr": 0.0,
        }

    if "gemini-4-neon" in m:
        return {
            "model": "gemini-4-neon",
            "tier": t,
            "input_per_1m": round(3.00 * tier_mult, 4),
            "output_per_1m": round(15.00 * tier_mult, 4),
            "cache_per_1m": round(0.15 * tier_mult, 4),
            "cache_storage_per_1m_hr": 0.0,
        }

    if "gemini-4-hydrogen" in m:
        return {
            "model": "gemini-4-hydrogen",
            "tier": t,
            "input_per_1m": round(1.50 * tier_mult, 4),
            "output_per_1m": round(7.50 * tier_mult, 4),
            "cache_per_1m": round(0.075 * tier_mult, 4),
            "cache_storage_per_1m_hr": 0.0,
        }

    if "gemini-decision" in m:
        return {
            "model": "gemini-decision-1",
            "tier": "standard",
            "batch_supported": False,
            "input_per_1m": 0.10,
            "output_per_1m": 0.0,
        }

    if "gemini-3.5-transcribe-live" in m:
        return {
            "model": "gemini-3.5-transcribe-live",
            "tier": "standard",
            "input_per_1m": 3.50,
            "output_per_1m": 21.00,
            "audio_tokens_per_sec": 25,
            "blended_usd_per_min": 0.009,
        }

    if "gemini-3.5-transcribe" in m:
        return {
            "model": "gemini-3.5-transcribe",
            "tier": "standard",
            "input_per_1m": 2.00,
            "output_per_1m": 12.00,
            "audio_tokens_per_sec": 25,
            "blended_usd_per_min": 0.005,
        }

    if "gemini-3.8-flash-lite-tts" in m:
        base_in = 0.50 if is_flash38_promo else 1.00
        base_audio_out = 6.00 if is_flash38_promo else 12.00
        return {
            "model": "gemini-3.8-flash-lite-tts",
            "tier": t,
            "promo_active": is_flash38_promo,
            "promo_until": "2026-12-31",
            "input_per_1m": round(base_in * tier_mult, 4),
            "output_per_1m": round(base_audio_out * tier_mult, 4),
            "audio_tokens_per_sec": 25,
        }

    if "gemini-3.8-flash-tts" in m:
        base_in = 0.50 if is_flash38_promo else 1.00
        base_audio_out = 9.00 if is_flash38_promo else 18.00
        return {
            "model": "gemini-3.8-flash-tts",
            "tier": t,
            "promo_active": is_flash38_promo,
            "promo_until": "2026-12-31",
            "input_per_1m": round(base_in * tier_mult, 4),
            "output_per_1m": round(base_audio_out * tier_mult, 4),
            "audio_tokens_per_sec": 25,
        }

    if "gemini-3.1-flash-tts" in m:
        return {
            "model": "gemini-3.1-flash-tts-preview",
            "tier": t,
            "input_per_1m": round(1.00 * tier_mult, 4),
            "output_per_1m": round(20.00 * tier_mult, 4),
            "audio_tokens_per_sec": 25,
        }

    if "gemini-3.8-flash" in m or "gemini-3.6-flash" in m:
        base_in = 0.75 if is_flash38_promo else 1.50
        base_out = 3.75 if is_flash38_promo else 7.50
        base_cache = 0.075 if is_flash38_promo else 0.15
        base_storage = 0.50 if is_flash38_promo else 1.00
        return {
            "model": "gemini-3.8-flash" if "3.8" in m else "gemini-3.6-flash",
            "tier": t,
            "promo_active": is_flash38_promo,
            "promo_until": "2026-12-31",
            "input_per_1m": round(base_in * tier_mult, 4),
            "output_per_1m": round(base_out * tier_mult, 4),
            "cache_per_1m": round(base_cache * tier_mult, 4),
            "cache_storage_per_1m_hr": base_storage,
        }

    if "nano-banana-2.1" in m:
        m_mult = 0.5 if t == "batch" else 1.0
        return {
            "model": "gemini-nano-banana-2.1",
            "tier": t,
            "input_per_1m": 1.50 * m_mult,
            "output_per_1m": 7.50 * m_mult,
            "image_output_per_1m": 30.00 * m_mult,
            "image_tokens_by_res": {"1k": 1120, "2k": 1680, "4k": 3780},
            "per_image_usd_by_res": {
                "1k": round(0.0336 * m_mult, 5),
                "2k": round(0.0504 * m_mult, 5),
                "4k": round(0.1134 * m_mult, 5),
            },
        }

    if "gemini-3.1-flash-lite-image" in m:
        m_mult = 0.5 if t == "batch" else 1.0
        return {
            "model": "gemini-3.1-flash-lite-image",
            "tier": t,
            "input_per_1m": 0.25 * m_mult,
            "output_per_1m": 1.50 * m_mult,
            "image_output_per_1m": 30.00 * m_mult,
            "image_tokens_by_res": {"0.5k": 747, "1k": 1120, "2k": 1680, "4k": 2520},
        }

    if "gemini-3.1-flash-image" in m:
        m_mult = 0.5 if t == "batch" else 1.0
        return {
            "model": "gemini-3.1-flash-image",
            "tier": t,
            "input_per_1m": 0.50 * m_mult,
            "output_per_1m": 3.00 * m_mult,
            "image_output_per_1m": 60.00 * m_mult,
            "image_tokens_by_res": {"0.5k": 747, "1k": 1120, "2k": 1680, "4k": 2520},
        }

    if "gemini-3-pro-image" in m:
        m_mult = 0.5 if t == "batch" else 1.0
        return {
            "model": "gemini-3-pro-image",
            "tier": t,
            "input_per_1m": 2.00 * m_mult,
            "output_per_1m": 12.00 * m_mult,
            "image_output_per_1m": 120.00 * m_mult,
            "image_tokens_by_res": {"1k": 1120, "2k": 1120, "4k": 2000},
            "per_image_usd_by_res": {
                "1k": round(0.1344 * m_mult, 5),
                "2k": round(0.1344 * m_mult, 5),
                "4k": round(0.2400 * m_mult, 5),
            },
        }

    if "omni-1.2-flash" in m or "omni-flash" in m:
        return {
            "model": "gemini-omni-1.2-flash",
            "tier": "standard",
            "input_per_1m": 1.50,
            "output_per_1m": 9.00,
            "video_output_per_1m": 12.00,
            "video_tokens_per_sec_by_res": {
                "360p": 1931,
                "720p": 5792,
                "1080p": 8688,
                "4k": 17376,
            },
            "video_usd_per_sec_by_res": {
                "360p": round(1931 * 12.00 / 1_000_000, 5),
                "720p": round(5792 * 12.00 / 1_000_000, 5),
                "1080p": round(8688 * 12.00 / 1_000_000, 5),
                "4k": round(17376 * 12.00 / 1_000_000, 5),
            },
        }

    if "omni-1.1-flash" in m:
        return {
            "model": "gemini-omni-1.1-flash",
            "tier": "standard",
            "input_per_1m": 1.50,
            "output_per_1m": 9.00,
            "video_output_per_1m": 17.50,
            "video_tokens_per_sec_by_res": {
                "360p": 1448,
                "720p": 5792,
                "1080p": 11584,
                "4k": 23168,
            },
            "video_usd_per_sec_by_res": {
                "360p": round(1448 * 17.50 / 1_000_000, 5),
                "720p": round(5792 * 17.50 / 1_000_000, 5),
                "1080p": round(11584 * 17.50 / 1_000_000, 5),
                "4k": round(23168 * 17.50 / 1_000_000, 5),
            },
        }

    if "gemini-3.8-live" in m:
        return {
            "model": "gemini-3.8-live-extended-thinking" if "extended" in m else "gemini-3.8-live",
            "tier": "standard",
            "input_per_1m": 0.75,
            "audio_input_per_1m": 3.00,
            "image_video_input_per_1m": 1.00,
            "output_per_1m": 4.50,
            "audio_output_per_1m": 12.00,
        }

    if "gemini-embedding-2" in m:
        m_mult = 0.5 if t == "batch" else 1.0
        return {
            "model": "gemini-embedding-2",
            "tier": t,
            "input_per_1m": round(0.20 * m_mult, 4),
            "image_input_per_1m": round(0.45 * m_mult, 4),
            "audio_input_per_1m": round(6.50 * m_mult, 4),
            "video_input_per_1m": round(12.00 * m_mult, 4),
            "output_per_1m": 0.0,
        }

    if "lyria-3-clip" in m:
        return {"model": "lyria-3-clip-preview", "tier": "standard", "per_song_usd": 0.04}

    if "lyria" in m:
        return {"model": "lyria-3.5", "tier": "standard", "per_song_usd": 0.08}

    if "imagen" in m:
        per_img = 0.02 if "fast" in m else (0.06 if "ultra" in m else 0.04)
        return {"model": m, "tier": "standard", "deprecated": True, "per_image_usd": per_img}

    if "gemini-3.1-pro" in m:
        return {
            "model": "gemini-3.1-pro-preview",
            "tier": t,
            "input_per_1m": round(2.00 * tier_mult, 4),
            "output_per_1m": round(12.00 * tier_mult, 4),
            "cache_per_1m": round(0.20 * tier_mult, 4),
            "cache_storage_per_1m_hr": 4.50,
        }

    if "gemini-3.5-flash-lite" in m:
        return {
            "model": "gemini-3.5-flash-lite",
            "tier": t,
            "input_per_1m": round(0.30 * tier_mult, 4),
            "output_per_1m": round(2.50 * tier_mult, 4),
            "cache_per_1m": round(0.03 * tier_mult, 4),
        }

    if "gemini-3.1-flash-lite" in m:
        return {
            "model": "gemini-3.1-flash-lite",
            "tier": t,
            "input_per_1m": round(0.25 * tier_mult, 4),
            "output_per_1m": round(1.50 * tier_mult, 4),
            "cache_per_1m": round(0.025 * tier_mult, 4),
        }

    if "gemma-4" in m:
        if "31b" in m:
            canonical = "gemma-4-31b-it"
        elif "26b" in m:
            canonical = "gemma-4-26b-a4b-it"
        else:
            canonical = m
        return {
            "model": canonical,
            "tier": "free",
            "free_tier_only": True,
            "input_per_1m": 0.0,
            "output_per_1m": 0.0,
            "cache_per_1m": 0.0,
        }

    # Default fallback to Gemini 4 Hydrogen rates
    return {
        "model": model,
        "tier": t,
        "input_per_1m": round(1.50 * tier_mult, 4),
        "output_per_1m": round(7.50 * tier_mult, 4),
        "cache_per_1m": round(0.075 * tier_mult, 4),
    }


def calculate_call_cost(
    model: str,
    tier: str = "standard",
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    images_generated: int = 0,
    image_resolution: str = "2k",
    video_seconds: float = 0.0,
    video_resolution: str = "720p",
    audio_seconds: float = 0.0,
    songs_generated: int = 0,
    cache_storage_hours: float = 0.0,
    as_of: Optional[datetime] = None,
) -> dict[str, Any]:
    """Calculate exact USD cost and itemized breakdown for a Gemini API call."""
    rates = get_pricing_rates(model, tier, as_of=as_of)
    resolved_model = str(rates.get("model", model))
    effective_in_tokens = int(input_tokens)
    if (
        "transcribe" in resolved_model
        and audio_seconds > 0
        and effective_in_tokens == 0
        and "audio_tokens_per_sec" in rates
    ):
        effective_in_tokens = int(round(audio_seconds * int(rates["audio_tokens_per_sec"])))

    uncached_in = max(0, effective_in_tokens - int(cached_tokens))
    cached_in = max(0, int(cached_tokens))

    in_rate = float(rates.get("input_per_1m", 0.0))
    cache_rate = float(rates.get("cache_per_1m", in_rate))
    out_rate = float(rates.get("output_per_1m", 0.0))

    input_cost = (uncached_in / 1_000_000.0) * in_rate
    cache_cost = (cached_in / 1_000_000.0) * cache_rate
    cache_storage_cost = (
        (cached_in / 1_000_000.0)
        * float(rates.get("cache_storage_per_1m_hr", 0.0))
        * float(cache_storage_hours)
    )

    image_cost = 0.0
    image_tokens_billed = 0
    if images_generated > 0:
        if "per_image_usd" in rates:
            image_cost = images_generated * float(rates["per_image_usd"])
        elif "image_output_per_1m" in rates:
            res_key = image_resolution.strip().lower()
            tok_map = rates.get("image_tokens_by_res", {"1k": 1120, "2k": 1680, "4k": 3780})
            tok_per_img = int(tok_map.get(res_key, tok_map.get("2k", 1680)))
            image_tokens_billed = images_generated * tok_per_img
            image_cost = (image_tokens_billed / 1_000_000.0) * float(rates["image_output_per_1m"])

    # Subtract image output tokens from text output count to avoid double-billing.
    effective_text_out_tokens = max(0, int(output_tokens) + int(thinking_tokens))
    if image_tokens_billed > 0 and effective_text_out_tokens >= image_tokens_billed:
        effective_text_out_tokens -= image_tokens_billed

    text_output_cost = (effective_text_out_tokens / 1_000_000.0) * out_rate

    video_cost = 0.0
    if video_seconds > 0 and "video_output_per_1m" in rates:
        vres = video_resolution.strip().lower()
        vtok_map = rates.get("video_tokens_per_sec_by_res", {"720p": 5792})
        vtok_per_sec = int(vtok_map.get(vres, 5792))
        video_tokens_billed = int(round(video_seconds * vtok_per_sec))
        video_cost = (video_tokens_billed / 1_000_000.0) * float(rates["video_output_per_1m"])

    audio_cost = 0.0
    if songs_generated > 0 and "per_song_usd" in rates:
        audio_cost += songs_generated * float(rates["per_song_usd"])
    elif (
        "transcribe" not in resolved_model
        and audio_seconds > 0
        and "audio_tokens_per_sec" in rates
        and effective_text_out_tokens == 0
    ):
        atok = int(round(audio_seconds * int(rates["audio_tokens_per_sec"])))
        audio_cost += (atok / 1_000_000.0) * out_rate

    total_cost = (
        input_cost
        + cache_cost
        + cache_storage_cost
        + text_output_cost
        + image_cost
        + video_cost
        + audio_cost
    )

    return {
        "model": resolved_model,
        "tier": str(rates.get("tier", tier)),
        "promo_active": rates.get("promo_active", False),
        "input_tokens": effective_in_tokens,
        "uncached_input_tokens": uncached_in,
        "cached_tokens": cached_in,
        "output_tokens": int(output_tokens),
        "thinking_tokens": int(thinking_tokens),
        "images_generated": int(images_generated),
        "image_resolution": image_resolution if images_generated > 0 else None,
        "video_seconds": float(video_seconds),
        "video_resolution": video_resolution if video_seconds > 0 else None,
        "cost_usd": round(total_cost, 6),
        "breakdown_usd": {
            "input_usd": round(input_cost, 6),
            "cache_usd": round(cache_cost + cache_storage_cost, 6),
            "text_and_thinking_output_usd": round(text_output_cost, 6),
            "image_output_usd": round(image_cost, 6),
            "video_output_usd": round(video_cost, 6),
            "audio_output_usd": round(audio_cost, 6),
        },
    }


def get_hard_stop_limit_usd(ledger: Optional[dict[str, Any]] = None) -> float:
    """Return the USD hard-stop limit (<= 0 disables the kill-switch)."""
    if ledger and ledger.get("hard_stop_limit_usd") is not None:
        try:
            return float(ledger["hard_stop_limit_usd"])
        except (TypeError, ValueError):
            pass
    try:
        return float(os.environ.get("OMNI_HARD_STOP_LIMIT_USD", str(DEFAULT_HARD_STOP_LIMIT_USD)))
    except (TypeError, ValueError):
        return DEFAULT_HARD_STOP_LIMIT_USD


def get_active_key_fingerprint() -> str:
    """Return a masked fingerprint of the active API key without exposing secrets."""
    raw_k = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if len(raw_k) >= 10:
        return f"{raw_k[:4]}...{raw_k[-4:]}"
    return "set" if raw_k else "unset"


def _empty_ledger(limit_usd: float) -> dict[str, Any]:
    remaining: Optional[float] = round(max(0.0, limit_usd), 6) if limit_usd > 0 else None
    status = "ACTIVE" if limit_usd > 0 else "UNLIMITED"
    return {
        "pricing_version": PRICING_VERSION,
        "pricing_source_url": PRICING_SOURCE_URL,
        "api_key_fingerprint": get_active_key_fingerprint(),
        "hard_stop_limit_usd": round(limit_usd, 2),
        "hard_stop_triggered": False,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "total_calls": 0,
            "total_cost_usd": 0.0,
            "hard_stop_limit_usd": round(limit_usd, 2),
            "remaining_budget_usd": remaining,
            "total_input_tokens": 0,
            "total_cached_tokens": 0,
            "total_output_tokens": 0,
            "total_thinking_tokens": 0,
            "total_images_generated": 0,
            "total_video_seconds": 0.0,
            "by_model": {},
            "by_tool": {},
        },
        "entries": [],
    }


def _save_ledger(ledger: dict[str, Any]) -> None:
    ledger_path = get_ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")


def load_usage_ledger() -> dict[str, Any]:
    """Load the usage ledger JSON from disk or initialize a fresh in-memory structure."""
    ledger_path = get_ledger_path()
    if ledger_path.is_file():
        try:
            return json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read usage ledger at %s, reinitializing: %s", ledger_path, exc)
    return _empty_ledger(get_hard_stop_limit_usd())


def recompute_ledger_totals(ledger: dict[str, Any]) -> dict[str, Any]:
    """Recompute aggregate totals across all entries in `ledger` and evaluate hard stop."""
    entries = ledger.get("entries", [])
    total_calls = len(entries)
    total_cost = 0.0
    total_in = 0
    total_cached = 0
    total_out = 0
    total_think = 0
    total_imgs = 0
    total_vid_sec = 0.0
    by_model: dict[str, dict[str, Any]] = {}
    by_tool: dict[str, dict[str, Any]] = {}

    for e in entries:
        c_usd = float(e.get("cost_usd", 0.0))
        in_t = int(e.get("input_tokens", 0))
        ca_t = int(e.get("cached_tokens", 0))
        ou_t = int(e.get("output_tokens", 0))
        th_t = int(e.get("thinking_tokens", 0))
        imgs = int(e.get("images_generated", 0))
        vsec = float(e.get("video_seconds", 0.0))
        mod = str(e.get("model", "unknown"))
        tname = str(e.get("tool_name", "unknown"))

        total_cost += c_usd
        total_in += in_t
        total_cached += ca_t
        total_out += ou_t
        total_think += th_t
        total_imgs += imgs
        total_vid_sec += vsec

        m_bucket = by_model.setdefault(
            mod,
            {
                "calls": 0,
                "cost_usd": 0.0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "images_generated": 0,
                "video_seconds": 0.0,
            },
        )
        m_bucket["calls"] += 1
        m_bucket["cost_usd"] = round(m_bucket["cost_usd"] + c_usd, 6)
        m_bucket["input_tokens"] += in_t
        m_bucket["cached_tokens"] += ca_t
        m_bucket["output_tokens"] += ou_t
        m_bucket["thinking_tokens"] += th_t
        m_bucket["images_generated"] += imgs
        m_bucket["video_seconds"] = round(m_bucket["video_seconds"] + vsec, 2)

        t_bucket = by_tool.setdefault(tname, {"calls": 0, "cost_usd": 0.0})
        t_bucket["calls"] += 1
        t_bucket["cost_usd"] = round(t_bucket["cost_usd"] + c_usd, 6)

    limit_usd = get_hard_stop_limit_usd(ledger)
    rounded_cost = round(total_cost, 6)
    if limit_usd <= 0:
        triggered = False
        status = "UNLIMITED"
        remaining: Optional[float] = None
    else:
        triggered = bool(ledger.get("hard_stop_triggered", False) or rounded_cost >= limit_usd)
        status = f"HARD_STOP_LOCKED_AT_{limit_usd:.2f}_USD" if triggered else "ACTIVE"
        remaining = round(max(0.0, limit_usd - rounded_cost), 6)

    ledger["api_key_fingerprint"] = get_active_key_fingerprint()
    ledger["hard_stop_limit_usd"] = round(limit_usd, 2)
    ledger["hard_stop_triggered"] = triggered
    ledger["status"] = status
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    ledger["totals"] = {
        "total_calls": total_calls,
        "total_cost_usd": rounded_cost,
        "hard_stop_limit_usd": round(limit_usd, 2),
        "remaining_budget_usd": remaining,
        "total_input_tokens": total_in,
        "total_cached_tokens": total_cached,
        "total_output_tokens": total_out,
        "total_thinking_tokens": total_think,
        "total_images_generated": total_imgs,
        "total_video_seconds": round(total_vid_sec, 2),
        "by_model": by_model,
        "by_tool": by_tool,
    }
    return ledger


def enforce_hard_budget_limit(
    estimated_next_cost_usd: float = 0.0,
    context: str = "",
) -> None:
    """Block API calls if cumulative spend reaches or exceeds `hard_stop_limit_usd`."""
    ledger = load_usage_ledger()
    limit_usd = get_hard_stop_limit_usd(ledger)
    if limit_usd <= 0:
        return

    totals = ledger.get("totals") or {}
    spent_usd = float(totals.get("total_cost_usd", 0.0))
    projected_usd = spent_usd + max(0.0, float(estimated_next_cost_usd))

    if ledger.get("hard_stop_triggered") or spent_usd >= limit_usd or projected_usd > limit_usd:
        try:
            with LEDGER_LOCK:
                ledger["hard_stop_triggered"] = True
                ledger["status"] = f"HARD_STOP_LOCKED_AT_{limit_usd:.2f}_USD"
                ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_ledger(ledger)
        except Exception:
            pass
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        ctx_suffix = f" [{context}]" if context else ""
        logger.critical(
            "HARD STOP LIMIT REACHED ($%.4f / $%.2f USD)%s. API access locked.",
            spent_usd,
            limit_usd,
            ctx_suffix,
        )
        raise HardBudgetStopError(
            f"HARD STOP LIMIT REACHED (${spent_usd:.4f} / ${limit_usd:.2f} USD in {get_ledger_path().name}){ctx_suffix}. "
            "gemini-omni-mcp has locked API calls to prevent additional spend."
        )


def _response_has_inline_image(response_obj: Any) -> bool:
    if hasattr(response_obj, "generated_images") and response_obj.generated_images:
        return True
    for cand in getattr(response_obj, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return True
    return False


def record_api_usage(
    tool_name: str,
    model: str,
    tier: str = "standard",
    response_obj: Any = None,
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    images_generated: int = 0,
    image_resolution: str = "2k",
    video_seconds: float = 0.0,
    video_resolution: str = "720p",
    audio_seconds: float = 0.0,
    songs_generated: int = 0,
    cache_storage_hours: float = 0.0,
    note: str = "",
    reconcile_key: Optional[str] = None,
) -> dict[str, Any]:
    """Record token/media usage and USD cost to the ledger; locks server if budget limit is crossed."""
    um = getattr(response_obj, "usage_metadata", None) if response_obj is not None else None
    if um is not None:
        input_tokens = int(getattr(um, "prompt_token_count", None) or input_tokens or 0)
        cached_tokens = int(getattr(um, "cached_content_token_count", None) or cached_tokens or 0)
        output_tokens = int(getattr(um, "candidates_token_count", None) or output_tokens or 0)
        thinking_tokens = int(getattr(um, "thoughts_token_count", None) or thinking_tokens or 0)

    if images_generated == 0 and response_obj is not None and (
        "image" in model.lower() or "banana" in model.lower()
    ):
        if _response_has_inline_image(response_obj):
            images_generated = 1

    cost_info = calculate_call_cost(
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
        cache_storage_hours=cache_storage_hours,
    )

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        **cost_info,
        "note": note,
    }
    if reconcile_key:
        entry["reconcile_key"] = reconcile_key

    crossed_limit = False
    spent_after = 0.0
    limit_usd = get_hard_stop_limit_usd()

    try:
        with LEDGER_LOCK:
            ledger = load_usage_ledger()
            if reconcile_key:
                existing_keys = {e.get("reconcile_key") for e in ledger.get("entries", [])}
                if reconcile_key in existing_keys:
                    return entry
            ledger.setdefault("entries", []).append(entry)
            recompute_ledger_totals(ledger)
            _save_ledger(ledger)
            limit_usd = get_hard_stop_limit_usd(ledger)
            spent_after = float(ledger["totals"]["total_cost_usd"])
            crossed_limit = bool(
                limit_usd > 0
                and (ledger.get("hard_stop_triggered") or spent_after >= limit_usd)
            )
    except Exception as exc:
        logger.warning("Failed to persist usage ledger entry: %s", exc)

    if crossed_limit:
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        logger.critical(
            "HARD STOP LIMIT EXCEEDED ($%.4f / $%.2f USD)! Locking gemini-omni-mcp.",
            spent_after,
            limit_usd,
        )
        raise HardBudgetStopError(
            f"HARD STOP LIMIT EXCEEDED (${spent_after:.4f} / ${limit_usd:.2f} USD). "
            "gemini-omni-mcp has locked itself and stopped further API calls."
        )

    return entry


def set_budget_limit(new_limit_usd: float) -> dict[str, Any]:
    """Update `hard_stop_limit_usd` in the ledger and unlock if the new limit permits."""
    with LEDGER_LOCK:
        ledger = load_usage_ledger()
        limit_val = round(max(0.0, float(new_limit_usd)), 2)
        ledger["hard_stop_limit_usd"] = limit_val
        recompute_ledger_totals(ledger)
        spent = float(ledger["totals"]["total_cost_usd"])
        if limit_val <= 0 or limit_val > spent:
            ledger["hard_stop_triggered"] = False
            recompute_ledger_totals(ledger)
        _save_ledger(ledger)
        return ledger


def reset_usage_ledger() -> dict[str, Any]:
    """Reset the usage ledger JSON on disk to empty."""
    with LEDGER_LOCK:
        ledger_path = get_ledger_path()
        if ledger_path.is_file():
            ledger_path.unlink()
        ledger = _empty_ledger(get_hard_stop_limit_usd())
        _save_ledger(ledger)
        return ledger
