import pytest
from pathlib import Path

from geometry_audit import audit_scabbard_geometry
from scabbard_generator import (
    CUSTOM_STL_PREVIEW_MODES,
    DEFAULT_SCABBARD_CLEARANCE_MM,
    MIN_SCABBARD_WALL_THICKNESS_MM,
    SCABBARD_SPLIT_MODES,
    SUPPORTED_SCABBARD_BLADE_STYLES,
    blade_center_offset_at,
    blade_envelope,
    blade_half_width_at,
    blade_profile_points,
    cavity_half_width_at,
    generate_custom_stl_scabbard_scad,
    generate_scabbard_scad,
    normalize_custom_stl_scabbard_parameters,
    normalize_scabbard_parameters,
    sanitize_stl_filename,
    scabbard_geometry_bounds,
    scabbard_inner_profile_points,
    scabbard_outer_profile_points,
    outer_half_width_at,
    scabbard_profile_samples,
    validate_custom_stl_upload,
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


def test_removed_scabbard_style_values_normalize_safely():
    params, warnings = normalize_scabbard_parameters("Falchion", preset_metrics(), split_mode="Legacy Preset")
    assert params.blade_profile.blade_type == "falchion"
    assert params.split_mode == "Single Piece"
    assert any("Unsupported scabbard split mode" in message for message in warnings)


def test_unsupported_scabbard_blades_fail_safely():
    with pytest.raises(ValueError, match="Unsupported scabbard blade type"):
        normalize_scabbard_parameters("Needle", preset_metrics())
    audit = audit_scabbard_geometry(preset_metrics(), "Needle")
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

    assert "Digital Forge Scabbard Version 2" in scad
    assert "Clearance is per side" in scad
    assert "blade_profile_points -> scabbard_inner_profile_points" in scad
    assert "module scabbard_cavity_profile_2d()" in scad
    assert "module scabbard_outer_profile_2d()" in scad
    assert "module scabbard_outer_volume()" in scad
    assert "module scabbard_inner_cavity()" in scad
    assert "module scabbard_hollow_shell()" in scad
    assert "module scabbard_throat_cut()" in scad
    assert "module scabbard_final_single_piece()" in scad
    assert "difference()" in scad
    assert "blade_length_mm = 930;" in scad
    final_module = scad.split("module scabbard_final_single_piece()", 1)[1].split("module scabbard_hollow_cutaway", 1)[0]
    assert final_module.index("scabbard_hollow_shell();") < final_module.index("scabbard_throat_cut();")
    assert "scabbard_outer_volume();" not in final_module
    if split_mode in {"Two Piece", "Left/Right Halves"}:
        assert "module scabbard_left_half()" in scad
        assert "module scabbard_right_half()" in scad
        assert "module scabbard_two_piece()" in scad
    elif split_mode == "Front/Back Halves":
        assert "module scabbard_part_a()" in scad
        assert "module scabbard_part_b()" in scad
        assert "module scabbard_two_piece()" in scad
    else:
        assert "module scabbard_single_piece()" in scad


def test_leaf_scabbard_does_not_taper_inward_before_leaf_belly():
    params, _ = normalize_scabbard_parameters("leaf", preset_metrics())
    base = cavity_half_width_at(params, params.blade_profile.ricasso_length_mm)
    belly = cavity_half_width_at(params, params.blade_profile.length_mm * 0.70)
    later_tip = cavity_half_width_at(params, params.blade_profile.length_mm * 0.92)
    blade_base = blade_half_width_at(params.blade_profile, params.blade_profile.ricasso_length_mm)
    blade_belly = blade_half_width_at(params.blade_profile, params.blade_profile.length_mm * 0.70)
    blade_later_tip = blade_half_width_at(params.blade_profile, params.blade_profile.length_mm * 0.92)
    outer_base = outer_half_width_at(params, params.blade_profile.ricasso_length_mm)
    outer_belly = outer_half_width_at(params, params.blade_profile.length_mm * 0.70)
    outer_later_tip = outer_half_width_at(params, params.blade_profile.length_mm * 0.92)
    outer_points = scabbard_outer_profile_points(params)
    belly_y = round(params.blade_profile.length_mm * 0.70, 6)

    assert blade_belly > blade_base
    assert blade_belly > blade_later_tip
    assert belly > base
    assert belly > later_tip
    assert outer_belly > outer_base
    assert outer_belly > outer_later_tip
    assert outer_belly - belly >= MIN_SCABBARD_WALL_THICKNESS_MM
    assert len(outer_points) > 4
    assert any(abs(y - belly_y) < 1e-6 for _x, y in outer_points)


def test_leaf_profile_points_are_full_symmetric_edges():
    params, _ = normalize_scabbard_parameters("leaf", preset_metrics())
    inner_points = scabbard_inner_profile_points(params)
    outer_points = scabbard_outer_profile_points(params)
    blade_points = blade_profile_points(params.blade_profile)
    belly_y = params.blade_profile.length_mm * 0.70

    assert len(blade_points) == 8
    assert len(inner_points) > 4
    assert len(outer_points) > 4
    assert any(y == pytest.approx(belly_y) and x < 0 for x, y in inner_points)
    assert any(y == pytest.approx(belly_y) and x > 0 for x, y in inner_points)
    for y in (params.blade_profile.ricasso_length_mm, belly_y, params.blade_profile.length_mm):
        xs = [x for x, point_y in inner_points if abs(point_y - round(y, 6)) < 1e-6]
        left, right = min(xs), max(xs)
        assert abs(left) == pytest.approx(abs(right))


def test_scabbard_throat_cut_and_cavity_bounds_open_entry_not_tip():
    params, _ = normalize_scabbard_parameters("leaf", preset_metrics())
    bounds = scabbard_geometry_bounds(params)
    scad = generate_scabbard_scad("leaf", preset_metrics())
    cavity_cut_points_text = scad.split("scabbard_cavity_cut_points = ", 1)[1].split(";\n", 1)[0]

    assert bounds.throat_y_mm < 0
    assert bounds.tip_y_mm == pytest.approx(params.outer_end_y_mm)
    assert bounds.max_cavity_half_width_mm < bounds.max_outer_half_width_mm
    assert bounds.outer_half_depth_mm > bounds.cavity_half_depth_mm
    assert f"{params.throat_start_y_mm - 6:g}" in cavity_cut_points_text
    throat_module = scad.split("module scabbard_throat_cut()", 1)[1].split("module scabbard_final_single_piece", 1)[0]
    assert "scabbard_throat_start_y_mm" in throat_module
    assert "scabbard_outer_end_y_mm" not in throat_module


@pytest.mark.parametrize("split_mode", ("Left/Right Halves", "Front/Back Halves"))
def test_scabbard_split_cutters_cover_full_shell_and_split_final_piece(split_mode):
    params, _ = normalize_scabbard_parameters("leaf", preset_metrics(), split_mode=split_mode)
    bounds = scabbard_geometry_bounds(params)
    scad = generate_scabbard_scad("leaf", preset_metrics(), split_mode=split_mode)
    split_section = scad.split("module scabbard_part_a()", 1)[1]

    assert bounds.split_length_bound_mm > params.outer_end_y_mm - params.throat_start_y_mm
    assert bounds.split_width_bound_mm > bounds.max_outer_half_width_mm * 2
    assert bounds.split_depth_bound_mm > params.outer_half_thickness_mm * 2
    assert "intersection()" in split_section
    assert "scabbard_final_single_piece();" in split_section
    assert "scabbard_outer_volume();" not in split_section
    assert "translate([-scabbard_max_outer_half_width_mm" in scad or "translate([0, 0, -scabbard_outer_half_thickness_mm" in scad
    part_a = scad.split("module scabbard_part_a()", 1)[1].split("module scabbard_part_b()", 1)[0]
    assert part_a.index("scabbard_final_single_piece();") < part_a.index("scabbard_split_halfspace_a();")


@pytest.mark.parametrize(
    ("split_mode", "expected_call"),
    [
        ("Single Piece", "scabbard_single_piece();"),
        ("Left/Right Halves", "scabbard_two_piece();"),
        ("Front/Back Halves", "scabbard_two_piece();"),
        ("Two Piece", "scabbard_two_piece();"),
    ],
)
def test_scabbard_production_top_level_calls_final_shell_path(split_mode, expected_call):
    scad = generate_scabbard_scad("leaf", preset_metrics(), split_mode=split_mode)
    top_level = scad.rsplit("module scabbard_", 1)[1]

    assert scad.strip().endswith(expected_call)
    assert "scabbard_final_single_piece();" in scad
    assert "scabbard_outer_volume();\n}" not in top_level


def test_falchion_scabbard_accounts_for_asymmetric_belly_and_throat():
    params, _ = normalize_scabbard_parameters("falchion", preset_metrics())
    left, right = blade_envelope(params.blade_profile)
    throat = cavity_half_width_at(params, params.throat_start_y_mm) * 2
    belly = cavity_half_width_at(params, params.blade_profile.length_mm * 0.84)
    base = cavity_half_width_at(params, 0)

    assert params.blade_profile.blade_type == "falchion"
    assert throat >= (right - left) + params.clearance_per_side_mm * 2
    assert belly > base
    assert not validate_scabbard_fit(params)["warnings"]
    scad = generate_scabbard_scad("falchion", preset_metrics())
    assert "falchion_style_aware_profile" in scad
    assert "blade_profile_points" in scad


def test_curved_scabbard_uses_centerline_offsets_in_fitted_mode():
    params, _ = normalize_scabbard_parameters("curved", preset_metrics())
    mid = blade_center_offset_at(params.blade_profile, params.blade_profile.length_mm * 0.62)
    tip = blade_center_offset_at(params.blade_profile, params.blade_profile.length_mm)
    inner_points = scabbard_inner_profile_points(params)

    assert abs(mid) > 0
    assert abs(tip) > abs(mid)
    assert any(x > 0 for x, _y in inner_points)
    assert not validate_scabbard_fit(params)["warnings"]
    scad = generate_scabbard_scad("curved", preset_metrics())
    assert "curved_style_aware_profile" in scad
    assert "Straight Exterior" in scad


def test_straight_exterior_preserves_fitted_cavity():
    fitted, _ = normalize_scabbard_parameters("falchion", preset_metrics(), fit_mode="Fitted Scabbard")
    straight, _ = normalize_scabbard_parameters("falchion", preset_metrics(), fit_mode="Straight Exterior")

    assert scabbard_inner_profile_points(fitted) == scabbard_inner_profile_points(straight)
    assert scabbard_outer_profile_points(fitted) != scabbard_outer_profile_points(straight)


def test_custom_stl_validation_and_scad_path_safety(monkeypatch):
    import scabbard_generator

    tmp_path = Path("generated/test_custom_stl_validation").resolve()
    upload_dir = tmp_path / "uploaded_stl"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(scabbard_generator, "CUSTOM_STL_DIR", upload_dir)
    stl_path = upload_dir / sanitize_stl_filename("../blade test.stl")
    stl_path.write_text("solid blade\nendsolid blade\n", encoding="utf-8")

    assert sanitize_stl_filename("../blade test.stl") == "blade_test.stl"
    assert validate_custom_stl_upload("blade.stl", 128) == []
    assert validate_custom_stl_upload("blade.obj", 128)
    scad, warnings = generate_custom_stl_scabbard_scad(
        stl_path=stl_path,
        clearance_mm=0.0,
        wall_thickness_mm=0.1,
        scale=100.0,
    )
    assert "Experimental STL-Derived Scabbard" in scad
    assert "import(" in scad
    assert ".." not in scad
    assert warnings
    unsafe_scad, unsafe_warnings = generate_custom_stl_scabbard_scad(stl_path=tmp_path / "outside.stl")
    assert "could not be generated safely" in unsafe_scad
    assert unsafe_warnings


def controlled_test_stl(monkeypatch, name: str = "blade.stl") -> Path:
    import scabbard_generator

    tmp_path = Path("generated/test_custom_stl_shell").resolve()
    upload_dir = tmp_path / "uploaded_stl"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(scabbard_generator, "CUSTOM_STL_DIR", upload_dir)
    stl_path = upload_dir / sanitize_stl_filename(name)
    stl_path.write_text("solid blade\nendsolid blade\n", encoding="utf-8")
    return stl_path


def test_custom_stl_scad_shell_is_outer_minus_inner_expanded_mesh(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    scad, warnings = generate_custom_stl_scabbard_scad(
        stl_path=stl_path,
        clearance_mm=0.7,
        wall_thickness_mm=3.1,
    )

    assert not warnings
    assert "module imported_blade_mesh()" in scad
    assert "module imported_blade_expanded(radius_mm)" in scad
    assert "module stl_scabbard_raw_shell()" in scad
    raw_shell = scad.split("module stl_scabbard_raw_shell()", 1)[1].split("module custom_stl_scabbard_final()", 1)[0]
    assert "difference()" in raw_shell
    assert raw_shell.index("stl_outer_volume();") < raw_shell.index("stl_inner_cavity();")
    assert "stl_clearance_mm = 0.7;" in scad
    assert "stl_shell_wall_mm = 3.1;" in scad
    assert "stl_shell_radius_mm = 3.8;" in scad
    assert "imported_blade_expanded(stl_clearance_mm);" in scad
    assert "imported_blade_expanded(stl_shell_radius_mm);" in scad


def test_custom_stl_outer_radius_is_greater_than_inner_and_invalid_values_clamp(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    params, warnings = normalize_custom_stl_scabbard_parameters(
        stl_path=stl_path,
        clearance_mm=0.0,
        wall_thickness_mm=0.0,
        throat_length_mm=0.0,
    )

    assert params is not None
    assert params.wall_thickness_mm >= MIN_SCABBARD_WALL_THICKNESS_MM
    assert params.clearance_mm >= DEFAULT_SCABBARD_CLEARANCE_MM or params.clearance_mm == 0.35
    assert params.clearance_mm + params.wall_thickness_mm > params.clearance_mm
    assert params.throat_length_mm > 0
    assert any("clearance" in message.lower() for message in warnings)
    assert any("wall thickness" in message.lower() for message in warnings)
    assert any("throat opening" in message.lower() for message in warnings)


def test_custom_stl_scabbard_only_does_not_emit_blade_as_final_positive_geometry(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    scad, _warnings = generate_custom_stl_scabbard_scad(stl_path=stl_path, preview_mode="Scabbard Only")

    top_level = scad.rsplit("module custom_stl_split_preview", 1)[1]
    assert top_level.strip().endswith("custom_stl_scabbard_final();")
    assert "%color" not in top_level
    assert "imported_blade_mesh();" not in top_level
    assert "union()" not in top_level


def test_custom_stl_diagnostic_preview_uses_background_modifier(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    scad, _warnings = generate_custom_stl_scabbard_scad(stl_path=stl_path, preview_mode="Blade Fit Diagnostic")

    top_level = scad.rsplit("module custom_stl_split_preview", 1)[1]
    assert '%color("silver", 0.35) imported_blade_mesh();' in top_level
    assert "custom_stl_scabbard_final();" in top_level
    assert "union()" not in top_level


def test_custom_stl_imported_blade_only_preview_is_separate_mode(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    scad, _warnings = generate_custom_stl_scabbard_scad(stl_path=stl_path, preview_mode="Imported Blade Only")

    assert "Preview mode: Imported Blade Only" in scad
    assert scad.strip().endswith("imported_blade_mesh();")


def test_custom_stl_final_module_subtracts_throat_cut_and_leaves_tip_uncut(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    scad, _warnings = generate_custom_stl_scabbard_scad(stl_path=stl_path, throat_length_mm=22)

    assert "module stl_throat_opening_cut()" in scad
    final_module = scad.split("module custom_stl_scabbard_final()", 1)[1].split("module custom_stl_split_preview", 1)[0]
    assert "difference()" in final_module
    assert final_module.index("stl_scabbard_raw_shell();") < final_module.index("stl_throat_opening_cut();")
    throat_module = scad.split("module stl_throat_opening_cut()", 1)[1].split("module stl_scabbard_raw_shell", 1)[0]
    assert "-5000 + stl_throat_length_mm/2" in throat_module
    assert "10000 + stl_throat_length_mm" in throat_module
    assert "tip" not in throat_module.lower()


@pytest.mark.parametrize("split_mode", ("Left/Right Halves", "Front/Back Halves"))
def test_custom_stl_split_modules_split_final_hollow_shell(monkeypatch, split_mode):
    stl_path = controlled_test_stl(monkeypatch)
    scad, _warnings = generate_custom_stl_scabbard_scad(stl_path=stl_path, split_mode=split_mode)

    split_module = scad.split("module custom_stl_split_preview", 1)[1]
    assert "custom_stl_scabbard_final();" in split_module
    assert "stl_outer_volume();" not in split_module
    assert "imported_blade_mesh();" not in split_module


def test_custom_stl_legacy_preview_setting_normalizes_to_diagnostic(monkeypatch):
    stl_path = controlled_test_stl(monkeypatch)
    params, warnings = normalize_custom_stl_scabbard_parameters(
        stl_path=stl_path,
        preview_imported_mesh=True,
    )

    assert params is not None
    assert not warnings
    assert params.preview_mode == "Blade Fit Diagnostic"
    assert CUSTOM_STL_PREVIEW_MODES[0] == "Scabbard Only"


def test_custom_stl_audit_warns_for_reversed_or_ambiguous_throat(monkeypatch):
    from geometry_audit import audit_custom_stl_scabbard_geometry

    stl_path = controlled_test_stl(monkeypatch, "full_sword_with_guard.stl")
    reversed_audit = audit_custom_stl_scabbard_geometry(str(stl_path), rotate_z_deg=180)
    ambiguous_audit = audit_custom_stl_scabbard_geometry(str(stl_path), rotate_z_deg=90)

    assert any("likely reversed" in message for message in reversed_audit["warnings"])
    assert any("Full-sword STL" in message for message in reversed_audit["warnings"])
    assert any("ambiguous" in message for message in ambiguous_audit["warnings"])
