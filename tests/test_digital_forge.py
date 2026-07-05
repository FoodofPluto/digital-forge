from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from design_notes import get_design_notes
from geometry_audit import audit_geometry
from preview_service import build_openscad_command, export_with_openscad
from realism_rules import check_realism
from scad_generator import (
    BLADE_STYLES,
    GUARD_STYLES,
    VISIBILITY_PRESETS,
    disk_guard_diameter,
    generate_scad,
    get_guard_rotation,
    has_visible_components,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS
from showcase_presets import SHOWCASE_PRESETS, generate_showcase_scad, preset_metrics as showcase_metrics


def preset_metrics(sword_type: str) -> dict[str, float]:
    return {name: spec["default"] for name, spec in SWORD_PRESETS[sword_type].items()}


def test_presets_contain_all_required_metrics():
    assert SWORD_PRESETS
    for preset in SWORD_PRESETS.values():
        assert set(preset) == set(REQUIRED_METRICS)
        for spec in preset.values():
            assert spec["min"] <= spec["default"] <= spec["max"]


def test_showcase_contains_requested_named_configurations():
    assert [preset.name for preset in SHOWCASE_PRESETS] == [
        "Straight Sword",
        "Falchion",
        "Curved Saber",
        "Crescent Guard Sword",
        "Disk Guard Sword",
        "Spike Pommel Sword",
        "Leaf Blade Sword",
    ]


def test_showcase_presets_generate_with_supported_values():
    for preset in SHOWCASE_PRESETS:
        assert preset.sword_type in SWORD_PRESETS
        assert preset.blade_style in BLADE_STYLES
        assert preset.guard_style in GUARD_STYLES
        assert preset.pommel_style in ("sphere", "wheel", "ring", "spike")
        assert set(showcase_metrics(preset)) == set(REQUIRED_METRICS)
        scad = generate_showcase_scad(preset)
        assert f"Digital Forge Version 4: {preset.sword_type}" in scad
        assert f"Blade style: {preset.blade_style}" in scad


def test_every_preset_has_ricasso():
    assert all("ricasso_length_mm" in preset for preset in SWORD_PRESETS.values())


def test_realism_checker_warns_for_out_of_range_value():
    metrics = preset_metrics("longsword")
    metrics["blade_length_mm"] = 2000
    warnings = check_realism("longsword", metrics)
    assert any("Blade Length" in warning and "2000 mm" in warning for warning in warnings)


def test_scad_contains_selection_and_metrics():
    scad = generate_scad("rapier", preset_metrics("rapier"), "needle", "disk", "ring")
    assert "Digital Forge Version 4: rapier" in scad
    assert "Blade style: needle" in scad
    assert "Guard style: disk" in scad
    assert "blade_length_mm = 1050;" in scad
    assert "grip_length_mm = 120;" in scad


def test_blade_style_changes_generated_geometry():
    metrics = preset_metrics("longsword")
    tapered = generate_scad("longsword", metrics, "tapered", "straight", "wheel")
    leaf = generate_scad("longsword", metrics, "leaf", "straight", "wheel")
    assert tapered != leaf
    assert "blade_length_mm*0.70" not in tapered
    assert "blade_length_mm*0.70" in leaf


def test_curved_blade_is_restored_and_has_visible_sweep():
    assert "curved" in BLADE_STYLES
    scad = generate_scad("longsword", preset_metrics("longsword"), "curved", "straight", "wheel")
    assert "blade_base_width_mm*0.72, blade_length_mm" in scad
    assert "blade_base_width_mm*0.12, blade_length_mm*0.62" in scad


def test_all_blade_variants_emit_distinct_profiles():
    metrics = preset_metrics("longsword")
    outputs = {
        style: generate_scad("longsword", metrics, style, "straight", "wheel")
        for style in BLADE_STYLES
    }
    assert len(set(outputs.values())) == len(BLADE_STYLES)


def test_falchion_has_pronounced_forward_chopping_profile():
    scad = generate_scad("falchion", preset_metrics("falchion"), "falchion", "straight", "wheel")
    assert "blade_base_width_mm*0.78, blade_length_mm*0.84" in scad
    assert "blade_base_width_mm*0.58, blade_length_mm*0.88" in scad
    assert "angled clipped point" in scad


def test_optional_blade_details_emit_geometry():
    scad = generate_scad(
        "greatsword",
        preset_metrics("greatsword"),
        "tapered",
        "downturned",
        "spike",
        fuller_enabled=True,
        fuller_length_ratio=0.7,
        fuller_width_mm=16,
        ridge_enabled=True,
    )
    assert "module fuller_geometry()" in scad
    assert "fuller_geometry();" in scad
    assert "module ridge_geometry()" in scad
    assert "ridge_geometry();" in scad


def test_design_notes_exist_for_every_sword_type():
    for sword_type in SWORD_PRESETS:
        assert get_design_notes(sword_type, "tapered", "straight", "sphere").strip()


def test_realism_warns_for_obvious_bad_ratios():
    metrics = preset_metrics("greatsword")
    metrics.update(grip_length_mm=50, guard_width_mm=80, ricasso_length_mm=500)
    warnings = check_realism(
        "greatsword", metrics, fuller_enabled=True, fuller_length_ratio=1.2
    )
    combined = " ".join(warnings).lower()
    assert "grip is unusually short" in combined
    assert "guard is narrow" in combined
    assert "fuller length is longer" in combined
    assert "ricasso is unusually long" in combined


def test_geometry_contract_and_connected_anchors():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "sphere"
    )
    assert "grip_start_y = -grip_length_mm;" in scad
    assert "grip_end_y = 0;" in scad
    assert "guard_bottom_y = grip_end_y;" in scad
    assert "guard_center_y = guard_bottom_y + guard_height_mm/2;" in scad
    assert "guard_top_y = guard_bottom_y + guard_height_mm;" in scad
    assert "blade_start_y = guard_top_y;" in scad
    assert "pommel_center_y = grip_start_y - pommel_size_mm/2" in scad
    assert "translate([0, blade_start_y, 0]) blade();" in scad
    assert "translate([0, guard_center_y, 0]) rotate([0, 0, 0]) guard();" in scad


def test_grip_is_elliptical_and_preserves_external_length_metric():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "sphere"
    )
    assert "grip_depth_mm/grip_width_mm" in scad
    assert "cylinder(h=grip_length_mm, d=grip_width_mm, center=true)" in scad
    assert "cube([grip_width_mm, grip_length_mm, grip_width_mm]" not in scad


def test_internal_tang_is_distinct_and_crosses_blade_grip_boundary():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "sphere"
    )
    assert "module tang_core()" in scad
    assert "tang_width_mm" in scad and "tang_thickness_mm" in scad
    assert "tang_length_mm = grip_length_mm" not in scad
    assert "tang_bottom_y = grip_start_y - tang_pommel_overlap_mm;" in scad
    assert "tang_top_y = blade_start_y + tang_blade_overlap_mm;" in scad
    assert "translate([0, tang_center_y, 0]) tang_core();" in scad


def test_blade_output_enforces_blunt_prop_minimums():
    scad = generate_scad(
        "rapier", preset_metrics("rapier"), "needle", "straight", "wheel"
    )
    assert "min_prop_tip_width_mm = 3;" in scad
    assert "min_prop_blade_thickness_mm = 2.4;" in scad
    assert "prop_tip_width_mm = max(blade_tip_width_mm" in scad
    assert "linear_extrude(height=prop_blade_thickness_mm" in scad
    assert "[0, blade_length_mm]" not in scad


def test_guard_orientations_disk_cap_and_falchion_profile():
    metrics = preset_metrics("greatsword")
    crescent = generate_scad("greatsword", metrics, "falchion", "crescent", "wheel")
    downturned = generate_scad("greatsword", metrics, "falchion", "downturned", "wheel")
    disk = generate_scad("greatsword", metrics, "tapered", "disk", "wheel")
    assert "Pronounced crescent" in crescent
    assert "toward +Y" in downturned
    assert crescent != downturned
    assert "forward-heavy belly" in crescent
    assert "disk_guard_diameter_mm" in disk
    assert "capped by Python" in disk


def test_crescent_and_spike_use_corrected_anchors():
    metrics = preset_metrics("longsword")
    crescent = generate_scad("longsword", metrics, "tapered", "crescent", "wheel")
    spike = generate_scad("longsword", metrics, "tapered", "straight", "spike")
    assert "guard_height_mm/guard_width_mm" in crescent
    assert "scale([1.18" in crescent
    assert "guard_height_mm*0.42" in crescent
    assert "pommel_anchor_y = grip_start_y + pommel_overlap_mm;" in spike
    assert "Local Y=0 is the attachment face" in spike
    assert "translate([0, pommel_anchor_y, 0]) pommel();" in spike


def test_disk_guard_size_is_capped():
    metrics = preset_metrics("greatsword")
    metrics["guard_width_mm"] = 1000
    assert disk_guard_diameter(metrics) == metrics["blade_base_width_mm"] * 3.25


def test_geometry_audit_reports_invalid_ratios():
    metrics = preset_metrics("longsword")
    metrics.update(grip_length_mm=10, guard_width_mm=10)
    audit = audit_geometry(metrics, "longsword", "tapered", "straight", "sphere")
    assert len(audit["warnings"]) >= 2


def test_geometry_audit_reports_normal_contacts_and_orientation():
    audit = audit_geometry(
        preset_metrics("longsword"), "longsword", "tapered", "crescent", "sphere"
    )
    combined = " ".join(audit["passes"])
    assert "Pommel-to-grip contact" in combined
    assert "Grip-to-guard contact" in combined
    assert "Guard-to-blade contact" in combined
    assert "pronounced silhouette" in combined
    assert "Oval grip" in combined
    assert "tang/core extends" in combined
    assert "minimum blunt edge thickness" in combined


def test_ring_guard_is_removed_from_available_options():
    assert "ring" not in GUARD_STYLES


def test_disk_guard_uses_y_axis_and_shared_contact_anchor():
    scad = generate_scad("longsword", preset_metrics("longsword"), "tapered", "disk", "wheel")
    assert "rotate([90, 0, 0])" in scad
    assert "guard_bottom_y = grip_end_y;" in scad
    assert "blade_start_y = guard_top_y;" in scad


def test_guard_rotation_rules_cover_falchion_and_curved_profiles():
    assert get_guard_rotation("falchion", "tapered") == 90
    assert get_guard_rotation("longsword", "falchion") == 90
    assert get_guard_rotation("longsword", "curved") == 90
    assert get_guard_rotation("longsword", "tapered") == 0
    for sword_type, blade_style in (("falchion", "tapered"), ("longsword", "falchion"), ("longsword", "curved")):
        scad = generate_scad(sword_type, preset_metrics(sword_type), blade_style, "crescent", "wheel")
        assert "rotate([0, 90, 0]) guard();" in scad


def test_geometry_audit_bad_dimensions_return_warnings_not_exceptions():
    metrics = {name: -1 for name in REQUIRED_METRICS}
    audit = audit_geometry(metrics, "unknown", "unknown", "unknown", "unknown")
    assert audit["warnings"]
    assert any("Unsupported sword type" in warning for warning in audit["warnings"])
    assert any("must be positive" in warning for warning in audit["warnings"])


def test_debug_mode_adds_markers_and_normal_mode_omits_them():
    metrics = preset_metrics("longsword")
    normal = generate_scad("longsword", metrics, "tapered", "straight", "sphere")
    debug = generate_scad(
        "longsword",
        metrics,
        "tapered",
        "straight",
        "sphere",
        debug_geometry=True,
    )
    assert "DEBUG GEOMETRY ENABLED" not in normal
    assert "module debug_markers()" not in normal
    assert "DEBUG GEOMETRY ENABLED" in debug
    assert "DEBUG CENTERLINE" in debug
    assert "DEBUG BOUNDS" in debug
    assert "debug_anchor(blade_start_y" in debug
    assert "debug_anchor(pommel_center_y" in debug


def test_preview_command_and_missing_openscad_are_safe():
    output_path = Path("generated/preview.png")
    scad_path = Path("generated/preview.scad")
    command = build_openscad_command(
        r"C:\Program Files\OpenSCAD\openscad.exe", output_path, scad_path
    )
    assert command[0] == r"C:\Program Files\OpenSCAD\openscad.exe"
    assert command[1] == "-o"
    with patch("preview_service.subprocess.run", side_effect=FileNotFoundError):
        result = export_with_openscad("cube(1);", "missing-openscad")
        ok, message, output = result
    assert not ok and output is None and "not found" in message
    assert result.error_code == "missing_executable"


def test_preview_command_failure_is_safe():
    failed = CompletedProcess(
        args=["openscad"], returncode=1, stdout="", stderr="Parser error"
    )
    with patch("preview_service.subprocess.run", return_value=failed):
        result = export_with_openscad("not valid scad", "openscad")
    assert not result.success
    assert result.path is None
    assert result.error_code == "command_failed"
    assert "Parser error" in result.message


def test_preview_rejects_empty_scad_and_invalid_executable_path():
    empty = export_with_openscad("   ", "openscad")
    invalid_path = export_with_openscad("cube(1);", r"C:\missing\openscad.exe")
    assert empty.error_code == "invalid_scad"
    assert invalid_path.error_code == "invalid_executable"


def _assembly_calls(scad: str) -> str:
    return scad.rsplit("// Visible components remain at their full-assembly anchors.", 1)[1]


def test_full_sword_visibility_is_the_default():
    scad = generate_scad("longsword", preset_metrics("longsword"), "tapered", "straight", "sphere")
    calls = _assembly_calls(scad)
    assert "Visible components: blade, tang, guard, grip, pommel" in scad
    assert all(call in calls for call in ("blade();", "tang_core();", "guard();", "grip();", "pommel();"))


def test_blade_and_tang_only_excludes_other_components():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "sphere",
        visible_components=VISIBILITY_PRESETS["Blade + tang only"],
    )
    calls = _assembly_calls(scad)
    assert "blade();" in calls and "tang_core();" in calls
    assert all(call not in calls for call in ("guard();", "grip();", "pommel();"))


def test_handle_and_guard_only_presets_emit_expected_components():
    metrics = preset_metrics("longsword")
    handle = _assembly_calls(generate_scad(
        "longsword", metrics, "tapered", "straight", "sphere",
        visible_components=VISIBILITY_PRESETS["Handle assembly only"],
    ))
    guard = _assembly_calls(generate_scad(
        "longsword", metrics, "tapered", "straight", "sphere",
        visible_components=VISIBILITY_PRESETS["Guard/hilt only"],
    ))
    assert all(call in handle for call in ("tang_core();", "grip();", "pommel();"))
    assert "blade();" not in handle and "guard();" not in handle
    assert "guard();" in guard
    assert all(call not in guard for call in ("blade();", "tang_core();", "grip();", "pommel();"))
    assert "translate([0, guard_center_y, 0])" in guard


def test_hiding_grip_keeps_tang_and_hiding_guard_keeps_other_parts():
    metrics = preset_metrics("longsword")
    no_grip = _assembly_calls(generate_scad(
        "longsword", metrics, "tapered", "straight", "sphere",
        visible_components={"grip": False},
    ))
    no_guard = _assembly_calls(generate_scad(
        "longsword", metrics, "tapered", "straight", "sphere",
        visible_components={"guard": False},
    ))
    assert "grip();" not in no_grip and "tang_core();" in no_grip
    assert "guard();" not in no_guard
    assert all(call in no_guard for call in ("blade();", "tang_core();", "grip();", "pommel();"))


def test_geometry_audit_skips_intentionally_hidden_component_checks():
    metrics = preset_metrics("longsword")
    metrics.update(blade_length_mm=-1, grip_length_mm=10, guard_width_mm=1000, pommel_size_mm=200)
    visible = VISIBILITY_PRESETS["Tang only"]
    audit = audit_geometry(metrics, "longsword", "unknown", "unknown", "unknown", visible)
    combined = " ".join(audit["warnings"])
    assert "Blade Length" not in combined
    assert "Grip length is below" not in combined
    assert "Guard width exceeds" not in combined
    assert "Pommel radius exceeds" not in combined
    assert any("Assembly view: tang" in message for message in audit["info"])
    assert any("tang/core extends" in message for message in audit["passes"])


def test_empty_component_selection_is_safe_and_reported():
    hidden = {name: False for name in ("blade", "tang", "guard", "grip", "pommel")}
    metrics = {name: -1 for name in REQUIRED_METRICS}
    scad = generate_scad(
        "longsword", metrics, "tapered", "straight", "sphere", visible_components=hidden
    )
    audit = audit_geometry(
        metrics, "longsword", "tapered", "straight", "sphere", hidden
    )
    assert not has_visible_components(hidden)
    assert "Visible components: none" in scad
    assert "EMPTY ASSEMBLY" in scad
    assert not audit["warnings"]
    assert any("no components visible" in message for message in audit["info"])
    assert any("preview or export" in message for message in audit["info"])


def test_one_visible_component_still_generates_normal_scad():
    visible = {name: name == "blade" for name in ("blade", "tang", "guard", "grip", "pommel")}
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "sphere",
        visible_components=visible,
    )
    assert has_visible_components(visible)
    assert "module blade()" in scad
    assert "translate([0, blade_start_y, 0]) blade();" in scad
    assert "EMPTY ASSEMBLY" not in scad
