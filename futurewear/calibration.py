"""Physical calibration records and readiness gates for Futurewear connectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from .constants import MODULAR_STANDARD_VERSION
from .connectors import (
    ConnectorParameters,
    ConnectorSize,
    ConnectorType,
    derive_male_dimensions,
    derive_receiver_dimensions,
    normalize_connector_parameters,
    summarize_effective_fit,
)
from .materials import PrintProfile
from .math_utils import finite_float

MIN_CYCLE_COUNT = 20
CALIBRATION_SCHEMA_VERSION = 1


class AssemblyResult(Enum):
    CANNOT_INSERT = "Cannot Insert"
    EXCESSIVE_FORCE = "Inserts With Excessive Force"
    FIRM_FUNCTIONAL = "Firm Functional Fit"
    SMOOTH_FUNCTIONAL = "Smooth Functional Fit"
    LOOSE = "Loose Fit"
    UNUSABLE = "Unusable"


class SlidingResult(Enum):
    CANNOT_EVALUATE = "Cannot Evaluate"
    GRITTY = "Gritty"
    CONTROLLED = "Controlled"
    SMOOTH = "Smooth"
    BINDING = "Binding"


class RetentionResult(Enum):
    CANNOT_EVALUATE = "Cannot Evaluate"
    STRONG = "Strong"
    FUNCTIONAL = "Functional"
    WEAK = "Weak"
    RELEASES_UNINTENTIONALLY = "Releases Unintentionally"


class DamageResult(Enum):
    NONE = "None"
    SURFACE_MARKING = "Surface Marking"
    RIB_DEFORMATION = "Rib Deformation"
    RAIL_DEFORMATION = "Rail Deformation"
    RECEIVER_CRACKING = "Receiver Cracking"
    OTHER = "Other"


class GateStatus(Enum):
    NOT_TESTED = "Not Tested"
    PASS = "Pass"
    FAIL = "Fail"


class WristwearReadiness(Enum):
    NOT_TESTED = "Not Tested"
    CALIBRATION_IN_PROGRESS = "Calibration In Progress"
    FAILED_PHYSICAL_GATE = "Failed Physical Gate"
    PASSED_EXPERIMENTAL = "Passed for Experimental Wristwear Prototype"


@dataclass(frozen=True)
class ClearanceSampleResult:
    clearance_mm: float
    assembly_result: str
    sliding_result: str
    retention_result: str
    damage_result: str
    cycle_count: int
    notes: str = ""


@dataclass(frozen=True)
class ConnectorCalibrationProfile:
    profile_id: str
    name: str
    standard_version: str
    connector_type: ConnectorType
    connector_size: ConnectorSize
    material_name: str
    printer_name: str
    nozzle_diameter_mm: float
    layer_height_mm: float
    slicer_name: str
    print_orientation: str
    printer_compensation_mm: float
    elephant_foot_compensation_mm: float
    selected_clearance_mm: float
    fit_rating: str
    repeated_cycle_count: int
    retention_result: str
    visible_damage: bool
    notes: str
    created_at: str
    archived: bool = False


@dataclass(frozen=True)
class NullTileVerification:
    installs: bool = False
    reaches_positive_stop: bool = False
    key_blocks_reversed_installation: bool = False
    acceptably_flush: bool = False
    removable_without_damage: bool = False
    notes: str = ""


@dataclass(frozen=True)
class CaliperMeasurements:
    printed_male_width_mm: float | None = None
    printed_male_depth_mm: float | None = None
    printed_receiver_opening_width_mm: float | None = None
    printed_receiver_depth_mm: float | None = None
    assembled_play_mm: float | None = None


@dataclass(frozen=True)
class SampleEvaluation:
    clearance_mm: float
    eligible: bool
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SelectionResult:
    selected_sample: ClearanceSampleResult | None
    evaluations: tuple[SampleEvaluation, ...]
    warnings: tuple[str, ...]
    override_used: bool = False


@dataclass(frozen=True)
class GateEvaluation:
    name: str
    status: GateStatus
    evidence: tuple[str, ...]
    outstanding: tuple[str, ...]


def _enum_value(enum_type, value, fallback):
    if isinstance(value, enum_type):
        return value
    text = str(value or "").strip()
    for item in enum_type:
        if text.lower() in {item.value.lower(), item.name.lower().replace("_", " "), item.name.lower()}:
            return item
    return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_clearance_sample(data: ClearanceSampleResult | dict) -> ClearanceSampleResult:
    if isinstance(data, ClearanceSampleResult):
        return data
    return ClearanceSampleResult(
        clearance_mm=round(finite_float(data.get("clearance_mm"), 0.32), 6),
        assembly_result=_enum_value(AssemblyResult, data.get("assembly_result"), AssemblyResult.UNUSABLE).value,
        sliding_result=_enum_value(SlidingResult, data.get("sliding_result"), SlidingResult.CANNOT_EVALUATE).value,
        retention_result=_enum_value(RetentionResult, data.get("retention_result"), RetentionResult.CANNOT_EVALUATE).value,
        damage_result=_enum_value(DamageResult, data.get("damage_result"), DamageResult.OTHER).value,
        cycle_count=max(0, int(finite_float(data.get("cycle_count"), 0))),
        notes=str(data.get("notes", "")),
    )


def normalize_calibration_profile(data: ConnectorCalibrationProfile | dict) -> ConnectorCalibrationProfile:
    if isinstance(data, ConnectorCalibrationProfile):
        return data
    connector_type = _enum_value(ConnectorType, data.get("connector_type"), ConnectorType.SLIDE_RAIL)
    connector_size = _enum_value(ConnectorSize, data.get("connector_size"), ConnectorSize.STANDARD)
    return ConnectorCalibrationProfile(
        profile_id=str(data.get("profile_id") or uuid4()),
        name=str(data.get("name") or "Unnamed Calibration"),
        standard_version=str(data.get("standard_version") or MODULAR_STANDARD_VERSION),
        connector_type=connector_type,
        connector_size=connector_size,
        material_name=str(data.get("material_name") or "PLA"),
        printer_name=str(data.get("printer_name") or "Unknown Printer"),
        nozzle_diameter_mm=finite_float(data.get("nozzle_diameter_mm"), 0.4),
        layer_height_mm=finite_float(data.get("layer_height_mm"), 0.2),
        slicer_name=str(data.get("slicer_name") or "Unknown Slicer"),
        print_orientation=str(data.get("print_orientation") or "Flat on build plate"),
        printer_compensation_mm=finite_float(data.get("printer_compensation_mm"), 0.0),
        elephant_foot_compensation_mm=finite_float(data.get("elephant_foot_compensation_mm"), 0.0),
        selected_clearance_mm=finite_float(data.get("selected_clearance_mm"), 0.32),
        fit_rating=str(data.get("fit_rating") or AssemblyResult.SMOOTH_FUNCTIONAL.value),
        repeated_cycle_count=max(0, int(finite_float(data.get("repeated_cycle_count"), 0))),
        retention_result=str(data.get("retention_result") or RetentionResult.CANNOT_EVALUATE.value),
        visible_damage=bool(data.get("visible_damage", False)),
        notes=str(data.get("notes") or ""),
        created_at=str(data.get("created_at") or _now_iso()),
        archived=bool(data.get("archived", False)),
    )


def profile_to_json_dict(profile: ConnectorCalibrationProfile) -> dict[str, object]:
    data = asdict(profile)
    data["connector_type"] = profile.connector_type.value
    data["connector_size"] = profile.connector_size.value
    return data


def evaluate_sample(sample: ClearanceSampleResult, minimum_cycles: int = MIN_CYCLE_COUNT) -> SampleEvaluation:
    sample = normalize_clearance_sample(sample)
    reasons: list[str] = []
    score = 0
    assembly = _enum_value(AssemblyResult, sample.assembly_result, AssemblyResult.UNUSABLE)
    retention = _enum_value(RetentionResult, sample.retention_result, RetentionResult.CANNOT_EVALUATE)
    damage = _enum_value(DamageResult, sample.damage_result, DamageResult.OTHER)

    if assembly in {AssemblyResult.CANNOT_INSERT, AssemblyResult.EXCESSIVE_FORCE, AssemblyResult.LOOSE, AssemblyResult.UNUSABLE}:
        reasons.append(f"Rejected: assembly result is {assembly.value}.")
    elif assembly == AssemblyResult.FIRM_FUNCTIONAL:
        score += 100
        reasons.append("Preferred: firm functional fit.")
    elif assembly == AssemblyResult.SMOOTH_FUNCTIONAL:
        score += 90
        reasons.append("Usable: smooth functional fit.")
    else:
        score += 50
        reasons.append("Usable only with warning: non-preferred assembly result.")

    if retention == RetentionResult.RELEASES_UNINTENTIONALLY:
        reasons.append("Rejected: releases unintentionally.")
    elif retention in {RetentionResult.STRONG, RetentionResult.FUNCTIONAL}:
        score += 20
        reasons.append(f"Retention is {retention.value.lower()}.")
    elif retention == RetentionResult.WEAK:
        score += 5
        reasons.append("Retention is weak.")
    else:
        reasons.append("Retention could not be evaluated.")

    if damage in {DamageResult.RECEIVER_CRACKING, DamageResult.RAIL_DEFORMATION, DamageResult.RIB_DEFORMATION}:
        reasons.append(f"Rejected: structural damage reported ({damage.value}).")
    elif damage == DamageResult.NONE:
        score += 15
        reasons.append("No visible damage.")
    else:
        score += 5
        reasons.append(f"Non-structural damage/marking reported: {damage.value}.")

    if sample.cycle_count < minimum_cycles:
        reasons.append(f"Rejected: only {sample.cycle_count} cycles recorded; minimum is {minimum_cycles}.")
    else:
        score += min(sample.cycle_count, 60) // 10
        reasons.append(f"Cycle count meets minimum: {sample.cycle_count}.")

    eligible = not any(reason.startswith("Rejected:") for reason in reasons)
    return SampleEvaluation(sample.clearance_mm, eligible, score if eligible else -1, tuple(reasons))


def select_best_sample(
    samples: list[ClearanceSampleResult],
    minimum_cycles: int = MIN_CYCLE_COUNT,
    override_clearance_mm: float | None = None,
) -> SelectionResult:
    normalized = [normalize_clearance_sample(sample) for sample in samples]
    evaluations = tuple(evaluate_sample(sample, minimum_cycles) for sample in normalized)
    warnings: list[str] = []
    if override_clearance_mm is not None:
        for sample, evaluation in zip(normalized, evaluations):
            if sample.clearance_mm == round(float(override_clearance_mm), 6):
                if not evaluation.eligible:
                    warnings.append("Override selected a sample that the rule-based gate rejected.")
                return SelectionResult(sample, evaluations, tuple(warnings), True)
        warnings.append("Override clearance did not match a recorded sample.")
    eligible = [(sample, evaluation) for sample, evaluation in zip(normalized, evaluations) if evaluation.eligible]
    if not eligible:
        return SelectionResult(None, evaluations, tuple(warnings), False)
    preferred_order = {
        AssemblyResult.FIRM_FUNCTIONAL.value: 0,
        AssemblyResult.SMOOTH_FUNCTIONAL.value: 1,
    }
    selected, _evaluation = sorted(
        eligible,
        key=lambda pair: (
            preferred_order.get(pair[0].assembly_result, 2),
            -pair[1].score,
            pair[0].clearance_mm,
        ),
    )[0]
    return SelectionResult(selected, evaluations, tuple(warnings), False)


def evaluate_gate_a(samples: list[ClearanceSampleResult]) -> GateEvaluation:
    if not samples:
        return GateEvaluation("Gate A - Basic Assembly", GateStatus.NOT_TESTED, (), ("Record at least one ladder sample.",))
    selection = select_best_sample(samples, minimum_cycles=0)
    if selection.selected_sample:
        return GateEvaluation("Gate A - Basic Assembly", GateStatus.PASS, ("At least one sample inserts without excessive force or structural damage.",), ())
    return GateEvaluation("Gate A - Basic Assembly", GateStatus.FAIL, ("No sample met basic insertion requirements.",), ("Print a new ladder or adjust cleanup/settings.",))


def evaluate_gate_b(sample: ClearanceSampleResult | None) -> GateEvaluation:
    if sample is None:
        return GateEvaluation("Gate B - Functional Retention", GateStatus.NOT_TESTED, (), ("Select a candidate sample.",))
    sample = normalize_clearance_sample(sample)
    retention = _enum_value(RetentionResult, sample.retention_result, RetentionResult.CANNOT_EVALUATE)
    assembly = _enum_value(AssemblyResult, sample.assembly_result, AssemblyResult.UNUSABLE)
    if retention in {RetentionResult.STRONG, RetentionResult.FUNCTIONAL} and assembly in {
        AssemblyResult.FIRM_FUNCTIONAL,
        AssemblyResult.SMOOTH_FUNCTIONAL,
    }:
        return GateEvaluation("Gate B - Functional Retention", GateStatus.PASS, ("Selected sample remains installed and can be intentionally removed.",), ())
    return GateEvaluation("Gate B - Functional Retention", GateStatus.FAIL, (f"Retention result: {retention.value}.",), ("Choose a sample with functional retention.",))


def evaluate_gate_c(sample: ClearanceSampleResult | None, minimum_cycles: int = MIN_CYCLE_COUNT) -> GateEvaluation:
    if sample is None:
        return GateEvaluation("Gate C - Repeated Cycling", GateStatus.NOT_TESTED, (), ("Run repeated insertion/removal cycles.",))
    evaluation = evaluate_sample(sample, minimum_cycles)
    if evaluation.eligible:
        return GateEvaluation("Gate C - Repeated Cycling", GateStatus.PASS, (f"Sample survived {sample.cycle_count} cycles.",), ())
    return GateEvaluation("Gate C - Repeated Cycling", GateStatus.FAIL, evaluation.reasons, ("Repeat cycling with a viable sample.",))


def evaluate_gate_d(null_tile: NullTileVerification | None) -> GateEvaluation:
    if null_tile is None:
        return GateEvaluation("Gate D - Null Tile Verification", GateStatus.NOT_TESTED, (), ("Record Null Tile test results.",))
    checks = {
        "installs": null_tile.installs,
        "reaches positive stop": null_tile.reaches_positive_stop,
        "key blocks reversed installation": null_tile.key_blocks_reversed_installation,
        "appears acceptably flush": null_tile.acceptably_flush,
        "removes without damage": null_tile.removable_without_damage,
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    if failed:
        return GateEvaluation("Gate D - Null Tile Verification", GateStatus.FAIL, tuple(f"Missing: {name}." for name in failed), ("Reprint or adjust selected clearance before wristwear.",))
    return GateEvaluation("Gate D - Null Tile Verification", GateStatus.PASS, tuple(f"Confirmed: {name}." for name in checks), ())


def evaluate_wristwear_readiness(
    samples: list[ClearanceSampleResult],
    null_tile: NullTileVerification | None,
    connector_type: ConnectorType = ConnectorType.SLIDE_RAIL,
    connector_size: ConnectorSize = ConnectorSize.STANDARD,
) -> tuple[WristwearReadiness, tuple[GateEvaluation, ...]]:
    if connector_type != ConnectorType.SLIDE_RAIL or connector_size != ConnectorSize.STANDARD:
        gate = GateEvaluation("Gate E - Wristwear Readiness", GateStatus.FAIL, ("Wristwear gate requires Standard Dock.",), ("Test Standard Dock for the intended printer/material.",))
        return WristwearReadiness.FAILED_PHYSICAL_GATE, (gate,)
    selection = select_best_sample(samples)
    selected = selection.selected_sample
    gates = (
        evaluate_gate_a(samples),
        evaluate_gate_b(selected),
        evaluate_gate_c(selected),
        evaluate_gate_d(null_tile),
    )
    if all(gate.status == GateStatus.PASS for gate in gates):
        return WristwearReadiness.PASSED_EXPERIMENTAL, gates
    if any(gate.status == GateStatus.FAIL for gate in gates):
        return WristwearReadiness.FAILED_PHYSICAL_GATE, gates
    if any(gate.status == GateStatus.PASS for gate in gates):
        return WristwearReadiness.CALIBRATION_IN_PROGRESS, gates
    return WristwearReadiness.NOT_TESTED, gates


def build_calibration_profile(
    name: str,
    selected_sample: ClearanceSampleResult,
    material_name: str = "PLA",
    printer_name: str = "Unknown Printer",
    nozzle_diameter_mm: float = 0.4,
    layer_height_mm: float = 0.2,
    slicer_name: str = "Unknown Slicer",
    print_orientation: str = "Flat on build plate",
    printer_compensation_mm: float = 0.0,
    elephant_foot_compensation_mm: float = 0.0,
    connector_type: ConnectorType = ConnectorType.SLIDE_RAIL,
    connector_size: ConnectorSize = ConnectorSize.STANDARD,
    notes: str = "",
) -> ConnectorCalibrationProfile:
    sample = normalize_clearance_sample(selected_sample)
    visible_damage = _enum_value(DamageResult, sample.damage_result, DamageResult.OTHER) != DamageResult.NONE
    return ConnectorCalibrationProfile(
        profile_id=str(uuid4()),
        name=name,
        standard_version=MODULAR_STANDARD_VERSION,
        connector_type=connector_type,
        connector_size=connector_size,
        material_name=material_name,
        printer_name=printer_name,
        nozzle_diameter_mm=nozzle_diameter_mm,
        layer_height_mm=layer_height_mm,
        slicer_name=slicer_name,
        print_orientation=print_orientation,
        printer_compensation_mm=printer_compensation_mm,
        elephant_foot_compensation_mm=elephant_foot_compensation_mm,
        selected_clearance_mm=sample.clearance_mm,
        fit_rating=sample.assembly_result,
        repeated_cycle_count=sample.cycle_count,
        retention_result=sample.retention_result,
        visible_damage=visible_damage,
        notes=notes,
        created_at=_now_iso(),
    )


def compare_caliper_measurements(params: ConnectorParameters, measurements: CaliperMeasurements) -> dict[str, float | list[str]]:
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    observations: list[str] = []
    result: dict[str, float | list[str]] = {"observations": observations}

    def record(name: str, measured: float | None, target: float) -> None:
        if measured is None:
            return
        error = round(measured - target, 6)
        result[f"{name}_error_mm"] = error
        if error > 0.15:
            observations.append(f"{name.replace('_', ' ')} printed oversized.")
        elif error < -0.15:
            observations.append(f"{name.replace('_', ' ')} printed undersized.")

    record("male_width", measurements.printed_male_width_mm, male.width_mm)
    record("male_depth", measurements.printed_male_depth_mm, male.depth_mm)
    record("receiver_width", measurements.printed_receiver_opening_width_mm, receiver.width_mm)
    record("receiver_depth", measurements.printed_receiver_depth_mm, receiver.depth_mm)
    if measurements.assembled_play_mm is not None:
        result["assembled_play_mm"] = measurements.assembled_play_mm
        if measurements.assembled_play_mm > params.fit_clearance_mm * 2 + 0.3:
            observations.append("Assembled play suggests likely excessive compensation or loose fit.")
    if measurements.printed_male_depth_mm is not None and measurements.printed_male_depth_mm > male.depth_mm + 0.2:
        observations.append("Likely elephant-foot interference on male depth or first-layer edges.")
    return result


def connector_params_from_profile(profile: ConnectorCalibrationProfile) -> ConnectorParameters:
    return normalize_connector_parameters(
        connector_type=profile.connector_type,
        size=profile.connector_size,
        material=profile.material_name,
        fit_clearance_mm=profile.selected_clearance_mm,
        print_profile=PrintProfile(
            nozzle_diameter_mm=profile.nozzle_diameter_mm,
            layer_height_mm=profile.layer_height_mm,
            printer_compensation_mm=profile.printer_compensation_mm,
            elephant_foot_compensation_mm=profile.elephant_foot_compensation_mm,
        ),
    )[0]
