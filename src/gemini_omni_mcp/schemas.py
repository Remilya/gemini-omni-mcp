"""Generalized Pydantic v2 schemas for structured Gemini 3D CAD outputs."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class MaterialHexLayer(BaseModel):
    part_name: str = Field(
        description="Component or surface name (e.g. primary_coat, trim_metal, roof_slate, emissive_glass)"
    )
    hex_color: str = Field(description="Canonical HEX color in #RRGGBB format")
    roughness: float = Field(
        ge=0.0, le=1.0, default=0.75, description="PBR surface roughness (0.0-1.0)"
    )
    metallic: float = Field(
        ge=0.0, le=1.0, default=0.0, description="PBR metallic value (0.0-1.0)"
    )
    is_emissive: bool = Field(
        default=False,
        description="True if this material is self-lit or emissive",
    )
    emission_hex: Optional[str] = Field(
        default=None, description="Optional #RRGGBB emission color if is_emissive is True"
    )
    emission_strength: float = Field(
        ge=0.0, default=0.0, description="Principled BSDF emission strength"
    )

    @field_validator("hex_color")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        v = value.strip().upper()
        if not v.startswith("#"):
            v = "#" + v
        if re.match(r"^#[0-9A-F]{3}$", v):
            v = "#" + "".join(ch * 2 for ch in v[1:])
        if not re.match(r"^#[0-9A-F]{6}$", v):
            raise ValueError(f"Invalid HEX color: {value!r}")
        return v


class PartProportionMetric(BaseModel):
    part_name: str = Field(description="Component name")
    width_m: float = Field(description="Target width (X-axis) in meters")
    depth_m: float = Field(description="Target depth (Y-axis) in meters")
    height_m: float = Field(description="Target height (Z-axis) in meters")
    z_center_m: float = Field(description="Target center Z elevation in meters")
    notes: str = Field(description="Geometric construction notes (primitive, bevel/taper, offsets)")


class Asset3DSpecResponse(BaseModel):
    subject_name: str
    entity_type: Literal["character", "prop", "architecture", "environment", "vehicle", "other"]
    silhouette_features: list[str] = Field(
        default_factory=list,
        description="Key silhouette landmarks, accessories, or structural components",
    )
    palette: list[MaterialHexLayer] = Field(
        description="Pixel-sampled #RRGGBB material palette covering major parts and accents"
    )
    proportions: list[PartProportionMetric] = Field(
        description="Measured 3D proportions and coordinates in meters"
    )
    triangle_budget_limit: int = Field(
        default=10000,
        ge=100,
        description="Target triangle budget limit",
    )
    geometry_rules: list[str] = Field(
        default_factory=list,
        description="Explicit non-overlapping and anti-Z-fighting offset rules",
    )


class MeshFixItem(BaseModel):
    target_object_or_function: str = Field(
        description="Name of the 3D object or builder function to modify"
    )
    issue_detected: str = Field(
        description="Specific visual or geometric defect observed in the render"
    )
    exact_coordinate_or_code_fix: str = Field(
        description="Concrete coordinate delta, scale vector, or code change to resolve the defect"
    )


class RLAIF3DCriticResponse(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall 3D fidelity score (0-100)")
    passed: bool = Field(description="True if score meets the quality bar")
    angle_scores: dict[str, int] = Field(
        description="Per-angle scores across rendered views"
    )
    visual_bugs: list[str] = Field(
        description="Visual, silhouette, proportion, color, or Z-fighting defects found"
    )
    exact_coordinate_and_mesh_fixes: list[MeshFixItem] = Field(
        description="Concrete geometric and coordinate fixes for the 3D script"
    )


class ArgonJudgeEvaluation(BaseModel):
    score: int = Field(
        ge=0,
        le=100,
        description="Supreme Judge score (0-100). Must be >= 95 with zero severe defects to pass.",
    )
    passed: bool = Field(
        description="True ONLY if score >= 95 and all rendered views match the references and rules"
    )
    rear_view_verdict: str = Field(
        description="Detailed audit of the rear/back view and occluded angles"
    )
    geometry_and_topology_audit: str = Field(
        description="Audit of topology, material separation, triangle budget, transforms, and Z-fighting offsets"
    )
    visual_bugs: list[str] = Field(
        default_factory=list,
        description="Remaining visual or mathematical bugs requiring script patches",
    )
    rewritten_script: Optional[str] = Field(
        default=None,
        description="Optional complete updated script if synthesized directly",
    )
