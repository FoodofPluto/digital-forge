import pytest

from geometry_audit import audit_scabbard_geometry
from scabbard_generator import (
    DEFAULT_SCABBARD_CLEARANCE_MM,
    MIN_SCABBARD_WALL_THICKNESS_MM,
    SCABBARD_SPLIT_MODES,
    SUPPORTED_SCABBARD_BLADE_STYLES,
    blade_half_width_at,
    cavity_half_width_at,
    generate_scabbard_scad,
    normalize_scabbard_parameters,
    outer_half_width_at,
    scabbard_profile_samples,
    validate_scabbard_fit,
)
from sword_presets import SWORD_PRESETS


def preset_metrics(sword_type: str = "longsword") -> dict[str, float]:
    return {name: spec["default"] for name, spec in SWORD_PRESETS[sword_type].items()}


@pytest.mark.parametrize("blade_type", SUPPORTED_SCABBARD_BLADE_STYLES)
def test_scabbard_inherits_sword_prop_clamped_blade_dimensions(blade_type):
    metrics = preset_metrics()
    metrics["blade_tip_width_mm"] = 1.0
    metrics["blade_thickness_mm"] = 1.0
    params, warnings = normalize_scabbard_parameters(blade_type, metrics)

    assert not warnings
    assert params.blade_profile.length_mm == metrics["blade_length_mm"]
    assert params.blade_profile.base_width_mm == metrics["blade_base_width_mm"]
    assert params.blade_profile.tip_width_mm == metrics["blade_tip_width_mm"]
    assert params.blade_profile.ricasso_length_mm == metrics["ricasso_length_mm"]
    assert params.blade_profile.prop_tip_width_mm == 3.0
    assert params.blade_profile.prop_blade_thickness_mm == 2.4


@pytest.mark.parametrize("blade_type", SUPPORTED_SCABBARD_BLADE_STYLES)
@pytest.mark.parametrize(
    "blade_width_mm",
    [
        SWORD_PRESETS["longsword"]["blade_base_width_mm"]["min"],
        SWORD_PRESETS["longsword"]["blade_base_width_mm"]["default"],
        SWORD_PRESETS["greatsword"]["blade_base_width_mm"]["max"],
    ],
)
def test_scabbard_blade_width_validation_matrix(blade_type, blade_width_mm):
    metrics = preset_metrics()
    metrics["blade_base_width_mm"] = blade_width_mm
    params, warnings = normalize_scabbard_parameters(blade_type, metrics)
    audit = validate_scabbard_fit(params)

    assert not warnings
    assert not audit["warnings"]
    for y in scabbard_profile_samples(params):
        blade_half = blade_half_width_at(params.blade_profile, min(y, params.blade_profile.length_mm))
        assert cavity_half_width_at(params, y) >= blade_half + params.clearance_per_side_mm
        assert outer_half_width_at(params, y) - cavity_half_width_at(params, y) >= MIN_SCABBARD_WALL_THICKNESS_MM


@pytest.mark.parametrize("blade_type", SUPPORTED_SCABBARD_BLADE_STYLES)
@pytest.mark.parametrize(
    "blade_thickness_mm",
    [
        SWORD_PRESETS["dagger"]["blade_thickness_mm"]["min"],
        SWORD_PRESETS["greatsword"]["blade_thickness_mm"]["max"],
    ],
)
def test_scabbard_blade_thickness_validation_matrix(blade_type, blade_thickness_mm):
    metrics = preset_metrics()
    metrics["blade_thickness_mm"] = blade_thickness_mm
    params, warnings = normalize_scabbard_parameters(blade_type, metrics)

    assert not warnings
    assert params.cavity_half_thickness_mm >= params.blade_profile.prop_blade_thickness_mm / 2 + DEFAULT_SCABBARD_CLEARANCE_MM
    assert params.outer_half_thickness_mm - params.cavity_half_thickness_mm >= MIN_SCABBARD_WALL_THICKNESS_MM
    assert not validate_scabbard_fit(params)["warnings"]


@pytest.mark.parametrize("blade_type", SUPPORTED_SCABBARD_BLADE_STYLES)
@pytest.mark.parametrize("split_mode", SCABBARD_SPLIT_MODES)
def test_completion_gate_profile_level_blade_fits_scabbard(blade_type, split_mode):
    metrics = preset_metrics()
    params, warnings = normalize_scabbard_parameters(blade_type, metrics, split_mode=split_mode)
    audit = validate_scabbard_fit(params)

    assert not warnings
    assert not audit["warnings"]
    sample_positions = [
        0.0,
        metrics["blade_length_mm"] * 0.25,
        metrics["blade_length_mm"] * 0.42,
        metrics["blade_length_mm"] * 0.70,
        metrics["blade_length_mm"] * 0.92,
    ]
    for y in sample_positions:
        assert cavity_half_width_at(params, y) >= blade_half_width_at(params.blade_profile, y) + params.clearance_per_side_mm
        assert params.cavity_half_thickness_mm >= params.blade_profile.prop_blade_thickness_mm / 2 + params.clearance_per_side_mm
        assert outer_half_width_at(params, y) - cavity_half_width_at(params, y) >= MIN_SCABBARD_WALL_THICKNESS_MM
        assert params.outer_half_thickness_mm - params.cavity_half_thickness_mm >= MIN_SCABBARD_WALL_THICKNESS_MM

    assert params.throat_start_y_mm < 0
    assert cavity_half_width_at(params, params.throat_start_y_mm) >= params.blade_profile.base_width_mm / 2 + params.clearance_per_side_mm
    assert params.cavity_end_y_mm > params.blade_profile.length_mm
    assert params.outer_end_y_mm - params.cavity_end_y_mm >= MIN_SCABBARD_WALL_THICKNESS_MM


def test_leaf_scabbard_cavity_follows_leaf_widest_section():
    params, _ = normalize_scabbard_parameters("leaf", preset_metrics())
    lower_mid = cavity_half_width_at(params, params.blade_profile.length_mm * 0.42)
    widest = cavity_half_width_at(params, params.blade_profile.length_mm * 0.70)
    near_tip = cavity_half_width_at(params, params.blade_profile.length_mm * 0.92)

    assert widest > lower_mid
    assert widest > near_tip


def test_tapered_scabbard_cavity_follows_taper():
    params, _ = normalize_scabbard_parameters("tapered", preset_metrics())
    base = cavity_half_width_at(params, 0)
    mid = cavity_half_width_at(params, params.blade_profile.length_mm * 0.5)
    tip = cavity_half_width_at(params, params.blade_profile.length_mm)

    assert base > mid > tip


def test_unsupported_scabbard_blades_fail_safely():
    with pytest.raises(ValueError, match="Unsupported scabbard blade type"):
        normalize_scabbard_parameters("Falchion", preset_metrics())
    audit = audit_scabbard_geometry(preset_metrics(), "Curved")
    assert audit["warnings"]
    assert "Unsupported scabbard blade type" in audit["warnings"][0]


def test_scabbard_clamps_clearance_and_wall_thickness_with_audit_messages():
    audit = audit_scabbard_geometry(
        preset_metrics(),
        "tapered",
        clearance_per_side_mm=0.0,
        wall_thickness_mm=0.1,
    )

    combined = " ".join(audit["warnings"])
    assert "Clearance below" in combined
    assert "Wall thickness below" in combined
    assert "clamped" in combined


@pytest.mark.parametrize("split_mode", SCABBARD_SPLIT_MODES)
def test_scabbard_scad_contains_named_modules_and_readable_parameters(split_mode):
    scad = generate_scabbard_scad("tapered", preset_metrics(), split_mode=split_mode)

    assert "Digital Forge Scabbard Version 1" in scad
    assert "Clearance is per side" in scad
    assert "module scabbard_cavity_profile_2d()" in scad
    assert "module scabbard_outer_profile_2d()" in scad
    assert "module scabbard_body()" in scad
    assert "difference()" in scad
    assert "blade_length_mm = 930;" in scad
    if split_mode == "Two Piece":
        assert "module scabbard_left_half()" in scad
        assert "module scabbard_right_half()" in scad
        assert "module scabbard_two_piece()" in scad
    else:
        assert "module scabbard_single_piece()" in scad
