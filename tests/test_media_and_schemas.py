"""Offline tests for media utilities and Pydantic v2 response schemas."""

from __future__ import annotations

import io
import wave
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from gemini_omni_mcp.media import (
    build_numbered_contact_grid,
    extract_json_text,
    save_pcm_or_audio_bytes,
)
from gemini_omni_mcp.schemas import (
    ArgonJudgeEvaluation,
    Asset3DSpecResponse,
    CuratedRefsResponse,
    MaterialHexLayer,
    RLAIF3DCriticResponse,
)


def test_build_numbered_contact_grid_and_corrupt_fallback(tmp_path):
    img1 = tmp_path / "front.png"
    img2 = tmp_path / "side.png"
    Image.new("RGB", (64, 64), (200, 50, 50)).save(img1, format="PNG")
    Image.new("RGB", (120, 80), (50, 180, 90)).save(img2, format="PNG")
    missing = tmp_path / "missing.png"

    grid_bytes, meta = build_numbered_contact_grid(
        [str(img1), str(img2), str(missing)], cols=2
    )
    assert grid_bytes[:2] == b"\xff\xd8"  # Valid JPEG header
    with Image.open(io.BytesIO(grid_bytes)) as grid_im:
        assert grid_im.size[0] == 840
        assert grid_im.size[1] > 0

    assert len(meta) == 3
    assert meta[0]["width"] == 64 and meta[0]["height"] == 64
    assert meta[1]["width"] == 120 and meta[1]["height"] == 80
    assert "error" in meta[2]


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

    curated = CuratedRefsResponse.model_validate(
        {
            "selected_refs": [
                {
                    "index": 0,
                    "file_path": "front.png",
                    "view_category": "front",
                    "score": 9.5,
                    "what_it_is_good_for": "Crisp front silhouette",
                }
            ],
            "rejected_indices": [1],
            "curation_summary": "Selected sharp front view.",
        }
    )
    assert curated.selected_refs[0].view_category == "front"

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
