from pathlib import Path

from futurewear import MODULAR_STANDARD_VERSION
from futurewear.calibration import (
    AssemblyResult,
    CaliperMeasurements,
    ClearanceSampleResult,
    DamageResult,
    GateStatus,
    NullTileVerification,
    RetentionResult,
    WristwearReadiness,
    build_calibration_profile,
    compare_caliper_measurements,
    evaluate_gate_a,
    evaluate_gate_b,
    evaluate_gate_c,
    evaluate_gate_d,
    evaluate_sample,
    evaluate_wristwear_readiness,
    normalize_calibration_profile,
    normalize_clearance_sample,
    profile_to_json_dict,
    select_best_sample,
)
from futurewear.connector_coupons import build_dock_ladder_samples
from futurewear.connectors import ConnectorSize, ConnectorType, normalize_connector_parameters, summarize_effective_fit


def viable_sample(clearance=0.32, cycles=20, assembly=AssemblyResult.FIRM_FUNCTIONAL.value):
    return ClearanceSampleResult(
        clearance_mm=clearance,
        assembly_result=assembly,
        sliding_result="Controlled",
        retention_result=RetentionResult.FUNCTIONAL.value,
        damage_result=DamageResult.NONE.value,
        cycle_count=cycles,
        notes="",
    )


def test_clearance_sample_normalization_handles_malformed_values():
    sample = normalize_clearance_sample(
        {
            "clearance_mm": "bad",
            "assembly_result": "unknown",
            "sliding_result": "smooth",
            "retention_result": "functional",
            "damage_result": "none",
            "cycle_count": "bad",
        }
    )
    assert sample.clearance_mm == 0.32
    assert sample.assembly_result == AssemblyResult.UNUSABLE.value
    assert sample.sliding_result == "Smooth"
    assert sample.retention_result == "Functional"
    assert sample.damage_result == "None"
    assert sample.cycle_count == 0


def test_legacy_numeric_clearance_samples_remain_loadable_with_derived_ids():
    sample = normalize_clearance_sample(
        {
            "clearance_mm": 0.32,
            "assembly_result": AssemblyResult.FIRM_FUNCTIONAL.value,
            "sliding_result": "Controlled",
            "retention_result": RetentionResult.FUNCTIONAL.value,
            "damage_result": DamageResult.NONE.value,
            "cycle_count": 20,
        }
    )
    assert sample.clearance_mm == 0.32
    ladder = build_dock_ladder_samples(sample.clearance_mm)
    assert tuple(item.sample_id for item in ladder) == ("A", "B", "C", "D")
    assert ladder[1].clearance_mm == sample.clearance_mm


def test_profile_normalization_and_json_serialization():
    profile = normalize_calibration_profile(
        {
            "name": "Printer PLA",
            "connector_type": "Slide Rail",
            "connector_size": "Standard",
            "selected_clearance_mm": 0.42,
        }
    )
    assert profile.standard_version == MODULAR_STANDARD_VERSION
    assert profile.connector_type == ConnectorType.SLIDE_RAIL
    assert profile.connector_size == ConnectorSize.STANDARD
    data = profile_to_json_dict(profile)
    assert data["connector_type"] == "Slide Rail"
    assert data["connector_size"] == "Standard"


def test_sample_candidate_rejection_rules_are_explicit():
    rejected = [
        viable_sample(assembly=AssemblyResult.CANNOT_INSERT.value),
        viable_sample(assembly=AssemblyResult.EXCESSIVE_FORCE.value),
        viable_sample(assembly=AssemblyResult.LOOSE.value),
        viable_sample(clearance=0.42, cycles=20).__class__(
            0.42, AssemblyResult.SMOOTH_FUNCTIONAL.value, "Smooth", RetentionResult.RELEASES_UNINTENTIONALLY.value, DamageResult.NONE.value, 20, ""
        ),
        viable_sample(clearance=0.52, cycles=20).__class__(
            0.52, AssemblyResult.SMOOTH_FUNCTIONAL.value, "Smooth", RetentionResult.FUNCTIONAL.value, DamageResult.RECEIVER_CRACKING.value, 20, ""
        ),
        viable_sample(cycles=5),
    ]
    for sample in rejected:
        evaluation = evaluate_sample(sample)
        assert not evaluation.eligible
        assert any(reason.startswith("Rejected:") for reason in evaluation.reasons)


def test_best_sample_selection_prefers_firm_then_smooth_and_explains():
    samples = [
        viable_sample(0.42, assembly=AssemblyResult.SMOOTH_FUNCTIONAL.value),
        viable_sample(0.32, assembly=AssemblyResult.FIRM_FUNCTIONAL.value),
    ]
    selection = select_best_sample(samples)
    assert selection.selected_sample.clearance_mm == 0.32
    assert not selection.override_used
    assert any("Preferred" in reason for reason in selection.evaluations[1].reasons)


def test_user_override_is_supported_with_warning_for_rejected_sample():
    bad = viable_sample(0.22, assembly=AssemblyResult.LOOSE.value)
    good = viable_sample(0.32)
    selection = select_best_sample([bad, good], override_clearance_mm=0.22)
    assert selection.selected_sample.clearance_mm == 0.22
    assert selection.override_used
    assert selection.warnings == ("Override selected a sample that the rule-based gate rejected.",)


def test_physical_gates_and_readiness():
    sample = viable_sample()
    null_tile = NullTileVerification(True, True, True, True, True)
    assert evaluate_gate_a([sample]).status == GateStatus.PASS
    assert evaluate_gate_b(sample).status == GateStatus.PASS
    assert evaluate_gate_c(sample).status == GateStatus.PASS
    assert evaluate_gate_d(null_tile).status == GateStatus.PASS
    readiness, gates = evaluate_wristwear_readiness([sample], null_tile)
    assert readiness == WristwearReadiness.PASSED_EXPERIMENTAL
    assert all(gate.status == GateStatus.PASS for gate in gates)


def test_wristwear_readiness_reports_not_tested_or_failed():
    readiness, gates = evaluate_wristwear_readiness([], None)
    assert readiness == WristwearReadiness.NOT_TESTED
    assert any(gate.status == GateStatus.NOT_TESTED for gate in gates)
    readiness, gates = evaluate_wristwear_readiness([viable_sample()], NullTileVerification())
    assert readiness == WristwearReadiness.FAILED_PHYSICAL_GATE
    assert gates[-1].status == GateStatus.FAIL


def test_effective_fit_summary_and_compensation_contribution():
    params, _ = normalize_connector_parameters(fit_clearance_mm=0.32, printer_compensation_mm=0.05)
    summary = summarize_effective_fit(params)
    assert summary["nominal_male_width_mm"] == 16.0
    assert summary["generated_male_width_mm"] == 15.9
    assert summary["generated_receiver_width_mm"] == 16.74
    assert summary["expected_total_width_clearance_from_fit_mm"] == 0.64
    assert summary["effective_total_width_difference_mm"] == 0.84
    assert summary["printer_compensation_total_width_contribution_mm"] == 0.2


def test_caliper_measurement_observations_are_deterministic():
    params, _ = normalize_connector_parameters()
    observations = compare_caliper_measurements(
        params,
        CaliperMeasurements(
            printed_male_width_mm=16.3,
            printed_male_depth_mm=3.3,
            printed_receiver_opening_width_mm=16.2,
            printed_receiver_depth_mm=2.8,
            assembled_play_mm=1.1,
        ),
    )
    text = " ".join(observations["observations"])
    assert "male width printed oversized" in text
    assert "receiver width printed undersized" in text
    assert "Likely elephant-foot interference" in text
    assert "loose fit" in text


def test_build_calibration_profile_from_selected_sample():
    profile = build_calibration_profile(
        "Shop PLA Dock",
        viable_sample(0.42),
        material_name="PLA",
        printer_name="Printer A",
        slicer_name="Slicer A",
    )
    assert profile.name == "Shop PLA Dock"
    assert profile.selected_clearance_mm == 0.42
    assert profile.repeated_cycle_count == 20
    assert not profile.visible_damage
    assert profile.standard_version == MODULAR_STANDARD_VERSION
