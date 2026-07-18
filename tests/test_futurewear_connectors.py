import math

import pytest

from futurewear import MODULAR_STANDARD_VERSION
from futurewear.audit import audit_connector
from futurewear.connectors import (
    CONNECTOR_SIZE_PRESETS,
    FIT_PRESET_CLEARANCES_MM,
    ConnectorGender,
    ConnectorMount,
    ConnectorSize,
    ConnectorType,
    FitPreset,
    connector_metadata,
    derive_clearance_envelope,
    derive_male_dimensions,
    derive_receiver_dimensions,
    normalize_connector_parameters,
)
from futurewear.materials import MATERIAL_PROFILES, PrintProfile, material_profile


def test_connector_enums_and_metadata_are_stable():
    assert [item.value for item in ConnectorType] == ["Slide Rail", "Twist Lock", "Cord Loop"]
    assert [item.value for item in ConnectorGender] == ["Male", "Female", "Paired"]
    assert [item.value for item in ConnectorSize] == ["Mini", "Standard", "Wide"]
    assert [item.value for item in FitPreset] == ["Tight", "Standard", "Relaxed", "Custom"]
    assert connector_metadata()["standard_version"] == MODULAR_STANDARD_VERSION
    assert connector_metadata()["customer_name"] == "Dock"
    assert connector_metadata(ConnectorType.TWIST_LOCK)["customer_name"] == "Quarter Turn"


def test_size_presets_exact_nominal_dimensions():
    expected = {
        ConnectorSize.MINI: (10.0, 2.4, 12.0, 2.0, 1.8, 0.20, 0.6),
        ConnectorSize.STANDARD: (16.0, 3.0, 18.0, 2.4, 2.4, 0.25, 0.8),
        ConnectorSize.WIDE: (24.0, 3.4, 24.0, 2.8, 3.0, 0.30, 1.0),
    }
    assert set(CONNECTOR_SIZE_PRESETS) == set(expected)
    for size, values in expected.items():
        preset = CONNECTOR_SIZE_PRESETS[size]
        assert (
            preset.nominal_interface_width_mm,
            preset.nominal_interface_depth_mm,
            preset.engagement_length_mm,
            preset.minimum_surrounding_wall_mm,
            preset.stop_thickness_mm,
            preset.retention_depth_mm,
            preset.edge_radius_mm,
        ) == values


def test_fit_and_material_presets_are_stable():
    assert FIT_PRESET_CLEARANCES_MM == {
        FitPreset.TIGHT: 0.22,
        FitPreset.STANDARD: 0.32,
        FitPreset.RELAXED: 0.45,
        FitPreset.CUSTOM: 0.32,
    }
    assert set(MATERIAL_PROFILES) == {"PLA", "PETG"}
    assert material_profile("PLA").density_g_cm3 == 1.24
    assert material_profile("PETG").default_fit_clearance_mm == 0.35


def test_invalid_numeric_normalization_clamps_nan_and_infinity():
    params, warnings = normalize_connector_parameters(
        fit_clearance_mm=math.nan,
        printer_compensation_mm=math.inf,
        retention_depth_mm=99,
    )
    assert params.fit_clearance_mm == 0.32
    assert params.printer_compensation_mm == 0.0
    assert params.retention_depth_mm == params.nominal_interface_depth_mm * 0.22
    assert warnings


def test_male_receiver_derivation_keeps_nominal_and_clearance_separate():
    params, _ = normalize_connector_parameters(
        size=ConnectorSize.STANDARD,
        fit_clearance_mm=0.32,
        printer_compensation_mm=0.05,
    )
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    assert params.nominal_interface_width_mm == 16.0
    assert male.width_mm == 15.9
    assert receiver.width_mm == 16.74
    assert receiver.width_mm - male.width_mm == pytest.approx(0.84)
    assert receiver.depth_mm - male.depth_mm == pytest.approx(0.42)
    envelope = derive_clearance_envelope(params)
    assert envelope["clearance_per_side_mm"] == 0.32
    assert envelope["total_width_clearance_mm"] == 0.84


def test_cord_loop_has_no_retention_or_keying():
    params, _ = normalize_connector_parameters(connector_type=ConnectorType.CORD_LOOP, retention_depth_mm=0.3)
    assert params.retention_depth_mm == 0
    assert not params.keyed


def test_default_dock_audit_passes_without_warnings():
    params, _ = normalize_connector_parameters()
    audit = audit_connector(params, "PLA")
    assert not audit["warnings"]
    assert any(MODULAR_STANDARD_VERSION in message for message in audit["info"])
    assert any("Positive stop" in message for message in audit["passes"])


def test_audit_reports_fusing_loose_wall_stop_mount_and_compensation_risks():
    params, _ = normalize_connector_parameters(
        fit_clearance_mm=0.15,
        printer_compensation_mm=0.5,
        retention_depth_mm=0.5,
    )
    mount = ConnectorMount(
        name="unsafe",
        connector=params,
        position_mm=(0, 0, 0),
        rotation_deg=(0, 0, 0),
        insertion_axis=(0, 1, 0),
        wearer_side_axis=(0, 0, -1),
        engagement_direction=(0, 1, 0),
        wearer_facing_clearance_mm=1.0,
    )
    audit = audit_connector(params, "PLA", PrintProfile(elephant_foot_compensation_mm=0.5), mount)
    combined = " ".join(audit["warnings"])
    assert "fuse" in combined
    assert "Retention feature" in combined
    assert "wearer-facing safety zone" in combined
    assert "invalidate nominal compatibility" in combined


def test_cord_loop_audit_opening_range():
    params, _ = normalize_connector_parameters(connector_type=ConnectorType.CORD_LOOP, size=ConnectorSize.MINI)
    audit = audit_connector(params, "PLA")
    assert any("Cord loop opening" in message for message in audit["passes"])
