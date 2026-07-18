from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

from app_config import load_config, save_openscad_path
from design_notes import get_design_notes
from geometry_audit import audit_bracer_geometry, audit_geometry, audit_pauldron_geometry
from preview_service import (
    BRACER_CAMERA_PRESETS,
    DEFAULT_OPENSCAD_TIMEOUT_SECONDS,
    SCABBARD_CAMERA_PRESETS,
    build_openscad_command,
    export_preview_set,
    export_with_openscad,
    resolve_openscad_executable,
)
from realism_rules import check_realism
from scad_generator import (
    ARMOR_TYPES,
    BLADE_STYLES,
    BRACER_BINDING_STYLES,
    BRACER_PANEL_ANGLE_SEGMENTS,
    BRACER_PANEL_LENGTH_SEGMENTS,
    BRACER_PANEL_TYPES,
    BRACER_STYLES,
    DEFAULT_BRACER_METRICS,
    PAULDRON_STYLES,
    GUARD_STYLES,
    VISIBILITY_PRESETS,
    blade_detail_bounds,
    blade_detail_offset_for_position,
    clamp_blade_detail_offset,
    compute_blade_detail_corridor,
    centered_peg_hole_positions,
    disk_guard_diameter,
    generate_armor_scad,
    generate_pauldron_scad,
    generate_scad,
    get_guard_rotation,
    has_visible_components,
    bracer_closure_layout_metrics,
    normalize_bracer_panel_type,
    resolve_render_quality_fn,
    resolve_bracer_metrics,
    resolve_pauldron_metrics,
    resolve_tang_details,
    resolve_fuller_dimensions,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS
from showcase_presets import SHOWCASE_PRESETS, generate_showcase_scad, preset_metrics as showcase_metrics
from ui_params import (
    BRACER_DECORATION_PRESETS,
    DEFAULT_GENERATION_CATEGORY,
    GENERATION_CATEGORIES,
    build_bracer_generation_params,
    build_pauldron_generation_params,
    enabled_bracer_detail_labels,
    enabled_pauldron_detail_labels,
    normalize_generation_category,
)


def preset_metrics(sword_type: str) -> dict[str, float]:
    return {name: spec["default"] for name, spec in SWORD_PRESETS[sword_type].items()}


def bracer_shell_side_width(metrics: dict[str, float]) -> float:
    return (min(metrics["wrist_width_mm"], metrics["forearm_width_mm"]) - metrics["bracer_opening_width_mm"]) / 2


def bracer_passage_outer_bound(metrics: dict[str, float], passage_depth: float) -> float:
    return (
        metrics["bracer_closure_edge_margin_mm"]
        + passage_depth
        + metrics["bracer_exterior_finishing_allowance_mm"] * 2
    )


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


def test_generate_scad_backward_compatible_sword_default():
    scad = generate_scad("longsword", preset_metrics("longsword"), "tapered", "straight", "sphere")
    assert "Digital Forge Version 4: longsword" in scad
    assert "module blade()" in scad
    assert "module bracer()" not in scad


def test_bracer_generation_returns_valid_scad_text():
    assert ARMOR_TYPES == ("Bracer", "Pauldron")
    scad = generate_armor_scad(
        armor_type="Bracer",
        metrics={
            "bracer_length_mm": 190,
            "wrist_width_mm": 72,
            "forearm_width_mm": 108,
            "bracer_depth_mm": 52,
            "bracer_thickness_mm": 4.5,
            "bracer_arc_degrees": 150,
            "bracer_opening_width_mm": 32,
        },
        bracer_style="Plain",
    )
    assert "Digital Forge Armor Version 1: Bracer" in scad
    assert "Decorative/prototype fantasy prop geometry only" in scad
    assert "bracer_length_mm = 190;" in scad
    assert "wrist_width_mm = 72;" in scad and "forearm_width_mm = 108;" in scad
    assert "bracer_depth_mm = 52;" in scad
    assert "bracer_opening_width_mm = 32;" in scad
    assert "function bracer_width_at(y)" in scad
    assert "function bracer_opening_angle_at(y)" in scad
    assert "function bracer_covered_angle_at(y)" in scad
    assert "module bracer_shell()" in scad
    assert "Tapered hollow shell" in scad
    assert "for (i=[0:bracer_shell_steps-1])" in scad
    assert "module bracer_outer_plate()" in scad
    assert "bracer();" in scad


def test_default_bracer_metrics_use_wearer_specific_prototype_values():
    metrics, warnings = resolve_bracer_metrics()
    assert not warnings
    assert DEFAULT_BRACER_METRICS["bracer_length_mm"] == 241.30
    assert DEFAULT_BRACER_METRICS["bracer_depth_mm"] == 69.85
    assert DEFAULT_BRACER_METRICS["wrist_width_mm"] == 76.20
    assert DEFAULT_BRACER_METRICS["forearm_width_mm"] == 114.30
    assert metrics["bracer_length_mm"] == 241.30
    assert metrics["bracer_depth_mm"] == 69.85
    assert metrics["wrist_width_mm"] == 76.20
    assert metrics["forearm_width_mm"] == 114.30


def test_pauldron_generation_returns_valid_scad_text():
    scad = generate_armor_scad(
        armor_type="Pauldron",
        metrics={
            "pauldron_width_mm": 170,
            "pauldron_depth_mm": 125,
            "pauldron_height_mm": 58,
            "plate_count": 4,
            "plate_overlap_mm": 15,
            "pauldron_thickness_mm": 4.5,
        },
        pauldron_style="Knight",
    )
    assert "Digital Forge Armor Version 1: Pauldron" in scad
    assert "Pauldron style: Knight" in scad
    assert "pauldron_width_mm = 170;" in scad
    assert "plate_count = 4;" in scad
    assert "module pauldron_plate(i)" in scad
    assert "module pauldron()" in scad
    assert "pauldron();" in scad
    assert "Layered shoulder lames overlap" in scad


def test_direct_pauldron_generator_matches_armor_route():
    direct = generate_pauldron_scad(pauldron_style="Elven")
    routed = generate_armor_scad(armor_type="Pauldron", pauldron_style="Elven")
    assert direct == routed
    assert "Elven style: slimmer leaf-like crest" in direct


def test_plain_bracer_generates_no_raised_panel_geometry():
    scad = generate_armor_scad(
        bracer_style="Plain",
        detail_options={"raised_panel": False},
    )
    assert "Bracer details: none" in scad
    assert "Plain bracer: no decorative geometry" in scad
    outer_plate = scad.split("module bracer_outer_plate()", 1)[1].split("module bracer_flange_section", 1)[0]
    assert "bracer_raised_design_panel();" not in outer_plate


def test_raised_design_panel_generates_positive_panel_geometry():
    scad = generate_armor_scad(
        bracer_style="Plain",
        detail_options={"raised_panel": True},
    )
    assert "Bracer details: raised_panel" in scad
    assert "module bracer_raised_design_panel()" in scad
    assert "Raised Design Panel: typed exterior field" in scad
    assert "bracer_raised_design_panel();" in scad
    panel_module = scad.split("module bracer_raised_design_panel()", 1)[1].split("module bracer_shell_point", 1)[0]
    assert "polyhedron(" in panel_module
    assert "bracer_panel_shell_point" in panel_module


def test_pauldron_detail_options_control_optional_scad_features():
    scad = generate_armor_scad(
        armor_type="Pauldron",
        pauldron_style="Barbarian",
        detail_options={
            "raised_trim": False,
            "rivets": True,
            "spikes": True,
            "runes": True,
        },
    )
    assert "Pauldron details: rivets, spikes, runes" in scad
    assert "Optional rivets anchored near plate corners" in scad
    assert "Optional blunt fantasy shoulder spikes" in scad
    assert "Optional raised rune-like decorative motif" in scad


def test_removed_bracer_aggregate_styles_fall_back_to_plain():
    assert BRACER_STYLES == ("Plain",)
    assert "Knight" not in BRACER_STYLES
    assert "Barbarian" not in BRACER_STYLES
    assert "Elven" not in BRACER_STYLES
    params, warnings = build_bracer_generation_params(bracer_style="Elven", detail_options={"runes": True})
    scad = generate_armor_scad(**params)
    assert not warnings
    assert params["bracer_style"] == "Plain"
    assert params["detail_options"] == {"raised_panel": False}
    assert "Bracer style: Plain" in scad
    assert "Plain bracer aggregate style" in scad
    assert "bracer_raised_design_panel();" not in scad


def test_bracer_plain_preset_is_clean_hollow_shell():
    scad = generate_armor_scad(
        detail_options={"raised_panel": False}
    )
    assert "Bracer details: none" in scad
    assert "Plain bracer: no decorative geometry" in scad
    assert "module bracer_shell_point" in scad
    assert "bracer_opening_width_mm" in scad
    assert "bracer_outer_plate();" in scad
    assert "bracer_rune" not in scad
    assert "bracer_spike" not in scad
    assert "bracer_trim_band" not in scad


def test_bracer_decoration_presets_are_frozen_to_two_choices():
    assert tuple(BRACER_DECORATION_PRESETS) == (
        "Plain",
        "Raised Design Panel",
    )
    assert BRACER_DECORATION_PRESETS["Plain"] == {"raised_panel": False}
    assert BRACER_DECORATION_PRESETS["Raised Design Panel"] == {"raised_panel": True}
    assert "Runes / Motif" not in BRACER_DECORATION_PRESETS


def test_each_pauldron_style_emits_style_specific_features():
    outputs = {
        style: generate_armor_scad(armor_type="Pauldron", pauldron_style=style)
        for style in PAULDRON_STYLES
    }
    assert "Knight style: clean layered shoulder plates" in outputs["Knight"]
    assert "Barbarian style: heavy center rib" in outputs["Barbarian"]
    assert "Elven style: slimmer leaf-like crest" in outputs["Elven"]
    assert len(set(outputs.values())) == len(PAULDRON_STYLES)


def test_invalid_bracer_dimensions_are_clamped_safely():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_length_mm": -100,
            "wrist_width_mm": 220,
            "forearm_width_mm": 40,
            "bracer_thickness_mm": 0.1,
            "bracer_arc_degrees": 999,
        }
    )
    assert metrics["bracer_length_mm"] == 60
    assert metrics["forearm_width_mm"] == 45
    assert metrics["wrist_width_mm"] < metrics["forearm_width_mm"]
    assert metrics["bracer_thickness_mm"] == 2.4
    assert metrics["bracer_wall_thickness_mm"] == 2.4
    assert metrics["bracer_arc_degrees"] == 260
    assert warnings
    scad = generate_armor_scad(metrics={
        "bracer_length_mm": -100,
        "wrist_width_mm": 220,
        "forearm_width_mm": 40,
        "bracer_thickness_mm": 0.1,
        "bracer_arc_degrees": 999,
    })
    assert "bracer_length_mm = 60;" in scad
    assert "wrist_width_mm = 36.9;" in scad
    assert "bracer_thickness_mm = 2.4;" in scad
    assert "bracer_wall_thickness_mm = 2.4;" in scad
    assert "Warning:" in scad


def test_bracer_new_shell_values_and_unsafe_opening_are_clamped():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_length_mm": 180,
            "wrist_width_mm": 70,
            "forearm_width_mm": 100,
            "bracer_depth_mm": 26,
            "bracer_wall_thickness_mm": 50,
            "bracer_opening_width_mm": 200,
            "bracer_detail_depth_mm": 99,
        }
    )
    assert metrics["bracer_wall_thickness_mm"] < metrics["bracer_depth_mm"] / 2
    layout = bracer_closure_layout_metrics(metrics)
    assert layout["hole_flange_margin_mm"] >= metrics["bracer_lacing_edge_margin_mm"]
    assert metrics["bracer_detail_depth_mm"] <= metrics["bracer_wall_thickness_mm"] * 1.1
    assert metrics["bracer_exterior_finishing_allowance_mm"] <= metrics["bracer_wall_thickness_mm"] * 0.28
    assert any("inner cavity fits" in warning for warning in warnings)
    assert any("opening" in warning for warning in warnings)


def test_default_raised_design_panel_values_generate_valid_scad():
    scad = generate_armor_scad(detail_options={"raised_panel": True})
    assert "Bracer panel type: Wide Panel" in scad
    assert "bracer_panel_length_mm = 132;" in scad
    assert "bracer_panel_width_mm = 56;" in scad
    assert "bracer_panel_height_mm = 4;" in scad
    assert "nan" not in scad.lower()
    assert " = inf;" not in scad.lower()
    assert " = -inf;" not in scad.lower()


def test_raised_design_panel_metrics_are_bounded_to_shell():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_length_mm": 120,
            "wrist_width_mm": 60,
            "forearm_width_mm": 72,
            "bracer_depth_mm": 32,
            "bracer_wall_thickness_mm": 3.2,
            "bracer_opening_width_mm": 44,
            "bracer_panel_length_mm": 999,
            "bracer_panel_width_mm": 999,
            "bracer_panel_height_mm": 99,
            "bracer_panel_edge_roundness_mm": 99,
            "bracer_panel_position_mm": 999,
        }
    )
    assert metrics["bracer_panel_length_mm"] <= metrics["bracer_panel_usable_length_mm"]
    assert metrics["bracer_panel_width_mm"] <= metrics["bracer_panel_safe_front_width_mm"]
    assert metrics["bracer_panel_width_mm"] <= metrics["bracer_panel_max_width_mm"]
    assert metrics["bracer_panel_height_mm"] <= metrics["bracer_panel_max_height_mm"]
    assert metrics["bracer_panel_height_mm"] >= metrics["bracer_panel_min_height_mm"]
    assert metrics["bracer_panel_edge_roundness_mm"] <= min(
        metrics["bracer_panel_length_mm"], metrics["bracer_panel_width_mm"]
    ) * 0.28
    assert metrics["bracer_panel_start_y_mm"] >= 0
    assert metrics["bracer_panel_end_y_mm"] <= metrics["bracer_length_mm"]
    assert any("bracer_panel_length_mm" in warning for warning in warnings)
    assert any("bracer_panel_width_mm" in warning for warning in warnings)
    assert any("bracer_panel_height_mm" in warning for warning in warnings)
    assert any("bracer_panel_edge_roundness_mm" in warning for warning in warnings)
    assert any("bracer_panel_position_mm" in warning for warning in warnings)


def test_raised_panel_uses_shell_derived_outward_projection():
    scad = generate_armor_scad(detail_options={"raised_panel": True})
    panel_module = scad.split("module bracer_raised_design_panel()", 1)[1].split("module bracer_shell_point", 1)[0]
    assert "Shell-derived raised skin" in panel_module
    assert "bracer_panel_shell_point(yi, ai, bracer_panel_height_mm)" in panel_module
    assert "bracer_wall_thickness_mm/2+bracer_exterior_finishing_allowance_mm+raise" in scad
    assert "bracer_surface_z(x, y)" in scad
    assert "for (col=[0:cols])" not in panel_module
    assert "for (row=[0:rows])" not in panel_module
    assert "cube([" not in panel_module


def test_raised_panel_has_bounded_low_complexity_mesh():
    scad = generate_armor_scad(detail_options={"raised_panel": True})
    panel_region = scad.split("function bracer_panel_y_for_index", 1)[1].split("module bracer_shell_point", 1)[0]
    assert f"bracer_panel_angle_segments = {BRACER_PANEL_ANGLE_SEGMENTS};" in scad
    assert f"bracer_panel_length_segments = {BRACER_PANEL_LENGTH_SEGMENTS};" in scad
    assert BRACER_PANEL_ANGLE_SEGMENTS <= 16
    assert BRACER_PANEL_LENGTH_SEGMENTS <= 16
    assert "sample_d" not in panel_region
    assert "bracer_surface_detail(" not in panel_region
    assert "hull()" not in panel_region
    assert "minkowski" not in panel_region.lower()
    assert panel_region.count("polyhedron(") == 1


def test_render_quality_is_bounded_and_preview_lower_than_final():
    preview = generate_armor_scad(detail_options={"raised_panel": True}, render_quality="preview")
    preview_set = generate_armor_scad(detail_options={"raised_panel": True}, render_quality="preview_set")
    final = generate_armor_scad(detail_options={"raised_panel": True}, render_quality="final")
    assert "$fn = 40;" in preview
    assert "$fn = 56;" in preview_set
    assert "$fn = 96;" in final
    assert resolve_render_quality_fn(999) == 96
    assert resolve_render_quality_fn(12) == 24


def test_bracer_panel_type_normalization_and_legacy_calls_are_safe():
    assert BRACER_PANEL_TYPES == ("Wide Panel", "Narrow Panel")
    assert normalize_bracer_panel_type(None) == "Wide Panel"
    assert normalize_bracer_panel_type("Narrow Panel") == "Narrow Panel"
    assert normalize_bracer_panel_type("unsupported") == "Wide Panel"
    legacy, _ = resolve_bracer_metrics({"bracer_panel_width_mm": 36})
    unsupported, warnings = resolve_bracer_metrics(
        {"bracer_panel_type": "unsupported", "bracer_panel_width_mm": 36}
    )
    assert legacy["bracer_panel_type"] == "Wide Panel"
    assert unsupported["bracer_panel_type"] == "Wide Panel"
    assert any("bracer_panel_type" in warning for warning in warnings)


def test_plain_bracer_ignores_panel_type_and_dimensions_for_geometry():
    scad = generate_armor_scad(
        detail_options={"raised_panel": False},
        metrics={
            "bracer_panel_type": "Narrow Panel",
            "bracer_panel_width_mm": 999,
            "bracer_panel_height_mm": 99,
        },
    )
    assert "Bracer details: none" in scad
    assert "Bracer panel type: Narrow Panel" in scad
    assert "bracer_raised_design_panel();" not in scad


def test_wide_and_narrow_panel_width_ranges_are_derived_and_clamped():
    wide, _ = resolve_bracer_metrics({"bracer_panel_type": "Wide Panel"})
    narrow, _ = resolve_bracer_metrics({"bracer_panel_type": "Narrow Panel"})
    previous_default_max = min(
        min(wide["wrist_width_mm"], wide["forearm_width_mm"]) * 0.58,
        min(wide["wrist_width_mm"], wide["forearm_width_mm"])
        - wide["bracer_opening_width_mm"]
        - wide["bracer_wall_thickness_mm"] * 3.0,
    )
    assert wide["bracer_wide_panel_max_width_mm"] > previous_default_max
    assert wide["bracer_panel_width_mm"] > narrow["bracer_panel_width_mm"] * 1.75
    assert wide["bracer_panel_min_width_mm"] > narrow["bracer_panel_max_width_mm"]
    assert wide["bracer_panel_min_width_mm"] <= wide["bracer_panel_width_mm"] <= wide["bracer_panel_max_width_mm"]
    assert narrow["bracer_narrow_panel_min_width_mm"] == 22.0
    assert narrow["bracer_narrow_panel_max_width_mm"] < wide["bracer_wide_panel_min_width_mm"]
    stale, warnings = resolve_bracer_metrics(
        {"bracer_panel_type": "Narrow Panel", "bracer_panel_width_mm": wide["bracer_wide_panel_max_width_mm"]}
    )
    assert stale["bracer_panel_width_mm"] == stale["bracer_panel_max_width_mm"]
    assert any("bracer_panel_width_mm" in warning for warning in warnings)


def test_wide_and_narrow_panels_remain_inside_safe_exterior_region():
    for panel_type in BRACER_PANEL_TYPES:
        metrics, _ = resolve_bracer_metrics(
            {"bracer_panel_type": panel_type, "bracer_panel_width_mm": 999}
        )
        assert metrics["bracer_panel_width_mm"] <= metrics["bracer_panel_safe_front_width_mm"]
        assert metrics["bracer_panel_width_mm"] <= metrics["bracer_panel_max_width_mm"]
        assert metrics["bracer_panel_start_y_mm"] >= 0
        assert metrics["bracer_panel_end_y_mm"] <= metrics["bracer_length_mm"]


def test_panel_height_range_expands_above_previous_bounds_and_clamps_excess():
    metrics, _ = resolve_bracer_metrics()
    narrow, _ = resolve_bracer_metrics({"bracer_panel_type": "Narrow Panel"})
    old_min_height = 0.5
    old_max_height = max(
        0.8,
        min(
            metrics["bracer_wall_thickness_mm"] * 0.72,
            metrics["bracer_depth_mm"] * 0.08,
            4.0,
        ),
    )
    assert metrics["bracer_panel_min_height_mm"] > old_min_height
    assert metrics["bracer_panel_max_height_mm"] > old_max_height
    assert metrics["bracer_panel_height_mm"] > 2.4
    assert narrow["bracer_panel_height_mm"] > old_min_height
    assert narrow["bracer_panel_height_mm"] < metrics["bracer_panel_height_mm"]
    assert metrics["bracer_panel_min_height_mm"] <= metrics["bracer_panel_height_mm"] <= metrics["bracer_panel_max_height_mm"]
    excessive, warnings = resolve_bracer_metrics({"bracer_panel_height_mm": 99})
    assert excessive["bracer_panel_height_mm"] == excessive["bracer_panel_max_height_mm"]
    assert any("bracer_panel_height_mm" in warning for warning in warnings)


def test_plain_bracer_has_no_panel_specific_audit_messages():
    audit = audit_bracer_geometry(
        {
            "bracer_panel_height_mm": 99,
            "bracer_panel_width_mm": 99,
            "bracer_panel_position_mm": 99,
        },
        detail_options={"raised_panel": False},
    )
    combined = " ".join(audit["warnings"] + audit["info"] + audit["passes"])
    assert "Raised Design Panel" not in combined


def test_raised_design_panel_audit_reports_height_and_opening_risks():
    audit = audit_bracer_geometry(
        {
            "bracer_length_mm": 120,
            "bracer_panel_length_mm": 96,
            "bracer_panel_height_mm": 0.55,
            "bracer_panel_position_mm": -40,
        },
        detail_options={"raised_panel": True},
    )
    combined = " ".join(audit["warnings"])
    assert "height is low" in combined or "height was clamped" in combined
    assert "wrist opening" in combined or "position was clamped" in combined


def test_raised_design_panel_audit_reports_closure_proximity():
    audit = audit_bracer_geometry(
        {
            "wrist_width_mm": 70,
            "forearm_width_mm": 92,
            "bracer_opening_width_mm": 44,
            "bracer_panel_width_mm": 60,
        },
        detail_options={"raised_panel": True},
        bracer_binding_style="Buckle-Ready Slots",
    )
    assert any("selected closure" in warning for warning in audit["warnings"])


def test_legacy_removed_bracer_detail_names_normalize_to_plain():
    scad = generate_armor_scad(
        detail_options={
            "raised_trim": True,
            "rivets": True,
            "center_ridge": True,
            "spikes": True,
            "runes": True,
        }
    )
    assert "Bracer details: none" in scad
    assert "bracer_raised_design_panel();" not in scad
    assert "bracer_rune" not in scad


def test_lacing_holes_are_complete_and_clear_of_opening_bounds():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_length_mm": 180,
            "wrist_width_mm": 70,
            "forearm_width_mm": 100,
            "bracer_wall_thickness_mm": 4,
            "bracer_opening_width_mm": 54,
            "bracer_exterior_finishing_allowance_mm": 1.5,
        }
    )
    layout = bracer_closure_layout_metrics(metrics)
    hole_depth = metrics["bracer_binding_hole_diameter_mm"]
    assert layout["hole_flange_margin_mm"] >= metrics["bracer_lacing_edge_margin_mm"]
    assert metrics["bracer_lacing_edge_margin_mm"] >= max(3.2, hole_depth * 0.55)
    assert any("opening_width" in warning or "closure" in warning for warning in warnings)
    scad = generate_armor_scad(metrics=metrics, bracer_binding_style="Lacing Holes")
    assert "module bracer_closure_flange(side)" in scad
    assert "rotate([0, bracer_opening_edge_angle(side, y), 0])" in scad
    assert "bracer_lacing_hole_cutter_diameter()" in scad
    assert "Cutter axis: radial XZ flange-face normal" in scad


def test_lacing_loop_geometry_has_outer_body_and_subtractive_passage():
    metrics, _ = resolve_bracer_metrics({"bracer_wall_thickness_mm": 4})
    scad = generate_armor_scad(metrics=metrics, bracer_binding_style="Lacing Loops")
    layout = bracer_closure_layout_metrics(metrics)
    loop_module = scad.split("module bracer_lacing_loop", 1)[1].split("module bracer_buckle_receiver_ear", 1)[0]
    assert "difference()" in loop_module
    assert "bracer_external_feature_center_x(side, y, bracer_loop_height_mm)" in loop_module
    assert "cylinder(h=bracer_loop_passage_diameter_mm + bracer_loop_wall_thickness_mm*4" in loop_module
    assert layout["loop_outside_cavity"]
    assert layout["loop_has_passage"]
    assert metrics["bracer_loop_passage_diameter_mm"] >= 3.2
    assert metrics["bracer_loop_height_mm"] <= metrics["bracer_closure_flange_thickness_mm"] * 1.1
    assert metrics["bracer_loop_length_mm"] <= metrics["bracer_closure_usable_length_mm"] / metrics["bracer_binding_count"] * 0.42


def test_strap_slots_are_complete_rounded_passages_clear_of_opening_bounds():
    metrics, warnings = resolve_bracer_metrics(
        {
            "wrist_width_mm": 64,
            "forearm_width_mm": 88,
            "bracer_wall_thickness_mm": 5,
            "bracer_opening_width_mm": 58,
        }
    )
    layout = bracer_closure_layout_metrics(metrics)
    assert layout["strap_slot_flange_margin_mm"] >= metrics["bracer_strap_slot_edge_margin_mm"]
    assert layout["strap_slot_inset_mm"] >= 2.8
    assert layout["slot_cutter_depth_mm"] > metrics["bracer_closure_flange_thickness_mm"] + metrics["bracer_closure_slot_inset_mm"] * 2
    assert layout["slot_cutter_overtravels_inset_and_frame"]
    assert metrics["bracer_strap_slot_width_mm"] > metrics["bracer_strap_width_nominal_mm"]
    assert warnings
    scad = generate_armor_scad(metrics=metrics, bracer_binding_style="Strap Slots")
    assert "module bracer_rounded_slot_cutter" in scad
    assert "Slot cutter axis: radial XZ flange normal" in scad
    strap_module = scad.split("module bracer_strap_slot", 1)[1].split("module bracer_lacing_loop", 1)[0]
    assert "bracer_slot_center_x(side, y)" in strap_module
    assert "bracer_slot_cutter_depth()" in strap_module
    assert "bracer_closure_cutter_depth()" not in strap_module


def test_buckle_receiver_has_exterior_ears_gap_and_pin_passage():
    metrics, _ = resolve_bracer_metrics({"bracer_wall_thickness_mm": 4.5})
    scad = generate_armor_scad(metrics=metrics, bracer_binding_style="Buckle-Ready Slots")
    layout = bracer_closure_layout_metrics(metrics)
    assert metrics["bracer_buckle_slot_width_mm"] > metrics["bracer_strap_slot_width_mm"]
    assert metrics["bracer_buckle_slot_length_mm"] > metrics["bracer_strap_slot_length_mm"]
    assert layout["buckle_slot_flange_margin_mm"] >= metrics["bracer_buckle_slot_edge_margin_mm"]
    assert len(layout["hardware_positions_y"]) == 3
    assert layout["hardware_positions_y"] == sorted(layout["hardware_positions_y"])
    assert layout["hardware_positions_y"][0] >= metrics["bracer_closure_wrist_margin_mm"]
    assert layout["hardware_positions_y"][-1] <= metrics["bracer_length_mm"] - metrics["bracer_closure_elbow_margin_mm"]
    assert layout["slot_cutter_depth_mm"] > (
        metrics["bracer_closure_flange_thickness_mm"]
        + metrics["bracer_wall_thickness_mm"] * 0.55
        + metrics["bracer_closure_slot_inset_mm"] * 2
    )
    assert layout["buckle_receiver_has_two_ears"]
    assert layout["buckle_receiver_has_central_gap"]
    assert layout["buckle_pin_cutter_overtravels_ears"] > metrics["bracer_buckle_receiver_total_length_mm"]
    assert "bracer_buckle_receiver_ear(side, y, ear_side)" in scad
    assert "for (ear_side=[-1, 1])" in scad
    assert "bracer_buckle_receiver_gap_mm/2 + bracer_buckle_receiver_ear_thickness_mm/2" in scad
    assert "bracer_buckle_receiver(1, bracer_hardware_slot_y(i));" in scad
    assert "bracer_strap_slot(-1, bracer_hardware_slot_y(i));" in scad
    assert "bracer_buckle_receiver_slot(1, bracer_hardware_slot_y(i));" in scad
    assert "bracer_buckle_pin_cutter(1, bracer_hardware_slot_y(i));" in scad
    assert "bracer_buckle_receiver_gap_mm\n                    + bracer_buckle_receiver_ear_thickness_mm*2 + 4" in scad
    bracer_module = scad.split("module bracer() ", 1)[1]
    union_before_cutters = bracer_module.split("bracer_binding_cutters();", 1)[0]
    assert "bracer_binding_positive();" in union_before_cutters
    assert "bracer_binding_cutters();" in bracer_module
    assert "bracer_reinforced_slot_frame" not in scad
    assert "bracer_strap_anchor_frame" not in scad
    assert "bracer_buckle_access_frame" not in scad
    assert "bracer_strap_anchor_slot" not in scad
    assert "bracer_buckle_access_slot" not in scad


def test_buckle_receiver_orientation_is_exterior_across_default_taper():
    for metric_overrides in (
        {},
        {"wrist_width_mm": 62, "forearm_width_mm": 96, "bracer_opening_width_mm": 42},
        {"wrist_width_mm": 90, "forearm_width_mm": 138, "bracer_opening_width_mm": 54},
    ):
        metrics, _ = resolve_bracer_metrics(metric_overrides)
        layout = bracer_closure_layout_metrics(metrics)
        assert layout["buckle_receiver_outward_axis"] == "bracer_outward_normal_xz"
        assert layout["buckle_receiver_min_offset_from_edge_mm"] > 0
        assert layout["buckle_receiver_min_offset_from_edge_mm"] > layout["inner_opening_boundary_offset_mm"]
        assert layout["buckle_receiver_center_offset_from_edge_mm"] > layout["buckle_slot_cutter_center_offset_from_edge_mm"]

    scad = generate_armor_scad(bracer_binding_style="Buckle-Ready Slots")
    receiver_module = scad.split("module bracer_buckle_receiver_ear", 1)[1].split("module bracer_buckle_receiver(side, y)", 1)[0]
    assert "bracer_buckle_receiver_center_x(side, y)" in receiver_module
    assert "bracer_buckle_receiver_center_z(side, y)" in receiver_module
    assert "bracer_slot_center_x(side, y)" not in receiver_module
    assert "bracer_slot_center_z(side, y)" not in receiver_module
    assert "bracer_flange_center_x(side, y)\n        + bracer_outward_normal_x(side, y)" in scad


def test_buckle_receiver_pin_and_ear_dimensions_are_clamped_safely():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_buckle_receiver_gap_mm": 1,
            "bracer_buckle_receiver_projection_mm": 20,
            "bracer_buckle_receiver_ear_thickness_mm": 1,
            "bracer_buckle_pin_diameter_mm": 10,
        }
    )
    assert metrics["bracer_buckle_receiver_gap_mm"] >= 8.0
    assert metrics["bracer_buckle_receiver_projection_mm"] <= 8.0
    assert metrics["bracer_buckle_receiver_ear_thickness_mm"] >= max(3.0, metrics["bracer_buckle_pin_diameter_mm"] * 0.9)
    assert metrics["bracer_buckle_pin_diameter_mm"] <= 4.0
    assert metrics["bracer_buckle_receiver_projection_mm"] - metrics["bracer_buckle_pin_diameter_mm"] >= (
        metrics["bracer_buckle_pin_wall_margin_mm"] * 2
    )
    assert any("bracer_buckle_receiver_gap_mm" in warning for warning in warnings)
    assert any("bracer_buckle_receiver_projection_mm" in warning for warning in warnings)
    assert any("bracer_buckle_receiver_ear_thickness_mm" in warning for warning in warnings)
    assert any("bracer_buckle_pin_diameter_mm" in warning for warning in warnings)


def test_buckle_receiver_complexity_stays_bounded():
    scad = generate_armor_scad(bracer_binding_style="Buckle-Ready Slots")
    receiver_section = scad.split("module bracer_buckle_receiver_ear", 1)[1].split("module bracer_binding_positive", 1)[0]
    assert "minkowski" not in receiver_section.lower()
    assert "polyhedron" not in receiver_section.lower()
    assert "hull()" not in receiver_section
    assert receiver_section.count("cube(") == 1
    assert receiver_section.count("cylinder(") == 1
    assert "[0:bracer_binding_count-1]" not in receiver_section


def test_small_bracer_dimensions_compress_hardware_slot_group_or_warn():
    metrics, warnings = resolve_bracer_metrics(
        {
            "bracer_length_mm": 60,
            "wrist_width_mm": 48,
            "forearm_width_mm": 58,
            "bracer_opening_width_mm": 42,
            "bracer_wall_thickness_mm": 4,
        }
    )
    layout = bracer_closure_layout_metrics(metrics)
    assert layout["slot_group_compressed"]
    assert layout["hardware_positions_y"][0] >= metrics["bracer_closure_wrist_margin_mm"]
    assert layout["hardware_positions_y"][-1] <= metrics["bracer_length_mm"] - metrics["bracer_closure_elbow_margin_mm"]
    assert any("hardware_slot_spacing" in warning for warning in warnings)


def test_panel_types_coexist_with_approved_closure_styles():
    for panel_type in BRACER_PANEL_TYPES:
        for closure in BRACER_BINDING_STYLES:
            scad = generate_armor_scad(
                detail_options={"raised_panel": True},
                metrics={"bracer_panel_type": panel_type},
                bracer_binding_style=closure,
            )
            assert "bracer();" in scad
            assert "nan" not in scad.lower()
            assert "undefined" not in scad.lower()
            if closure == "Strap Slots":
                assert "bracer_strap_slot(side, bracer_hardware_slot_y(i));" in scad
            if closure == "Buckle-Ready Slots":
                assert "bracer_buckle_receiver_slot(1, bracer_hardware_slot_y(i));" in scad


def test_finishing_allowance_adds_exterior_stock_without_shrinking_passages_or_fit():
    base, _ = resolve_bracer_metrics(
        {
            "wrist_width_mm": 72,
            "forearm_width_mm": 104,
            "bracer_wall_thickness_mm": 4.5,
            "bracer_exterior_finishing_allowance_mm": 0,
        }
    )
    finished, warnings = resolve_bracer_metrics(
        {
            "wrist_width_mm": 72,
            "forearm_width_mm": 104,
            "bracer_wall_thickness_mm": 4.5,
            "bracer_exterior_finishing_allowance_mm": 1.5,
        }
    )
    assert finished["wrist_width_mm"] == base["wrist_width_mm"]
    assert finished["forearm_width_mm"] == base["forearm_width_mm"]
    assert finished["bracer_wall_thickness_mm"] == base["bracer_wall_thickness_mm"]
    assert finished["bracer_binding_hole_diameter_mm"] == base["bracer_binding_hole_diameter_mm"]
    assert finished["bracer_strap_slot_width_mm"] == base["bracer_strap_slot_width_mm"]
    assert finished["bracer_exterior_finishing_allowance_mm"] <= finished["bracer_wall_thickness_mm"] * 0.28
    assert any("finishing_allowance" in warning for warning in warnings)
    scad = generate_armor_scad(metrics=finished, bracer_binding_style="Lacing Holes")
    assert "bracer_shell_point_diameter() = bracer_wall_thickness_mm + 2*bracer_exterior_finishing_allowance_mm" in scad
    assert "bracer_lacing_hole_cutter_diameter() =" in scad


def test_bracer_binding_styles_emit_expected_positive_and_subtractive_geometry():
    assert BRACER_BINDING_STYLES == ("None", "Lacing Holes", "Lacing Loops", "Strap Slots", "Buckle-Ready Slots")
    none = generate_armor_scad(bracer_binding_style="None")
    holes = generate_armor_scad(bracer_binding_style="Lacing Holes")
    loops = generate_armor_scad(bracer_binding_style="Lacing Loops")
    slots = generate_armor_scad(bracer_binding_style="Strap Slots")
    buckle = generate_armor_scad(bracer_binding_style="Buckle-Ready Slots")
    legacy_buckle = generate_armor_scad(bracer_binding_style="Buckle Tabs")
    assert "No positive bracer binding hardware selected" in none
    assert "Lacing holes: paired subtractive round holes" in holes
    assert "bracer_lacing_hole(side, bracer_binding_y(i));" in holes
    assert "difference()" in holes
    assert "Compact external lacing loops" in loops
    assert "bracer_lacing_loop(side, bracer_binding_y(i));" in loops
    assert "Strap slots: paired subtractive rectangular slots" in slots
    assert "bracer_strap_slot(side, bracer_hardware_slot_y(i));" in slots
    assert "Exterior buckle receiver" in buckle
    assert "bracer_buckle_receiver(1, bracer_hardware_slot_y(i));" in buckle
    assert "bracer_strap_slot(-1, bracer_hardware_slot_y(i));" in buckle
    assert "bracer_buckle_receiver_slot(1, bracer_hardware_slot_y(i));" in buckle
    assert "bracer_buckle_pin_cutter(1, bracer_hardware_slot_y(i));" in buckle
    assert "Bracer binding: Buckle-Ready Slots" in legacy_buckle


def test_every_bracer_binding_style_generates_with_plain_and_raised_panel():
    for style in BRACER_BINDING_STYLES:
        plain = generate_armor_scad(bracer_binding_style=style, detail_options={"raised_panel": False})
        raised = generate_armor_scad(bracer_binding_style=style, detail_options={"raised_panel": True})
        assert f"Bracer binding: {style}" in plain
        assert f"Bracer binding: {style}" in raised
        assert "bracer();" in plain
        assert "bracer();" in raised
        assert "bracer_raised_design_panel();" not in plain
        assert "bracer_raised_design_panel();" in raised


def test_bracer_export_scad_stays_functional_for_armor_visibility_flow():
    scad = generate_armor_scad(
        armor_type="Bracer",
        detail_options={"raised_panel": True},
        bracer_binding_style="Strap Slots",
        debug_geometry=True,
    )
    assert "Digital Forge Armor Version 1: Bracer" in scad
    assert "bracer();" in scad
    assert "bracer_closure_debug_geometry();" in scad
    assert "EMPTY ASSEMBLY" not in scad


def test_bracer_closure_spacing_spans_usable_length_uniformly():
    layout = bracer_closure_layout_metrics({"bracer_length_mm": 180, "bracer_wall_thickness_mm": 4})
    metrics = layout["metrics"]
    positions = layout["positions_y"]
    spacings = [b - a for a, b in zip(positions, positions[1:])]
    assert positions[0] >= metrics["bracer_closure_wrist_margin_mm"]
    assert positions[-1] <= metrics["bracer_length_mm"] - metrics["bracer_closure_elbow_margin_mm"]
    assert abs(sum(positions) / len(positions) - layout["usable_midpoint_y"]) < 0.001
    assert max(spacings) - min(spacings) < 0.001
    coverage = (positions[-1] - positions[0]) / metrics["bracer_length_mm"]
    assert 0.65 <= coverage <= 0.75


def test_bracer_closure_uses_explicit_flange_system_for_all_active_styles():
    for style in ("Lacing Holes", "Lacing Loops", "Strap Slots", "Buckle-Ready Slots"):
        scad = generate_armor_scad(bracer_binding_style=style)
        assert "module bracer_closure_flanges()" in scad
        assert "bracer_closure_flanges();" in scad
        assert "function bracer_flange_center_x(side, y)" in scad
        assert "function bracer_outward_normal_x(side, y)" in scad
        assert "bracer_closure_center_x(side, y, passage_depth) = bracer_flange_center_x(side, y);" in scad


def test_bracer_closure_cutter_orientation_regression_not_shell_tangent():
    layout = bracer_closure_layout_metrics()
    scad = generate_armor_scad(bracer_binding_style="Lacing Holes")
    hole_module = scad.split("module bracer_lacing_hole", 1)[1].split("module bracer_rounded_slot_cutter", 1)[0]
    assert layout["cutter_axis"] == "radial_flange_normal_xz"
    assert layout["legacy_shell_tangent_axis"] == "z"
    assert "rotate([0, bracer_opening_edge_angle(side, y), 0])" in hole_module
    assert "bracer_closure_cutter_depth()" in hole_module
    assert "cylinder(h=bracer_wall_thickness_mm*7" not in hole_module


def test_default_lacing_hole_has_complete_flange_margin_and_crossing_cutter():
    layout = bracer_closure_layout_metrics()
    metrics = layout["metrics"]
    assert layout["hole_flange_margin_mm"] >= metrics["bracer_lacing_edge_margin_mm"]
    assert layout["cutter_crosses_flange_thickness"] > metrics["bracer_closure_flange_thickness_mm"]
    assert metrics["bracer_closure_flange_outward_offset_mm"] > metrics["bracer_closure_flange_thickness_mm"] / 2


def test_bracer_debug_geometry_exposes_flanges_cutters_and_normals():
    scad = generate_armor_scad(bracer_binding_style="Strap Slots", debug_geometry=True)
    assert "bracer_closure_debug_geometry();" in scad
    assert "%bracer_closure_flanges();" in scad
    assert "#bracer_binding_cutters();" in scad
    assert "bracer_outward_normal_x(side, y)*bracer_closure_flange_thickness_mm" in scad


def test_invalid_pauldron_dimensions_are_clamped_safely():
    metrics, warnings = resolve_pauldron_metrics(
        {
            "pauldron_width_mm": -10,
            "pauldron_depth_mm": 999,
            "pauldron_height_mm": 2,
            "plate_count": 99,
            "plate_overlap_mm": 1,
            "pauldron_thickness_mm": 0.1,
        }
    )
    assert metrics["pauldron_width_mm"] == 70
    assert metrics["pauldron_depth_mm"] == 260
    assert metrics["pauldron_height_mm"] == 18
    assert metrics["plate_count"] == 8
    assert metrics["pauldron_thickness_mm"] == 2.4
    assert metrics["plate_overlap_mm"] >= 4
    assert warnings
    scad = generate_armor_scad(armor_type="Pauldron", metrics={
        "pauldron_width_mm": -10,
        "pauldron_depth_mm": 999,
        "pauldron_height_mm": 2,
        "plate_count": 99,
        "plate_overlap_mm": 1,
        "pauldron_thickness_mm": 0.1,
    })
    assert "pauldron_width_mm = 70;" in scad
    assert "plate_count = 8;" in scad
    assert "Warning:" in scad


def test_ui_generation_category_defaults_to_sword():
    assert GENERATION_CATEGORIES == ("Sword", "Scabbard", "Armor", "Futurewear")
    assert DEFAULT_GENERATION_CATEGORY == "Sword"
    assert normalize_generation_category(None) == "Sword"
    assert normalize_generation_category("unknown") == "Sword"
    assert normalize_generation_category("scabbard") == "Scabbard"
    assert normalize_generation_category("armor") == "Armor"
    assert normalize_generation_category("futurewear") == "Futurewear"


def test_ui_armor_params_build_valid_bracer_kwargs():
    params, warnings = build_bracer_generation_params(
        armor_type="Bracer",
        bracer_style="Elven",
        metrics={
            "bracer_length_mm": 210,
            "wrist_width_mm": 74,
            "forearm_width_mm": 112,
            "bracer_thickness_mm": 5,
            "bracer_arc_degrees": 155,
        },
        detail_options={
            "raised_panel": True,
        },
        bracer_binding_style="Lacing Loops",
    )
    assert not warnings
    assert params["armor_type"] == "Bracer"
    assert params["bracer_style"] == "Plain"
    assert params["metrics"]["bracer_length_mm"] == 210
    assert params["detail_options"] == {"raised_panel": True}
    assert params["bracer_binding_style"] == "Lacing Loops"
    assert enabled_bracer_detail_labels(params["detail_options"]) == ["Raised Design Panel"]
    scad = generate_armor_scad(**params)
    assert "Digital Forge Armor Version 1: Bracer" in scad
    assert "Bracer style: Plain" in scad
    assert "bracer_raised_design_panel();" in scad


def test_ui_armor_params_build_valid_pauldron_kwargs():
    params, warnings = build_pauldron_generation_params(
        armor_type="Pauldron",
        pauldron_style="Barbarian",
        metrics={
            "pauldron_width_mm": 180,
            "pauldron_depth_mm": 128,
            "pauldron_height_mm": 62,
            "plate_count": 5,
            "plate_overlap_mm": 16,
            "pauldron_thickness_mm": 5,
        },
        detail_options={
            "raised_trim": True,
            "rivets": True,
            "spikes": True,
            "runes": False,
        },
    )
    assert not warnings
    assert params["armor_type"] == "Pauldron"
    assert params["pauldron_style"] == "Barbarian"
    assert params["metrics"]["plate_count"] == 5
    assert enabled_pauldron_detail_labels(params["detail_options"]) == ["Raised trim", "Rivets", "Spikes"]
    scad = generate_armor_scad(**params)
    assert "Digital Forge Armor Version 1: Pauldron" in scad
    assert "Pauldron style: Barbarian" in scad


def test_valid_bracer_audit_has_no_warnings():
    audit = audit_bracer_geometry(
        {
            "bracer_length_mm": 185,
            "wrist_width_mm": 72,
            "forearm_width_mm": 104,
            "bracer_thickness_mm": 4.2,
            "bracer_arc_degrees": 145,
        },
        bracer_style="Plain",
        detail_options={"raised_panel": False},
    )
    assert not audit["warnings"]
    combined = " ".join(audit["passes"])
    assert "tapers outward" in combined
    assert "Inner cavity remains" in combined
    assert "Plain bracer style" in combined


def test_thin_bracer_audit_warns():
    audit = audit_bracer_geometry(
        {
            "bracer_length_mm": 180,
            "wrist_width_mm": 70,
            "forearm_width_mm": 100,
            "bracer_thickness_mm": 2.4,
            "bracer_arc_degrees": 145,
        }
    )
    assert any("thickness" in warning and "fragile" in warning for warning in audit["warnings"])


def test_extreme_bracer_curvature_warns_or_clamps():
    audit = audit_bracer_geometry(
        {
            "bracer_length_mm": 180,
            "wrist_width_mm": 70,
            "forearm_width_mm": 100,
            "bracer_thickness_mm": 4,
            "bracer_arc_degrees": 220,
        }
    )
    assert any("curvature is high" in warning for warning in audit["warnings"])


def test_invalid_bracer_taper_audit_warns_and_generation_corrects():
    metrics = {
        "bracer_length_mm": 180,
        "wrist_width_mm": 120,
        "forearm_width_mm": 90,
        "bracer_thickness_mm": 4,
        "bracer_arc_degrees": 145,
    }
    audit = audit_bracer_geometry(metrics)
    resolved, warnings = resolve_bracer_metrics(metrics)
    assert resolved["wrist_width_mm"] < resolved["forearm_width_mm"]
    assert any("Wrist width is larger" in warning for warning in audit["warnings"])
    assert any("tapers outward" in warning for warning in warnings)


def test_bracer_audit_warns_for_extreme_ratio_and_unsupported_legacy_detail():
    audit = audit_bracer_geometry(
        {
            "bracer_length_mm": 420,
            "wrist_width_mm": 45,
            "forearm_width_mm": 70,
            "bracer_thickness_mm": 12,
            "bracer_arc_degrees": 145,
        },
        detail_options={"rivets": True, "spikes": True, "unknown_detail": True},
    )
    combined = " ".join(audit["warnings"])
    assert "length-to-width ratio is extreme" in combined
    assert "Unsupported bracer detail option" in combined


def test_valid_pauldron_audit_has_no_warnings():
    audit = audit_pauldron_geometry(
        {
            "pauldron_width_mm": 165,
            "pauldron_depth_mm": 120,
            "pauldron_height_mm": 55,
            "plate_count": 4,
            "plate_overlap_mm": 14,
            "pauldron_thickness_mm": 4.2,
        },
        detail_options={"raised_trim": True},
    )
    assert not audit["warnings"]
    combined = " ".join(audit["passes"])
    assert "plate overlap visually connects" in combined
    assert "readable shoulder dome" in combined
    assert "Armor type is supported" in combined


def test_pauldron_audit_warns_for_many_plates_and_thin_material():
    audit = audit_pauldron_geometry(
        {
            "pauldron_width_mm": 165,
            "pauldron_depth_mm": 120,
            "pauldron_height_mm": 55,
            "plate_count": 8,
            "plate_overlap_mm": 14,
            "pauldron_thickness_mm": 2.4,
        }
    )
    combined = " ".join(audit["warnings"])
    assert "plate count" in combined
    assert "thickness" in combined and "fragile" in combined


def test_pauldron_audit_warns_for_low_overlap_and_extreme_proportions():
    audit = audit_pauldron_geometry(
        {
            "pauldron_width_mm": 300,
            "pauldron_depth_mm": 70,
            "pauldron_height_mm": 125,
            "plate_count": 4,
            "plate_overlap_mm": 4,
            "pauldron_thickness_mm": 4,
        }
    )
    combined = " ".join(audit["warnings"])
    assert "overlap is low" in combined
    assert "width/depth proportion is extreme" in combined


def test_pauldron_audit_warns_for_oversized_details_and_unknown_options():
    audit = audit_pauldron_geometry(
        {
            "pauldron_width_mm": 80,
            "pauldron_depth_mm": 80,
            "pauldron_height_mm": 22,
            "plate_count": 3,
            "plate_overlap_mm": 8,
            "pauldron_thickness_mm": 12,
        },
        detail_options={"spikes": True, "rivets": True, "unknown": True},
    )
    combined = " ".join(audit["warnings"])
    assert "spikes are oversized" in combined
    assert "rivets are large" in combined
    assert "Unsupported pauldron detail option" in combined


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


def test_fuller_is_a_bounded_subtractive_rounded_depression():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "wheel",
        fuller_enabled=True, fuller_depth_mm=0.9,
    )
    blade = scad.split("module blade()", 1)[1]
    assert "difference()" in blade and "fuller_geometry();" in blade
    assert "Rounded capsule cutters" in scad and "hull()" in scad and "sphere(d=local_d)" in scad
    assert "face*prop_blade_thickness_mm/2" in scad


def test_fuller_dimensions_clamp_inside_prop_blade():
    width, depth = resolve_fuller_dimensions(30, 4, 1000, 1000)
    assert width == 30 * 0.42
    assert depth == 4 * 0.28 < 4 / 2
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "tapered", "straight", "wheel",
        fuller_enabled=True, fuller_width_mm=1000, fuller_depth_mm=1000,
    )
    assert f"fuller_width_mm = {preset_metrics('longsword')['blade_base_width_mm'] * 0.42:g};" in scad
    assert "fuller_depth_mm = " in scad


def test_ridge_remains_positive_and_outside_fuller_difference():
    scad = generate_scad(
        "longsword", preset_metrics("longsword"), "leaf", "straight", "wheel",
        fuller_enabled=True, ridge_enabled=True,
    )
    blade = scad.split("module blade()", 1)[1]
    assert blade.index("fuller_geometry();") < blade.index("ridge_geometry();")
    assert "linear_extrude(height=ridge_height+0.15)" in scad


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
    assert "tang_bottom_y = tang_top_y - tang_length_mm;" in scad
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


def test_custom_tang_dimensions_are_distinct_from_external_grip():
    metrics = preset_metrics("longsword")
    metrics.update(tang_length_mm=180, tang_width_mm=12, tang_thickness_mm=4)
    scad = generate_scad("longsword", metrics, "tapered", "straight", "wheel")
    assert "tang_length_mm = 180;" in scad
    assert "tang_width_mm = 12;" in scad
    assert "tang_thickness_mm = 4;" in scad
    assert "grip_length_mm = 230;" in scad and "grip_width_mm = 29;" in scad


def test_peg_holes_are_optional_and_cut_through_tang():
    metrics = preset_metrics("longsword")
    metrics.update(peg_hole_count=2, peg_hole_diameter_mm=5, peg_hole_spacing_mm=40)
    with_holes = generate_scad("longsword", metrics, "tapered", "straight", "wheel")
    metrics["peg_hole_count"] = 0
    without_holes = generate_scad("longsword", metrics, "tapered", "straight", "wheel")
    assert "peg_hole_count = 2;" in with_holes
    assert "cylinder(h=tang_thickness_mm+2, d=peg_hole_diameter_mm" in with_holes
    assert "peg_hole_count = 0;" in without_holes
    assert "cylinder(h=tang_thickness_mm+2, d=peg_hole_diameter_mm" not in without_holes


def test_peg_holes_and_count_are_clamped_to_prop_safe_tang_bounds():
    metrics = preset_metrics("dagger")
    metrics.update(peg_hole_count=9, peg_hole_diameter_mm=100, peg_hole_spacing_mm=1000)
    scad = generate_scad("dagger", metrics, "tapered", "straight", "sphere")
    assert "peg_hole_count = 3;" in scad
    audit = audit_geometry(metrics, "dagger", "tapered", "straight", "sphere")
    assert any("between 0 and 3" in warning for warning in audit["warnings"])
    assert any("Peg holes fit" in message for message in audit["passes"])


def test_visible_tang_with_hidden_grip_keeps_peg_holes():
    metrics = preset_metrics("longsword")
    metrics["peg_hole_count"] = 2
    scad = generate_scad(
        "longsword", metrics, "tapered", "straight", "wheel",
        visible_components={"grip": False, "tang": True},
    )
    calls = _assembly_calls(scad)
    assert "tang_core();" in calls and "grip();" not in calls
    assert "peg_hole_count = 2;" in scad and "module tang_core()" in scad


def test_single_peg_hole_is_centered_in_usable_tang():
    positions = centered_peg_hole_positions(180, 1, 5, 28)
    assert positions == [(28 + 5 + 180 - 5) / 2]


def test_two_and_three_peg_holes_are_distributed_around_usable_center():
    for count in (2, 3):
        positions = centered_peg_hole_positions(180, count, 5, 28, 36)
        assert len(positions) == count
        assert (positions[0] + positions[-1]) / 2 == (33 + 175) / 2
        assert positions == sorted(positions)
        assert positions[0] > 28


def test_peg_holes_respect_both_tang_margins_after_clamping():
    metrics = preset_metrics("dagger")
    metrics.update(peg_hole_count=3, peg_hole_diameter_mm=100, peg_hole_spacing_mm=1000)
    tang = resolve_tang_details(metrics)
    assert tang["peg_hole_positions_mm"][0] >= tang["peg_hole_usable_start_mm"]
    assert tang["peg_hole_positions_mm"][-1] <= tang["peg_hole_usable_end_mm"]


def test_tang_only_and_blade_tang_views_keep_peg_holes():
    metrics = preset_metrics("longsword")
    metrics["peg_hole_count"] = 2
    for preset in ("Tang only", "Blade + tang only"):
        scad = generate_scad(
            "longsword", metrics, "tapered", "straight", "wheel",
            visible_components=VISIBILITY_PRESETS[preset],
        )
        assert "module tang_core()" in scad
        assert "cylinder(h=tang_thickness_mm+2, d=peg_hole_diameter_mm" in scad


def test_fuller_and_ridge_use_bounded_blade_local_geometry():
    metrics = preset_metrics("longsword")
    start, end = blade_detail_bounds(
        metrics["blade_length_mm"], metrics["ricasso_length_mm"], 0.7, "tapered"
    )
    scad = generate_scad(
        "longsword", metrics, "tapered", "straight", "wheel",
        fuller_enabled=True, fuller_length_ratio=0.7, ridge_enabled=True,
    )
    assert start >= metrics["ricasso_length_mm"] and end < metrics["blade_length_mm"]
    assert f"blade_detail_start_y = {start:g};" in scad
    assert f"blade_detail_end_y = {end:g};" in scad
    assert "intersection()" in scad
    assert "prop_blade_thickness_mm/2-0.15" in scad


def test_blade_details_follow_blade_visibility_and_audit_bounds():
    metrics = preset_metrics("longsword")
    hidden = generate_scad(
        "longsword", metrics, "leaf", "straight", "wheel",
        fuller_enabled=True, ridge_enabled=True,
        visible_components=VISIBILITY_PRESETS["Tang only"],
    )
    assert "module fuller_geometry()" not in hidden
    assert "module ridge_geometry()" not in hidden
    audit = audit_geometry(
        metrics, "longsword", "leaf", "straight", "wheel",
        VISIBILITY_PRESETS["Blade only"], True, 0.85, True,
    )
    combined = " ".join(audit["passes"])
    assert "Fuller stays within" in combined and "Central ridge stays within" in combined


def test_symmetrical_blade_details_default_to_centered_offsets():
    metrics = preset_metrics("longsword")
    for style in ("tapered", "leaf", "needle"):
        scad = generate_scad(
            "longsword", metrics, style, "straight", "wheel",
            fuller_enabled=True, ridge_enabled=True,
        )
        assert "fuller_offset_x = 0;" in scad
        assert "ridge_offset_x = 0;" in scad


def test_asymmetrical_blades_accept_left_and_right_detail_offsets():
    for style in ("falchion", "curved"):
        metrics = preset_metrics("falchion" if style == "falchion" else "longsword")
        left = blade_detail_offset_for_position(
            "Slight left", metrics["blade_base_width_mm"], metrics["blade_length_mm"], style
        )
        right = blade_detail_offset_for_position(
            "Slight right", metrics["blade_base_width_mm"], metrics["blade_length_mm"], style
        )
        scad = generate_scad(
            "longsword", metrics, style, "straight", "wheel",
            fuller_enabled=True, ridge_enabled=True,
            fuller_offset_x=left, ridge_offset_x=right,
        )
        safe_left = clamp_blade_detail_offset(
            metrics["blade_base_width_mm"], left, 12,
            metrics["blade_length_mm"], style,
        )
        safe_right = clamp_blade_detail_offset(
            metrics["blade_base_width_mm"], right,
            metrics["blade_base_width_mm"] * 0.14,
            metrics["blade_length_mm"], style,
        )
        assert f"fuller_offset_x = {safe_left:g};" in scad
        assert f"ridge_offset_x = {safe_right:g};" in scad
        assert "function fuller_path_x(y)" in scad
        assert "translate([fuller_path_x(y), y, face*prop_blade_thickness_mm/2])" in scad
        assert "translate([ridge_offset_x, 0])" in scad


def test_asymmetrical_detail_offsets_scale_and_stay_in_corridor():
    for style in ("falchion", "curved"):
        center, corridor = compute_blade_detail_corridor(50, 600, style)
        left = blade_detail_offset_for_position("Slight left", 50, 600, style)
        right = blade_detail_offset_for_position("Slight right", 50, 600, style)
        assert center - corridor / 2 <= left < center < right <= center + corridor / 2
        assert right - left >= 50 * 0.1
        assert clamp_blade_detail_offset(50, -1000, 8, 600, style) >= center - corridor / 2
        assert clamp_blade_detail_offset(50, 1000, 8, 600, style) <= center + corridor / 2


def test_curved_fuller_is_sampled_along_style_aware_centerline():
    metrics = preset_metrics("longsword")
    scad = generate_scad(
        "longsword", metrics, "curved", "straight", "wheel", fuller_enabled=True
    )
    assert "fuller_samples = 18" in scad
    assert "function fuller_center_x(y) = blade_base_width_mm*0.82*pow" in scad
    assert "function fuller_diameter_at(y)" in scad
    assert "for (sample=[0:fuller_samples-1])" in scad


def test_fuller_length_defaults_and_clamps_to_safe_usable_range():
    metrics = preset_metrics("longsword")
    default_scad = generate_scad("longsword", metrics, "tapered", "straight", "wheel")
    long_scad = generate_scad(
        "longsword", metrics, "curved", "straight", "wheel",
        fuller_enabled=True, fuller_length_ratio=99,
    )
    assert "fuller_length_ratio = 0.65;" in default_scad
    _, expected_end = blade_detail_bounds(
        metrics["blade_length_mm"], metrics["ricasso_length_mm"], 99, "curved"
    )
    assert f"blade_detail_end_y = {expected_end:g};" in long_scad
    assert expected_end < metrics["blade_length_mm"]


def test_openscad_path_config_round_trip_and_invalid_json():
    path = Path("generated/test-digital-forge-config.json")
    try:
        save_openscad_path(r"C:\Program Files\OpenSCAD\openscad.exe", path)
        assert load_config(path)["openscad_path"].endswith("openscad.exe")
        path.write_text("not-json", encoding="utf-8")
        assert load_config(path) == {}
    finally:
        path.unlink(missing_ok=True)


def test_tapered_and_leaf_center_positions_remain_centered():
    for style in ("tapered", "leaf"):
        assert blade_detail_offset_for_position("Center", 50, 600, style) == 0


def test_excessive_blade_detail_offsets_are_clamped_and_audited():
    metrics = preset_metrics("longsword")
    width = metrics["blade_base_width_mm"]
    expected_fuller = clamp_blade_detail_offset(width, 1000, 12)
    expected_ridge = clamp_blade_detail_offset(width, -1000, width * 0.14)
    scad = generate_scad(
        "longsword", metrics, "tapered", "straight", "wheel",
        fuller_enabled=True, ridge_enabled=True,
        fuller_offset_x=1000, ridge_offset_x=-1000,
    )
    assert f"fuller_offset_x = {expected_fuller:g};" in scad
    assert f"ridge_offset_x = {expected_ridge:g};" in scad
    audit = audit_geometry(
        metrics, "longsword", "tapered", "straight", "wheel", None,
        True, 0.65, True, 1000, -1000, 12,
    )
    assert sum("offset exceeds safe blade bounds" in item for item in audit["warnings"]) == 2


def test_detail_offsets_respect_component_visibility():
    metrics = preset_metrics("longsword")
    offset = blade_detail_offset_for_position("Slight right", metrics["blade_base_width_mm"])
    visible = generate_scad(
        "longsword", metrics, "curved", "straight", "wheel",
        fuller_enabled=True, ridge_enabled=True,
        visible_components=VISIBILITY_PRESETS["Blade only"],
        fuller_offset_x=offset, ridge_offset_x=-offset,
    )
    hidden = generate_scad(
        "longsword", metrics, "curved", "straight", "wheel",
        fuller_enabled=True, ridge_enabled=True,
        visible_components=VISIBILITY_PRESETS["Tang only"],
        fuller_offset_x=offset, ridge_offset_x=-offset,
    )
    assert "module fuller_geometry()" in visible and "module ridge_geometry()" in visible
    assert "module fuller_geometry()" not in hidden and "module ridge_geometry()" not in hidden


def test_straight_guard_uses_rounded_capsule_helper():
    scad = generate_scad("longsword", preset_metrics("longsword"), "tapered", "straight", "wheel")
    assert "module rounded_guard_bar" in scad
    assert "hull()" in scad
    assert "rounded_guard_bar(guard_width_mm, guard_height_mm);" in scad


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


def test_openscad_resolver_prefers_windows_cli_companion():
    test_dir = Path("generated/test_openscad_resolver")
    test_dir.mkdir(parents=True, exist_ok=True)
    exe_path = test_dir / "openscad.exe"
    com_path = test_dir / "openscad.com"
    exe_path.write_text("gui", encoding="utf-8")
    com_path.write_text("cli", encoding="utf-8")

    assert resolve_openscad_executable(str(exe_path)) == str(com_path)
    assert resolve_openscad_executable("openscad") == "openscad"


def test_bracer_camera_presets_are_complete_and_deterministic():
    assert tuple(BRACER_CAMERA_PRESETS) == (
        "front_exterior",
        "front_three_quarter",
        "side_profile",
        "closure_side",
        "top_oblique",
        "rear_three_quarter",
    )
    assert all(isinstance(value, str) and value.count(",") == 6 for value in BRACER_CAMERA_PRESETS.values())
    assert BRACER_CAMERA_PRESETS["front_exterior"] == "0,120,42,68,0,0,520"
    assert BRACER_CAMERA_PRESETS["closure_side"] == "70,118,12,92,0,148,260"
    assert BRACER_CAMERA_PRESETS["closure_side"] != "-150,118,38,70,0,92,540"


def test_scabbard_camera_presets_are_complete_and_deterministic():
    assert tuple(SCABBARD_CAMERA_PRESETS) == (
        "three_quarter",
        "side_profile",
        "opening_view",
        "top_profile",
    )
    assert all(isinstance(value, str) and value.count(",") == 6 for value in SCABBARD_CAMERA_PRESETS.values())
    assert SCABBARD_CAMERA_PRESETS["three_quarter"] == "90,360,90,62,0,28,1040"
    assert SCABBARD_CAMERA_PRESETS["opening_view"] == "0,20,38,74,0,0,260"


def test_export_preview_set_builds_named_camera_exports():
    calls = []
    output_dir = Path("generated/test_preview_set_success")
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == DEFAULT_OPENSCAD_TIMEOUT_SECONDS
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_bytes(b"png")
        return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    with patch("preview_service.GENERATED_DIR", output_dir), patch("preview_service.subprocess.run", side_effect=fake_run):
        result = export_preview_set("cube(1);", "openscad")

    assert result.success
    assert set(result.successful_paths) == set(BRACER_CAMERA_PRESETS)
    assert [Path(command[command.index("-o") + 1]).name for command in calls] == [
        f"bracer_{name}.png" for name in BRACER_CAMERA_PRESETS
    ]
    assert all("--camera" in command for command in calls)
    assert [command[command.index("--camera") + 1] for command in calls] == list(BRACER_CAMERA_PRESETS.values())
    assert [Path(command[command.index("-o") + 1]).stem.removeprefix("bracer_") for command in calls] == list(BRACER_CAMERA_PRESETS)


def test_export_preview_set_supports_scabbard_label_and_presets():
    calls = []
    output_dir = Path("generated/test_scabbard_preview_set_success")
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(command, **kwargs):
        calls.append(command)
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_bytes(b"png")
        return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    with patch("preview_service.GENERATED_DIR", output_dir), patch("preview_service.subprocess.run", side_effect=fake_run):
        result = export_preview_set("cube(1);", "openscad", presets=SCABBARD_CAMERA_PRESETS, label="scabbard")

    assert result.success
    assert [Path(command[command.index("-o") + 1]).name for command in calls] == [
        f"scabbard_{name}.png" for name in SCABBARD_CAMERA_PRESETS
    ]
    assert [command[command.index("--camera") + 1] for command in calls] == list(SCABBARD_CAMERA_PRESETS.values())


def test_export_preview_set_preserves_successes_when_one_view_fails():
    output_dir = Path("generated/test_preview_set_partial")
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("-o") + 1])
        if output_path.name == "bracer_side_profile.png":
            return CompletedProcess(args=command, returncode=1, stdout="", stderr="camera failed")
        output_path.write_bytes(b"png")
        return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    with patch("preview_service.GENERATED_DIR", output_dir), patch("preview_service.subprocess.run", side_effect=fake_run):
        result = export_preview_set("cube(1);", "openscad")

    assert not result.success
    assert "side_profile" in result.failures
    assert result.failures["side_profile"].error_code == "command_failed"
    assert len(result.successful_paths) == len(BRACER_CAMERA_PRESETS) - 1
    assert "front_exterior" in result.successful_paths


def test_export_preview_set_subprocess_timeout_is_graceful():
    output_dir = Path("generated/test_preview_set_subprocess_timeout")
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(command, **kwargs):
        output_path = Path(command[command.index("-o") + 1])
        if output_path.name == "bracer_side_profile.png":
            raise TimeoutExpired(command, kwargs["timeout"])
        output_path.write_bytes(b"png")
        return CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    with patch("preview_service.GENERATED_DIR", output_dir), patch("preview_service.subprocess.run", side_effect=fake_run):
        result = export_preview_set("cube(1);", "openscad", timeout=7)

    assert not result.success
    assert len(result.successful_paths) == len(BRACER_CAMERA_PRESETS) - 1
    assert result.failures["side_profile"].error_code == "timeout"
    assert "side_profile" in result.failures["side_profile"].message


def test_export_preview_set_missing_executable_is_graceful():
    with patch("preview_service.subprocess.run", side_effect=FileNotFoundError):
        result = export_preview_set("cube(1);", "missing-openscad")
    assert not result.success
    assert set(result.failures) == set(BRACER_CAMERA_PRESETS)
    assert all(view.error_code == "missing_executable" for view in result.failures.values())


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
