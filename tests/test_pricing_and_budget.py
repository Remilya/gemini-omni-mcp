"""Offline tests for the pricing engine, usage ledger, and hard-stop budget kill-switch."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from gemini_omni_mcp.config import get_ledger_path
from gemini_omni_mcp.pricing import (
    HardBudgetStopError,
    calculate_call_cost,
    enforce_hard_budget_limit,
    get_pricing_rates,
    load_usage_ledger,
    record_api_usage,
    reset_usage_ledger,
    set_budget_limit,
)


def test_promo_vs_regular_rates_by_date():
    promo_dt = datetime(2026, 11, 20, tzinfo=timezone.utc)
    post_argon_dt = datetime(2026, 12, 1, tzinfo=timezone.utc)
    post_flash_dt = datetime(2027, 1, 1, tzinfo=timezone.utc)

    argon_promo = get_pricing_rates("gemini-4-argon", "standard", as_of=promo_dt)
    argon_reg = get_pricing_rates("gemini-4-argon", "standard", as_of=post_argon_dt)
    assert argon_promo["promo_active"] is True
    assert argon_promo["input_per_1m"] == 2.00
    assert argon_promo["output_per_1m"] == 10.00
    assert argon_reg["promo_active"] is False
    assert argon_reg["input_per_1m"] == 4.00
    assert argon_reg["output_per_1m"] == 20.00

    flash_promo = get_pricing_rates("gemini-3.8-flash", "standard", as_of=post_argon_dt)
    flash_reg = get_pricing_rates("gemini-3.8-flash", "standard", as_of=post_flash_dt)
    assert flash_promo["promo_active"] is True
    assert flash_promo["input_per_1m"] == 0.75
    assert flash_reg["promo_active"] is False
    assert flash_reg["input_per_1m"] == 1.50


def test_tier_multipliers_and_media_cost_math():
    promo_dt = datetime(2026, 11, 20, tzinfo=timezone.utc)
    std = calculate_call_cost(
        model="gemini-3.8-flash",
        tier="standard",
        input_tokens=1_000_000,
        cached_tokens=500_000,
        output_tokens=1_000_000,
        as_of=promo_dt,
    )
    batch = calculate_call_cost(
        model="gemini-3.8-flash",
        tier="batch",
        input_tokens=1_000_000,
        cached_tokens=500_000,
        output_tokens=1_000_000,
        as_of=promo_dt,
    )
    priority = calculate_call_cost(
        model="gemini-3.8-flash",
        tier="priority",
        input_tokens=1_000_000,
        cached_tokens=500_000,
        output_tokens=1_000_000,
        as_of=promo_dt,
    )
    assert batch["cost_usd"] == pytest.approx(std["cost_usd"] * 0.5, rel=1e-4)
    assert priority["cost_usd"] == pytest.approx(std["cost_usd"] * 1.8, rel=1e-4)

    # Image output tokens (1680 for 2k) should be subtracted from text output to prevent double billing.
    img_cost = calculate_call_cost(
        model="gemini-nano-banana-2.1",
        tier="standard",
        input_tokens=1000,
        output_tokens=1680,
        images_generated=1,
        image_resolution="2k",
    )
    assert img_cost["breakdown_usd"]["text_and_thinking_output_usd"] == 0.0
    assert img_cost["breakdown_usd"]["image_output_usd"] == pytest.approx(0.0504, rel=1e-4)

    vid_cost = calculate_call_cost(
        model="gemini-omni-1.2-flash",
        video_seconds=10.0,
        video_resolution="720p",
    )
    assert vid_cost["breakdown_usd"]["video_output_usd"] == pytest.approx(0.69504, rel=1e-4)

    song_cost = calculate_call_cost(model="lyria-3.5", songs_generated=2)
    assert song_cost["breakdown_usd"]["audio_output_usd"] == pytest.approx(0.16, rel=1e-4)


def test_ledger_persistence_and_hard_budget_stop(monkeypatch):
    monkeypatch.setenv("OMNI_HARD_STOP_LIMIT_USD", "1.00")
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key-123456")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key-789012")

    # Reading an empty ledger should NOT write to disk lazily.
    assert not get_ledger_path().exists()
    empty = load_usage_ledger()
    assert empty["totals"]["total_cost_usd"] == 0.0
    assert not get_ledger_path().exists()

    # Record a small video call under $1.00 (~$0.695) -> persists ledger lazily.
    record_api_usage(
        tool_name="gemini_video_studio",
        model="gemini-omni-1.2-flash",
        video_seconds=10.0,
        video_resolution="720p",
    )
    assert get_ledger_path().is_file()
    saved = json.loads(get_ledger_path().read_text(encoding="utf-8"))
    assert saved["totals"]["total_calls"] == 1
    assert "gemini-omni-1.2-flash" in saved["totals"]["by_model"]
    assert "gemini_video_studio" in saved["totals"]["by_tool"]

    # Regression check: passing context= to enforce_hard_budget_limit must not raise TypeError.
    enforce_hard_budget_limit(estimated_next_cost_usd=0.05, context="gemini_async_swarm[t1]")

    # Exceeding budget locks ledger and purges keys from os.environ.
    with pytest.raises(HardBudgetStopError, match="HARD STOP LIMIT"):
        record_api_usage(
            tool_name="gemini_video_studio",
            model="gemini-omni-1.2-flash",
            video_seconds=10.0,
            video_resolution="720p",
        )
    assert "GEMINI_API_KEY" not in os.environ
    assert "GOOGLE_API_KEY" not in os.environ

    with pytest.raises(HardBudgetStopError, match="swarm_ctx"):
        enforce_hard_budget_limit(context="swarm_ctx")

    # Raising the limit unlocks the ledger cleanly.
    unlocked = set_budget_limit(5.0)
    assert unlocked["hard_stop_triggered"] is False
    assert unlocked["status"] == "ACTIVE"
    enforce_hard_budget_limit(context="unlocked_ok")

    # Setting limit to 0 disables the hard stop.
    unlimited = set_budget_limit(0.0)
    assert unlimited["status"] == "UNLIMITED"
    assert unlimited["totals"]["remaining_budget_usd"] is None
    enforce_hard_budget_limit(estimated_next_cost_usd=9999.0, context="unlimited_ok")

    reset = reset_usage_ledger()
    assert reset["totals"]["total_calls"] == 0
