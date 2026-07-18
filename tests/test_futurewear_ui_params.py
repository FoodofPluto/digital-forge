from futurewear import MODULAR_STANDARD_VERSION
from futurewear.connector_coupons import build_dock_ladder_samples, dock_ladder_sample_table
from futurewear.preview_presets import CONNECTOR_CAMERA_PRESETS
from futurewear.ui import FuturewearRenderResult, build_futurewear_connector_result
from ui_params import GENERATION_CATEGORIES, normalize_generation_category


def test_futurewear_generation_category_is_registered_without_changing_default():
    assert GENERATION_CATEGORIES == ("Sword", "Scabbard", "Armor", "Futurewear")
    assert normalize_generation_category(None) == "Sword"
    assert normalize_generation_category("Futurewear") == "Futurewear"


def test_connector_preview_presets_are_complete_and_deterministic():
    assert tuple(CONNECTOR_CAMERA_PRESETS) == (
        "print_layout",
        "exploded_pair_view",
        "insertion_view",
        "assembled_preview",
        "isometric",
        "top",
        "side",
    )
    assert all(value.count(",") == 6 for value in CONNECTOR_CAMERA_PRESETS.values())
    assert CONNECTOR_CAMERA_PRESETS["isometric"] == "-12,71,18,60,0,35,420"
    assert CONNECTOR_CAMERA_PRESETS["top"] == "-12,71,0,0,0,0,520"


def test_futurewear_ui_result_builder_is_testable_without_streamlit_controls():
    result = build_futurewear_connector_result()
    assert isinstance(result, FuturewearRenderResult)
    assert result.can_export
    assert MODULAR_STANDARD_VERSION in result.scad
    assert result.download_name == "DF-MOD-1.0_slide_rail_standard_dock_paired_coupon.scad"
    assert "printer_comp_0" in result.coupon_identifier
    assert result.effective_fit["effective_total_width_difference_mm"] == 0.64
    assert result.preview_presets == CONNECTOR_CAMERA_PRESETS
    assert result.preview_label == "futurewear_connector"
    assert not result.audit["warnings"]


def test_futurewear_ladder_result_exposes_sample_table_and_legend():
    result = build_futurewear_connector_result(coupon_type="Dock Clearance Ladder")
    assert result.download_name == "DF-MOD-1.0_slide_rail_standard_dock_clearance_ladder_c0.32_s0.1_n4.scad"
    assert tuple(row["Sample"] for row in result.dock_ladder_samples) == ("A", "B", "C", "D")
    assert result.dock_ladder_samples[0]["Clearance per side"] == "0.22 mm"
    assert result.dock_ladder_samples[0]["Effective total width gap"] == "0.44 mm"
    assert result.dock_ladder_samples[1]["Expected relative fit"] == "Selected clearance"
    assert ("male Dock piece", "gainsboro / silver") in result.preview_color_legend
    assert "dock_clearance_ladder_print_layout();" in result.scad
    assert "START arrow points" in result.scad


def test_futurewear_ladder_ui_order_matches_coupon_sample_source():
    result = build_futurewear_connector_result(coupon_type="Dock Clearance Ladder")
    samples = build_dock_ladder_samples(0.32)
    table = dock_ladder_sample_table(0.32)
    assert result.dock_ladder_samples == table
    assert tuple(row["Sample"] for row in result.dock_ladder_samples) == tuple(sample.sample_id for sample in samples)
    assert tuple(row["Clearance per side"] for row in result.dock_ladder_samples) == tuple(f"{sample.clearance_mm:.2f} mm" for sample in samples)
