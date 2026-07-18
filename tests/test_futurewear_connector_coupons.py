from futurewear import MODULAR_STANDARD_VERSION
from futurewear.connector_coupons import (
    COUPON_TYPES,
    DockLadderPrintProfile,
    audit_dock_ladder_printability,
    build_dock_ladder_layout,
    build_dock_ladder_samples,
    coupon_identifier,
    dock_ladder_feature_dimensions,
    dock_ladder_print_layout_footprint,
    dock_ladder_sample_table,
    generate_connector_test_coupon_scad,
    generate_cord_opening_ladder_scad,
    generate_dock_clearance_ladder_scad,
    generate_dock_paired_coupon_scad,
    generate_quarter_turn_coupon_scad,
    stable_coupon_filename,
)
from futurewear.connectors import derive_clearance_envelope, derive_male_dimensions, derive_receiver_dimensions
from futurewear.connectors import ConnectorType, normalize_connector_parameters


def test_coupon_types_are_stable():
    assert COUPON_TYPES == (
        "Dock Paired Coupon",
        "Dock Clearance Ladder",
        "Cord Opening Ladder",
        "Quarter Turn Coupon",
        "Null Tile",
    )


def test_stable_coupon_filename_contains_standard_version():
    params, _ = normalize_connector_parameters()
    assert stable_coupon_filename(params, "Dock Paired Coupon") == "DF-MOD-1.0_slide_rail_standard_dock_paired_coupon.scad"
    assert stable_coupon_filename(params, "Dock Clearance Ladder") == "DF-MOD-1.0_slide_rail_standard_dock_clearance_ladder_c0.32_s0.1_n4.scad"
    assert coupon_identifier(params, "Dock Clearance Ladder", "PLA") == (
        "DF-MOD-1.0|slide_rail|standard|pla|dock_clearance_ladder|clearance_0.32|printer_comp_0|step_0.1|samples_4"
    )


def test_dock_paired_coupon_has_grip_tabs_and_pair():
    params, _ = normalize_connector_parameters()
    scad = generate_dock_paired_coupon_scad(params)
    assert MODULAR_STANDARD_VERSION in scad
    assert "module coupon_grip_tab" in scad
    assert "module dock_paired_coupon()" in scad
    assert "dock_positive();" in scad
    assert "dock_receiver_body();" in scad


def test_dock_clearance_ladder_has_four_variants():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    scad = generate_dock_clearance_ladder_scad(params)
    assert scad.count("clearance_variant_") == 4
    assert "clearance_variant_0: 0.22 mm per side" in scad
    assert "clearance_variant_3: 0.52 mm per side" in scad


def test_dock_ladder_samples_are_ordered_unique_and_match_table():
    samples = build_dock_ladder_samples(0.32, printer_compensation_mm=0.05)
    assert tuple(sample.sample_id for sample in samples) == ("A", "B", "C", "D")
    assert len({sample.sample_id for sample in samples}) == len(samples)
    assert tuple(sample.clearance_mm for sample in samples) == (0.22, 0.32, 0.42, 0.52)
    assert tuple(sample.clearance_mm for sample in samples) == tuple(sorted(sample.clearance_mm for sample in samples))
    assert samples[1].effective_total_width_gap_mm == 0.84
    table = dock_ladder_sample_table(0.32, printer_compensation_mm=0.05)
    assert table[0]["Sample"] == "A"
    assert table[0]["Clearance per side"] == "0.22 mm"
    assert table[1]["Effective total width gap"] == "0.84 mm"
    assert table[1]["Expected relative fit"] == "Selected clearance"
    assert table[3]["Printed identifier"] == "D 0.52"


def test_dock_ladder_scad_contains_physical_labels_arrows_stop_and_keying():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    scad = generate_dock_clearance_ladder_scad(params)
    for sample_id, clearance in (("A", "0.22"), ("B", "0.32"), ("C", "0.42"), ("D", "0.52")):
        assert f'"{sample_id}"' in scad
        assert f'"{sample_id} {clearance}"' in scad
        assert f"sample {sample_id}" in scad
    assert "module dock_ladder_text" in scad
    assert "module dock_ladder_arrow_3d" in scad
    assert "dock_ladder_start_plate" in scad
    assert "dock_ladder_stop_plate" in scad
    assert "dock_positive();" in scad
    assert "dock_receiver_body();" in scad
    assert "dock_key_rib" in scad
    assert "color(\"tomato\")" in scad
    assert "Preview color legend:" in scad
    assert "Physical labels are raised" in scad


def test_dock_ladder_preview_modes_are_available_without_separate_stls():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    scad = generate_dock_clearance_ladder_scad(params, preview_mode="Insertion View", selected_sample_id="C")
    assert "module dock_clearance_ladder_print_layout()" in scad
    assert "module dock_clearance_ladder_exploded_pair_view()" in scad
    assert "module dock_clearance_ladder_insertion_view()" in scad
    assert "module dock_clearance_ladder_assembled_preview()" in scad
    assert scad.strip().endswith("dock_clearance_ladder_insertion_view();")
    assert '"C 0.42"' in scad


def test_dock_ladder_layout_bounds_do_not_overlap_and_rest_on_print_plane():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    placements = build_dock_ladder_layout(params)
    assert len(placements) == 8
    assert all(placement.min_z_mm >= 0 for placement in placements)
    assert all(placement.max_z_mm > placement.min_z_mm for placement in placements)
    for left_index, left in enumerate(placements):
        for right in placements[left_index + 1:]:
            separated = (
                left.max_x_mm <= right.min_x_mm
                or right.max_x_mm <= left.min_x_mm
                or left.max_y_mm <= right.min_y_mm
                or right.max_y_mm <= left.min_y_mm
            )
            assert separated, (left, right)
    receiver_rows = [p.center_y_mm for p in placements if p.role == "receiver"]
    assert receiver_rows == sorted(receiver_rows)


def test_dock_ladder_printability_audit_passes_default_fdm_profile():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32, material="PLA")
    audit = audit_dock_ladder_printability(params, DockLadderPrintProfile())
    assert audit.passed, audit.warnings
    assert audit.metrics["receiver_text_size_mm"] >= 3.0
    assert audit.metrics["text_extrusion_height_mm"] >= 0.4
    assert audit.metrics["label_tab_thickness_mm"] >= 0.8
    assert audit.metrics["arrow_shaft_width_mm"] >= 0.8
    assert audit.metrics["arrowhead_width_mm"] >= 1.6
    assert audit.metrics["stop_bar_thickness_mm"] >= 0.8
    assert audit.metrics["receiver_label_edge_margin_x_mm"] >= 0.8
    assert audit.metrics["receiver_label_edge_margin_y_mm"] >= 0.8
    assert audit.metrics["width_mm"] * audit.metrics["depth_mm"] < 9000


def test_dock_ladder_footprint_is_compact_and_deterministic():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    footprint = dock_ladder_print_layout_footprint(params)
    assert footprint == {
        "min_x_mm": -34.32,
        "max_x_mm": 10.92,
        "min_y_mm": -20.71,
        "max_y_mm": 164.02,
        "width_mm": 45.24,
        "depth_mm": 184.73,
    }


def test_dock_ladder_label_tabs_are_outside_mating_geometry_comments():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    scad = generate_dock_clearance_ladder_scad(params)
    assert "dock_male_engagement_mm/2 + stop_thickness_mm + label_plate_len_mm/2" in scad
    assert "-body_len/2 - label_plate_len_mm/2" in scad
    assert "body_len/2 + label_plate_len_mm/2" in scad


def test_dock_ladder_visual_features_remain_outside_functional_bounds():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    features = dock_ladder_feature_dimensions(params)
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    assert features["male_label_tab_length_mm"] > 0
    assert features["receiver_label_tab_length_mm"] > 0
    scad = generate_dock_clearance_ladder_scad(params)
    assert "translate([0, 0, dock_male_depth_mm/2]) dock_positive();" in scad
    assert "translate([0, 0, dock_receiver_depth_mm/2 + minimum_surrounding_wall_mm]) dock_receiver_body();" in scad
    assert "dock_male_engagement_mm/2 + stop_thickness_mm + label_plate_len_mm/2" in scad
    assert "-body_len/2 - label_plate_len_mm/2" in scad
    assert "body_len/2 + label_plate_len_mm/2" in scad
    assert male.width_mm == 16.0
    assert male.depth_mm == 3.0
    assert male.engagement_length_mm == 18.0
    assert receiver.width_mm == 16.64
    assert receiver.depth_mm == 3.32
    assert receiver.engagement_length_mm == 18.32


def test_dock_ladder_mating_dimensions_match_connector_derivation():
    base_params, _ = normalize_connector_parameters(fit_clearance_mm=0.32, printer_compensation_mm=0.05)
    for sample in build_dock_ladder_samples(base_params.fit_clearance_mm, printer_compensation_mm=base_params.printer_compensation_mm):
        params, _ = normalize_connector_parameters(fit_clearance_mm=sample.clearance_mm, printer_compensation_mm=0.05)
        male = derive_male_dimensions(params)
        receiver = derive_receiver_dimensions(params)
        envelope = derive_clearance_envelope(params)
        assert male.width_mm == 15.9
        assert male.depth_mm == 2.95
        assert male.engagement_length_mm == 17.95
        assert receiver.width_mm == round(16 + sample.clearance_mm * 2 + 0.1, 6)
        assert receiver.depth_mm == round(3 + sample.clearance_mm + 0.05, 6)
        assert receiver.engagement_length_mm == round(18 + sample.clearance_mm + 0.05, 6)
        assert envelope["clearance_per_side_mm"] == sample.clearance_mm
        assert envelope["total_width_clearance_mm"] == sample.effective_total_width_gap_mm


def test_dock_ladder_arrow_and_stop_match_insertion_axis():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32)
    scad = generate_dock_clearance_ladder_scad(params, preview_mode="Insertion View")
    assert "dock_ladder_arrow_3d(label_plate_len_mm*0.9" in scad
    assert "translate([0, -body_len/2 - label_plate_len_mm/2" in scad
    assert "translate([0, body_len/2 + label_plate_len_mm/2" in scad
    assert "START arrow points toward the receiver positive stop" in scad


def test_cord_opening_ladder_has_three_reinforced_openings():
    params, _ = normalize_connector_parameters(connector_type=ConnectorType.CORD_LOOP)
    scad = generate_cord_opening_ladder_scad(params)
    assert scad.count("cord_opening_variant_") == 3
    assert "cord_opening_ladder();" in scad


def test_quarter_turn_coupon_is_experimental_and_simple():
    params, _ = normalize_connector_parameters(connector_type=ConnectorType.TWIST_LOCK)
    scad = generate_quarter_turn_coupon_scad(params)
    assert "Experimental Quarter Turn paired coupon" in scad
    assert "quarter_turn_positive();" in scad
    assert "quarter_turn_receiver();" in scad


def test_coupon_dispatch_returns_scad_warnings_and_filename():
    scad, warnings, filename = generate_connector_test_coupon_scad(coupon_type="Null Tile")
    assert not warnings
    assert "null_tile();" in scad
    assert filename.endswith("_null_tile.scad")

    scad, _warnings, filename = generate_connector_test_coupon_scad(coupon_type="Cord Opening Ladder")
    assert "cord_opening_ladder();" in scad
    assert "_cord_loop_" in filename

    scad, _warnings, filename = generate_connector_test_coupon_scad(coupon_type="Quarter Turn Coupon")
    assert "quarter_turn_coupon();" in scad
    assert "_twist_lock_" in filename
