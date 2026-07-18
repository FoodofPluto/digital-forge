"""Versioned connector data model and deterministic dimension derivation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .constants import (
    MAX_COMPATIBLE_PRINTER_COMPENSATION_MM,
    MAX_CONNECTOR_CLEARANCE_MM,
    MIN_CONNECTOR_CLEARANCE_MM,
    MODULAR_STANDARD_VERSION,
)
from .materials import MaterialProfile, PrintProfile, material_profile
from .math_utils import clamp, finite_float, normalize_vector


class ConnectorType(Enum):
    SLIDE_RAIL = "Slide Rail"
    TWIST_LOCK = "Twist Lock"
    CORD_LOOP = "Cord Loop"


class ConnectorGender(Enum):
    MALE = "Male"
    FEMALE = "Female"
    PAIRED = "Paired"


class ConnectorSize(Enum):
    MINI = "Mini"
    STANDARD = "Standard"
    WIDE = "Wide"


class FitPreset(Enum):
    TIGHT = "Tight"
    STANDARD = "Standard"
    RELAXED = "Relaxed"
    CUSTOM = "Custom"


@dataclass(frozen=True)
class ConnectorParameters:
    standard_version: str
    connector_type: ConnectorType
    gender: ConnectorGender
    size: ConnectorSize
    nominal_interface_width_mm: float
    nominal_interface_depth_mm: float
    engagement_length_mm: float
    fit_clearance_mm: float
    printer_compensation_mm: float
    minimum_surrounding_wall_mm: float
    stop_thickness_mm: float
    retention_depth_mm: float
    edge_radius_mm: float
    keyed: bool = True
    debug_geometry: bool = False


@dataclass(frozen=True)
class ConnectorMount:
    name: str
    connector: ConnectorParameters
    position_mm: tuple[float, float, float]
    rotation_deg: tuple[float, float, float]
    insertion_axis: tuple[float, float, float]
    wearer_side_axis: tuple[float, float, float]
    engagement_direction: tuple[float, float, float]
    wearer_facing_clearance_mm: float


@dataclass(frozen=True)
class ConnectorAuditResult:
    warnings: tuple[str, ...]
    info: tuple[str, ...]
    passes: tuple[str, ...]


@dataclass(frozen=True)
class DerivedConnectorDimensions:
    width_mm: float
    depth_mm: float
    engagement_length_mm: float
    stop_thickness_mm: float
    retention_depth_mm: float
    key_offset_mm: float
    entrance_chamfer_mm: float
    edge_radius_mm: float


@dataclass(frozen=True)
class ConnectorSizePreset:
    size: ConnectorSize
    nominal_interface_width_mm: float
    nominal_interface_depth_mm: float
    engagement_length_mm: float
    minimum_surrounding_wall_mm: float
    stop_thickness_mm: float
    retention_depth_mm: float
    edge_radius_mm: float
    compatible_product_scale: str


CONNECTOR_SIZE_PRESETS: dict[ConnectorSize, ConnectorSizePreset] = {
    ConnectorSize.MINI: ConnectorSizePreset(
        ConnectorSize.MINI, 10.0, 2.4, 12.0, 2.0, 1.8, 0.20, 0.6, "small charms, side modules, zipper pulls"
    ),
    ConnectorSize.STANDARD: ConnectorSizePreset(
        ConnectorSize.STANDARD, 16.0, 3.0, 18.0, 2.4, 2.4, 0.25, 0.8, "wristwear center modules, pendants, bag charms"
    ),
    ConnectorSize.WIDE: ConnectorSizePreset(
        ConnectorSize.WIDE, 24.0, 3.4, 24.0, 2.8, 3.0, 0.30, 1.0, "wide face modules and sling-bag attachment tiles"
    ),
}

FIT_PRESET_CLEARANCES_MM: dict[FitPreset, float] = {
    FitPreset.TIGHT: 0.22,
    FitPreset.STANDARD: 0.32,
    FitPreset.RELAXED: 0.45,
    FitPreset.CUSTOM: 0.32,
}

CUSTOMER_CONNECTOR_NAMES = {
    ConnectorType.SLIDE_RAIL: "Dock",
    ConnectorType.TWIST_LOCK: "Quarter Turn",
    ConnectorType.CORD_LOOP: "Cord Loop",
}


def _enum_value(enum_type, value, fallback):
    if isinstance(value, enum_type):
        return value
    text = str(value or "").strip()
    for item in enum_type:
        if text.lower() in {item.value.lower(), item.name.lower().replace("_", " "), item.name.lower()}:
            return item
    return fallback


def connector_size_preset(size: ConnectorSize | str = ConnectorSize.STANDARD) -> ConnectorSizePreset:
    return CONNECTOR_SIZE_PRESETS[_enum_value(ConnectorSize, size, ConnectorSize.STANDARD)]


def connector_metadata(
    connector_type: ConnectorType | str = ConnectorType.SLIDE_RAIL,
    size: ConnectorSize | str = ConnectorSize.STANDARD,
) -> dict[str, object]:
    ctype = _enum_value(ConnectorType, connector_type, ConnectorType.SLIDE_RAIL)
    preset = connector_size_preset(size)
    return {
        "standard_version": MODULAR_STANDARD_VERSION,
        "connector_type": ctype.value,
        "customer_name": CUSTOMER_CONNECTOR_NAMES[ctype],
        "size": preset.size.value,
        "compatible_product_scale": preset.compatible_product_scale,
    }


def normalize_connector_parameters(
    connector_type: ConnectorType | str = ConnectorType.SLIDE_RAIL,
    gender: ConnectorGender | str = ConnectorGender.PAIRED,
    size: ConnectorSize | str = ConnectorSize.STANDARD,
    fit_preset: FitPreset | str = FitPreset.STANDARD,
    material: MaterialProfile | str | None = None,
    print_profile: PrintProfile | None = None,
    fit_clearance_mm: float | None = None,
    printer_compensation_mm: float | None = None,
    retention_depth_mm: float | None = None,
    debug_geometry: bool = False,
) -> tuple[ConnectorParameters, list[str]]:
    warnings: list[str] = []
    ctype = _enum_value(ConnectorType, connector_type, ConnectorType.SLIDE_RAIL)
    cgender = _enum_value(ConnectorGender, gender, ConnectorGender.PAIRED)
    csize = _enum_value(ConnectorSize, size, ConnectorSize.STANDARD)
    fpreset = _enum_value(FitPreset, fit_preset, FitPreset.STANDARD)
    mat = material if isinstance(material, MaterialProfile) else material_profile(material)
    printer = print_profile or PrintProfile()
    preset = CONNECTOR_SIZE_PRESETS[csize]

    clearance_default = mat.default_fit_clearance_mm if fpreset == FitPreset.CUSTOM else FIT_PRESET_CLEARANCES_MM[fpreset]
    requested_clearance = finite_float(fit_clearance_mm, clearance_default) if fit_clearance_mm is not None else clearance_default
    clearance = clamp(requested_clearance, MIN_CONNECTOR_CLEARANCE_MM, MAX_CONNECTOR_CLEARANCE_MM)
    if clearance != requested_clearance:
        warnings.append(f"Fit clearance was clamped to {clearance:g} mm per side.")

    requested_comp = (
        finite_float(printer_compensation_mm, printer.printer_compensation_mm)
        if printer_compensation_mm is not None
        else finite_float(printer.printer_compensation_mm, 0.0)
    )
    comp = clamp(requested_comp, -0.5, 0.5)
    if comp != requested_comp:
        warnings.append(f"Printer compensation was clamped to {comp:g} mm.")

    requested_retention = finite_float(retention_depth_mm, preset.retention_depth_mm) if retention_depth_mm is not None else preset.retention_depth_mm
    retention = clamp(requested_retention, 0.0, preset.nominal_interface_depth_mm * 0.22)
    if retention != requested_retention:
        warnings.append(f"Retention depth was clamped to {retention:g} mm.")
    if ctype == ConnectorType.CORD_LOOP:
        retention = 0.0

    return (
        ConnectorParameters(
            standard_version=MODULAR_STANDARD_VERSION,
            connector_type=ctype,
            gender=cgender,
            size=csize,
            nominal_interface_width_mm=preset.nominal_interface_width_mm,
            nominal_interface_depth_mm=preset.nominal_interface_depth_mm,
            engagement_length_mm=preset.engagement_length_mm,
            fit_clearance_mm=clearance,
            printer_compensation_mm=comp,
            minimum_surrounding_wall_mm=max(preset.minimum_surrounding_wall_mm, mat.minimum_wall_mm),
            stop_thickness_mm=preset.stop_thickness_mm,
            retention_depth_mm=retention,
            edge_radius_mm=max(preset.edge_radius_mm, mat.minimum_edge_radius_mm),
            keyed=ctype != ConnectorType.CORD_LOOP,
            debug_geometry=bool(debug_geometry),
        ),
        warnings,
    )


def derive_male_dimensions(params: ConnectorParameters) -> DerivedConnectorDimensions:
    """Return generated male dimensions. Clearance is per side and is not baked into nominal dimensions."""
    comp = params.printer_compensation_mm
    return DerivedConnectorDimensions(
        width_mm=round(max(0.1, params.nominal_interface_width_mm - comp * 2), 6),
        depth_mm=round(max(0.1, params.nominal_interface_depth_mm - comp), 6),
        engagement_length_mm=round(max(0.1, params.engagement_length_mm - comp), 6),
        stop_thickness_mm=params.stop_thickness_mm,
        retention_depth_mm=params.retention_depth_mm,
        key_offset_mm=0.10 * params.nominal_interface_width_mm if params.keyed else 0.0,
        entrance_chamfer_mm=max(0.5, params.edge_radius_mm * 0.75),
        edge_radius_mm=params.edge_radius_mm,
    )


def derive_receiver_dimensions(params: ConnectorParameters) -> DerivedConnectorDimensions:
    """Return generated receiver dimensions. Clearance is applied per side around mating width/depth."""
    comp = params.printer_compensation_mm
    clearance = params.fit_clearance_mm
    return DerivedConnectorDimensions(
        width_mm=round(params.nominal_interface_width_mm + clearance * 2 + comp * 2, 6),
        depth_mm=round(params.nominal_interface_depth_mm + clearance + comp, 6),
        engagement_length_mm=round(params.engagement_length_mm + clearance + comp, 6),
        stop_thickness_mm=params.stop_thickness_mm,
        retention_depth_mm=max(0.0, params.retention_depth_mm - clearance * 0.35),
        key_offset_mm=0.10 * params.nominal_interface_width_mm if params.keyed else 0.0,
        entrance_chamfer_mm=max(0.5, params.edge_radius_mm * 0.75),
        edge_radius_mm=params.edge_radius_mm,
    )


def derive_clearance_envelope(params: ConnectorParameters) -> dict[str, float]:
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    return {
        "clearance_per_side_mm": params.fit_clearance_mm,
        "total_width_clearance_mm": round(receiver.width_mm - male.width_mm, 6),
        "depth_clearance_mm": round(receiver.depth_mm - male.depth_mm, 6),
        "engagement_clearance_mm": round(receiver.engagement_length_mm - male.engagement_length_mm, 6),
    }


def summarize_effective_fit(params: ConnectorParameters) -> dict[str, float]:
    """Expose nominal, generated, and compensation effects for fit review."""
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    compensation_width_contribution = abs(params.printer_compensation_mm) * 4
    return {
        "nominal_male_width_mm": params.nominal_interface_width_mm,
        "generated_male_width_mm": male.width_mm,
        "nominal_receiver_width_mm": params.nominal_interface_width_mm,
        "generated_receiver_width_mm": receiver.width_mm,
        "requested_clearance_per_side_mm": params.fit_clearance_mm,
        "expected_total_width_clearance_from_fit_mm": round(params.fit_clearance_mm * 2, 6),
        "effective_total_width_difference_mm": round(receiver.width_mm - male.width_mm, 6),
        "printer_compensation_mm": params.printer_compensation_mm,
        "printer_compensation_total_width_contribution_mm": round(compensation_width_contribution, 6),
    }


def paired_connector_parameters(params: ConnectorParameters) -> tuple[ConnectorParameters, ConnectorParameters]:
    return replace(params, gender=ConnectorGender.MALE), replace(params, gender=ConnectorGender.FEMALE)


def normalize_connector_mount(mount: ConnectorMount) -> ConnectorMount:
    return replace(
        mount,
        insertion_axis=normalize_vector(mount.insertion_axis),
        wearer_side_axis=normalize_vector(mount.wearer_side_axis),
        engagement_direction=normalize_vector(mount.engagement_direction),
    )


def compensation_invalidates_nominal_compatibility(params: ConnectorParameters) -> bool:
    return abs(params.printer_compensation_mm) > MAX_COMPATIBLE_PRINTER_COMPENSATION_MM
