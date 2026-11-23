"""Offline tests for media utilities and Pydantic v2 response schemas."""

from __future__ import annotations

import wave
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from gemini_omni_mcp.media import (
    extract_json_text,
    save_pcm_or_audio_bytes,
)
from gemini_omni_mcp.schemas import (
    ArgonJudgeEvaluation,
    Asset3DSpecResponse,
    MaterialHexLayer,
    RLAIF3DCriticResponse,
)


def test_save_pcm_or_audio_bytes_wraps_raw_pcm(tmp_path):
    pcm_data = b"\x00\x01" * 4800  # 0.2s of 24kHz mono 16-bit PCM
    out_wav = tmp_path / "audio" / "test.wav"
    save_pcm_or_audio_bytes(pcm_data, "audio/L16;rate=24000", out_wav)

    assert out_wav.is_file()
    raw = out_wav.read_bytes()
    assert raw[:4] == b"RIFF"
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() == 4800


def test_extract_json_text_strips_fences():
    resp = SimpleNamespace(
        text='Here is the output:\n```json\n{"score": 97, "passed": true}\n```\nDone.'
    )
    extracted = extract_json_text(resp)
    assert extracted == '{"score": 97, "passed": true}'


def test_schemas_validation_and_hex_normalization():
    mat1 = MaterialHexLayer(part_name="trim", hex_color="#abc")
    mat2 = MaterialHexLayer(part_name="body", hex_color="ff00aa")
    assert mat1.hex_color == "#AABBCC"
    assert mat2.hex_color == "#FF00AA"

    with pytest.raises(ValidationError):
        MaterialHexLayer(part_name="bad", hex_color="not-a-hex")

    spec = Asset3DSpecResponse.model_validate(
        {
            "subject_name": "Lantern Drone",
            "entity_type": "prop",
            "silhouette_features": ["ring antenna", "glass dome"],
            "palette": [{"part_name": "housing", "hex_color": "#2b303a"}],
            "proportions": [
                {
                    "part_name": "body",
                    "width_m": 0.4,
                    "depth_m": 0.4,
                    "height_m": 0.5,
                    "z_center_m": 0.25,
                    "notes": "Beveled cylinder",
                }
            ],
            "triangle_budget_limit": 5000,
            "geometry_rules": ["Offset decals >= 0.01m"],
        }
    )
    assert spec.palette[0].hex_color == "#2B303A"

    critic = RLAIF3DCriticResponse.model_validate(
        {
            "score": 91,
            "passed": True,
            "angle_scores": {"front": 94, "back": 88},
            "visual_bugs": [],
            "exact_coordinate_and_mesh_fixes": [],
        }
    )
    assert critic.score == 91

    judge = ArgonJudgeEvaluation.model_validate(
        {
            "score": 96,
            "passed": True,
            "rear_view_verdict": "Back geometry matches silhouette.",
            "geometry_and_topology_audit": "Within budget, clean transforms.",
            "visual_bugs": [],
            "rewritten_script": None,
        }
    )
    assert judge.passed is True
