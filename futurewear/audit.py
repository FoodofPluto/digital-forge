"""Audits for Digital Forge Futurewear connector geometry."""

from .constants import (
    MAX_COMPATIBLE_PRINTER_COMPENSATION_MM,
    MIN_FDM_CHAMFER_MM,
    MIN_FDM_FEATURE_MM,
    MIN_DOCK_KEY_OFFSET_MM,
    MODULAR_STANDARD_VERSION,
)
from .connectors import (
    ConnectorAuditResult,
    ConnectorMount,
    ConnectorParameters,
    ConnectorType,
    compensation_invalidates_nominal_compatibility,
    derive_clearance_envelope,
    derive_male_dimensions,
    derive_receiver_dimensions,
)
from .materials import MaterialProfile, PrintProfile, material_profile


def audit_connector(
    params: ConnectorParameters,
    material: MaterialProfile | str | None = None,
    print_profile: PrintProfile | None = None,
    mount: ConnectorMount | None = None,
) -> dict[str, list[str]]:
    mat = material if isinstance(material, MaterialProfile) else material_profile(material)
    printer = print_profile or PrintProfile()
    warnings: list[str] = []
    info: list[str] = [
        f"Modular standard: {MODULAR_STANDARD_VERSION}.",
        "Fit clearance is per side for width and one-sided for receiver depth/engagement relief.",
        "Digital validation does not replace physical tolerance testing on the target printer.",
    ]
    passes: list[str] = []
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    envelope = derive_clearance_envelope(params)
    implied_width_gap = params.fit_clearance_mm * 2
    if envelope["total_width_clearance_mm"] > implied_width_gap + 0.35:
        warnings.append(
            "Printer compensation substantially increases the effective width gap beyond the selected fit preset."
        )

    if params.fit_clearance_mm < 0.22:
        warnings.append("Clearance is likely to fuse on moderate FDM printers.")
    elif params.fit_clearance_mm > 0.55:
        warnings.append("Clearance may feel excessively loose without secondary retention.")
    else:
        passes.append("Fit clearance is within the default FDM calibration range.")

    if params.minimum_surrounding_wall_mm < mat.minimum_wall_mm:
        warnings.append(f"Surrounding wall is below the {mat.name} minimum wall recommendation.")
    else:
        passes.append("Surrounding wall meets the selected material minimum.")

    if params.stop_thickness_mm < mat.minimum_wall_mm:
        warnings.append("Positive stop may be too weak for repeated module insertion.")
    else:
        passes.append("Positive stop thickness is in the printable load-bearing range.")

    if params.engagement_length_mm < params.nominal_interface_width_mm * 0.9:
        warnings.append("Engagement length is short relative to interface width.")
    else:
        passes.append("Engagement length is sufficient for a guided connector.")

    if params.retention_depth_mm > params.fit_clearance_mm * 1.25 and params.connector_type == ConnectorType.SLIDE_RAIL:
        warnings.append("Retention feature may be too aggressive for smooth sliding fit.")
    elif 0 < params.retention_depth_mm < 0.16:
        warnings.append("Retention feature is shallow enough that it may not matter after sanding or slicer variation.")
    elif params.connector_type == ConnectorType.SLIDE_RAIL:
        passes.append("Dock retention depth is restrained.")

    if params.keyed and male.key_offset_mm < MIN_DOCK_KEY_OFFSET_MM:
        warnings.append("Key feature is below the practical printable offset.")
    elif params.keyed:
        passes.append("Asymmetric key feature is large enough to print.")

    if male.entrance_chamfer_mm < MIN_FDM_CHAMFER_MM:
        warnings.append("Entrance chamfer is too small for reliable insertion.")
    else:
        passes.append("Entrance chamfer is large enough to guide assembly.")

    if params.edge_radius_mm < mat.minimum_edge_radius_mm:
        warnings.append("Edge radius is unsuitable for wearable skin-adjacent use.")
    else:
        passes.append("Edge radius meets the selected wearable material profile.")

    if params.connector_type == ConnectorType.CORD_LOOP:
        opening = max(params.nominal_interface_width_mm - params.minimum_surrounding_wall_mm * 2, 0)
        if params.minimum_surrounding_wall_mm < mat.minimum_wall_mm:
            warnings.append("Cord loop wall is too thin around the opening.")
        if opening < 3.0:
            warnings.append("Cord loop opening is too small for common cord, elastic, or split-ring testing.")
        else:
            passes.append("Cord loop opening is in the printable utility range.")

    if receiver.depth_mm <= male.depth_mm:
        warnings.append("Receiver depth does not exceed male depth; parts may fuse.")
    if envelope["total_width_clearance_mm"] <= 0:
        warnings.append("Receiver width does not exceed male width.")

    if abs(printer.elephant_foot_compensation_mm) > 0.35:
        warnings.append("Elephant-foot compensation is large; verify first-layer cleanup before fit testing.")
    if compensation_invalidates_nominal_compatibility(params):
        warnings.append(
            f"Printer compensation above {MAX_COMPATIBLE_PRINTER_COMPENSATION_MM:g} mm may invalidate nominal compatibility."
        )

    if mount is not None:
        if mount.wearer_facing_clearance_mm < params.minimum_surrounding_wall_mm + params.nominal_interface_depth_mm:
            warnings.append("Receiver cavity may enter a wearer-facing safety zone.")
        else:
            passes.append("Mount keeps connector volume away from the wearer-facing side.")

    if params.nominal_interface_depth_mm < MIN_FDM_FEATURE_MM:
        warnings.append("Interface depth is below minimum practical FDM feature size.")

    return {"warnings": warnings, "info": info, "passes": passes}


def audit_connector_result(*args, **kwargs) -> ConnectorAuditResult:
    audit = audit_connector(*args, **kwargs)
    return ConnectorAuditResult(tuple(audit["warnings"]), tuple(audit["info"]), tuple(audit["passes"]))
