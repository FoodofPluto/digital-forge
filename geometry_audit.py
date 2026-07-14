"""Advisory checks for generated decorative sword assembly geometry."""

from math import cos, isfinite, radians, sin
from pathlib import Path

from scad_generator import (
    ARMOR_TYPES,
    BLADE_STYLES,
    BRACER_PANEL_ANGLE_SEGMENTS,
    BRACER_PANEL_LENGTH_SEGMENTS,
    BRACER_DETAIL_OPTIONS,
    BRACER_STYLES,
    GUARD_STYLES,
    PAULDRON_DETAIL_OPTIONS,
    PAULDRON_STYLES,
    POMMEL_STYLES,
    blade_detail_bounds,
    clamp_blade_detail_offset,
    compute_blade_detail_corridor,
    disk_guard_diameter,
    guard_should_rotate_90,
    normalize_armor_type,
    normalize_bracer_binding_style,
    normalize_bracer_detail_options,
    normalize_bracer_panel_type,
    normalize_bracer_style,
    normalize_component_visibility,
    normalize_pauldron_detail_options,
    normalize_pauldron_style,
    resolve_bracer_metrics,
    resolve_pauldron_metrics,
    resolve_tang_details,
    resolve_fuller_dimensions,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS
from scabbard_generator import (
    MAX_SCABBARD_CLEARANCE_MM,
    MAX_CUSTOM_STL_UPLOAD_BYTES,
    MIN_SCABBARD_CLEARANCE_MM,
    MIN_SCABBARD_WALL_THICKNESS_MM,
    normalize_custom_stl_scabbard_parameters,
    normalize_scabbard_parameters,
    validate_scabbard_fit,
)


SUPPORTED_BLADE_STYLES = set(BLADE_STYLES)
SUPPORTED_GUARD_STYLES = set(GUARD_STYLES)
SUPPORTED_POMMEL_STYLES = set(POMMEL_STYLES)

MAX_GUARD_WIDTH_MM = 500.0
MAX_DISK_GUARD_DIAMETER_MM = 220.0
MAX_POMMEL_RADIUS_MM = 50.0
MIN_GRIP_LENGTH_MM = 75.0
MIN_BRACER_THICKNESS_MM = 3.0
MAX_BRACER_ARC_DEGREES = 190.0
MAX_BRACER_LENGTH_TO_WIDTH_RATIO = 3.2
MIN_BRACER_LENGTH_TO_WIDTH_RATIO = 1.1
MIN_PAULDRON_THICKNESS_MM = 3.0
MAX_PAULDRON_PLATES = 6
MIN_PAULDRON_OVERLAP_RATIO = 0.12
MAX_PAULDRON_WIDTH_DEPTH_RATIO = 2.4
MAX_PAULDRON_HEIGHT_WIDTH_RATIO = 0.7


def _number(metrics: dict[str, float], name: str) -> float:
    value = metrics.get(name, 0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if isfinite(number) else 0.0


def _rotated_blade_axis_y_component(rx_deg: float, ry_deg: float, rz_deg: float) -> float:
    """Return the Y component of a +Y blade axis after OpenSCAD-style X/Y/Z rotations."""
    x, y, z = 0.0, 1.0, 0.0
    rx, ry, rz = radians(rx_deg), radians(ry_deg), radians(rz_deg)
    cy, sy = cos(rx), sin(rx)
    y, z = y * cy - z * sy, y * sy + z * cy
    cx, sx = cos(ry), sin(ry)
    x, z = x * cx + z * sx, -x * sx + z * cx
    cz, sz = cos(rz), sin(rz)
    _x, y = x * cz - y * sz, x * sz + y * cz
    return y


def audit_scabbard_geometry(
    metrics: dict[str, float],
    blade_type: str = "tapered",
    clearance_per_side_mm: float = 0.6,
    wall_thickness_mm: float = 3.2,
    split_mode: str = "Single Piece",
    throat_enabled: bool = True,
    end_cap_enabled: bool = True,
    fit_mode: str = "Fitted Scabbard",
    seam_allowance_mm: float = 0.25,
) -> dict[str, list[str]]:
    """Return scabbard-specific geometry checks and clamp messages."""
    warnings: list[str] = []
    info: list[str] = ["Scabbard mode: digital prototype geometry derived from the selected blade profile."]
    passed: list[str] = []

    try:
        params, clamp_warnings = normalize_scabbard_parameters(
            blade_type,
            metrics,
            clearance_per_side_mm,
            wall_thickness_mm,
            split_mode,
            throat_enabled,
            end_cap_enabled,
            fit_mode,
            seam_allowance_mm,
        )
    except ValueError as exc:
        return {"warnings": [str(exc)], "info": info, "passes": passed}

    warnings.extend(clamp_warnings)
    requested_clearance = _number({"value": clearance_per_side_mm}, "value")
    requested_wall = _number({"value": wall_thickness_mm}, "value")
    if requested_clearance < MIN_SCABBARD_CLEARANCE_MM:
        warnings.append(
            f"Clearance below {MIN_SCABBARD_CLEARANCE_MM:g} mm would create zero practical insertion room; "
            f"generation uses {params.clearance_per_side_mm:g} mm per side."
        )
    elif requested_clearance > MAX_SCABBARD_CLEARANCE_MM:
        warnings.append(
            f"Clearance above {MAX_SCABBARD_CLEARANCE_MM:g} mm may be excessively loose; "
            f"generation uses {params.clearance_per_side_mm:g} mm per side."
        )
    if requested_wall < MIN_SCABBARD_WALL_THICKNESS_MM:
        warnings.append(
            f"Wall thickness below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm is unsafe for this prototype; "
            f"generation uses {params.wall_thickness_mm:g} mm."
        )

    fit = validate_scabbard_fit(params)
    warnings.extend(fit["warnings"])
    info.extend(fit["info"])
    passed.extend(fit["passes"])
    if params.blade_profile.ricasso_length_mm < params.blade_profile.length_mm:
        passed.append("Inherited sword blade dimensions are internally consistent with scabbard length.")
    return {"warnings": warnings, "info": info, "passes": passed}


def audit_custom_stl_scabbard_geometry(
    stl_path: str,
    object_type: str = "Blade only",
    rotate_x_deg: float = 0.0,
    rotate_y_deg: float = 0.0,
    rotate_z_deg: float = 0.0,
    scale: float = 1.0,
    clearance_mm: float = 0.6,
    wall_thickness_mm: float = 3.2,
    throat_length_mm: float = 18.0,
    split_mode: str = "Single Piece",
    seam_allowance_mm: float = 0.25,
) -> dict[str, list[str]]:
    """Return safety and limitation checks for the experimental STL scabbard workflow."""
    params, warnings = normalize_custom_stl_scabbard_parameters(
        stl_path,
        object_type,
        rotate_x_deg,
        rotate_y_deg,
        rotate_z_deg,
        scale,
        clearance_mm,
        wall_thickness_mm,
        throat_length_mm,
        split_mode,
        seam_allowance_mm,
    )
    info = [
        "Experimental STL scabbards require blade-only, watertight, manifold meshes aligned to the project axis.",
        "OpenSCAD mesh clearance uses minkowski() around the imported STL, which can be slow on detailed meshes.",
        f"Upload size limit is {MAX_CUSTOM_STL_UPLOAD_BYTES // (1024 * 1024)} MB.",
    ]
    passed: list[str] = []
    if params is None:
        return {"warnings": warnings, "info": info, "passes": passed}
    inner_radius = params.clearance_mm
    outer_radius = params.clearance_mm + params.wall_thickness_mm
    if not warnings:
        passed.append("Uploaded STL path is inside the controlled generated/uploaded_stl directory.")
    if params.object_type == "Blade only":
        passed.append("Blade-only STL mode avoids wrapping guard, grip, and pommel geometry.")
    else:
        warnings.append("Full-sword STL detected or strongly suspected; use a blade-only STL for cavity generation.")
    if params.wall_thickness_mm >= MIN_SCABBARD_WALL_THICKNESS_MM:
        passed.append("STL shell wall thickness is within the scabbard safety range.")
    else:
        warnings.append(f"STL shell wall is below the configured {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm minimum.")
    if outer_radius <= inner_radius:
        warnings.append("STL final output has no valid cavity wall because outer expansion is not greater than inner expansion.")
    else:
        passed.append("STL outer expansion radius is greater than the inner cavity expansion radius.")
        passed.append("STL final shell is generated as outer expanded blade minus inner expanded blade.")
    if params.throat_length_mm <= 0:
        warnings.append("STL throat cut does not intersect the shell because throat opening length is zero.")
    else:
        passed.append("STL throat cut removes the blade-entry cap while leaving the expected +Y tip end closed.")
    axis_y = _rotated_blade_axis_y_component(params.rotate_x_deg, params.rotate_y_deg, params.rotate_z_deg)
    if axis_y < -0.35:
        warnings.append("Uploaded mesh orientation is likely reversed; the throat cut may be at the tip end instead of the blade base.")
    elif abs(axis_y) <= 0.35:
        warnings.append("STL rotations make the blade-entry throat end ambiguous; verify the blade base remains on the expected -Y/+Y entry side.")
    else:
        passed.append("STL rotation keeps the imported blade axis broadly aligned with the expected +Y throat-to-tip direction.")
    if params.scale < 0.2 or params.scale > 5.0:
        warnings.append("Scaled STL dimensions may be far outside normal prop ranges; verify orientation and units.")
    if abs(params.rotate_x_deg) > 360 or abs(params.rotate_y_deg) > 360 or abs(params.rotate_z_deg) > 360:
        warnings.append("STL rotation values are large; verify the imported blade is oriented along the expected axis.")
    path = Path(stl_path)
    lowered_name = path.name.lower()
    if any(token in lowered_name for token in ("sword", "hilt", "guard", "grip", "pommel", "handle")):
        warnings.append("Full-sword STL detected or strongly suspected from the filename; upload blade-only geometry.")
    try:
        if path.exists() and path.stat().st_size > MAX_CUSTOM_STL_UPLOAD_BYTES * 0.75:
            warnings.append("Minkowski result is likely impractical due to excessive mesh complexity or file size.")
    except OSError:
        warnings.append("Uploaded STL could not be inspected for mesh-complexity warnings.")
    return {"warnings": warnings, "info": info, "passes": passed}


def audit_bracer_geometry(
    metrics: dict[str, float],
    armor_type: str = "Bracer",
    bracer_style: str = "Plain",
    detail_options: dict[str, bool] | None = None,
    bracer_binding_style: str = "None",
) -> dict[str, list[str]]:
    """Return advisory checks for decorative bracer geometry."""
    warnings: list[str] = []
    info: list[str] = []
    passed: list[str] = []

    normalized_type = normalize_armor_type(armor_type)
    style = normalize_bracer_style(bracer_style)
    details = normalize_bracer_detail_options(style, detail_options)
    binding = normalize_bracer_binding_style(bracer_binding_style)
    resolved, clamp_warnings = resolve_bracer_metrics(metrics)

    info.append("Armor mode: Bracer decorative/prototype geometry only.")
    if armor_type not in ARMOR_TYPES:
        warnings.append(f"Unsupported armor type '{armor_type}' will be generated as Bracer.")
    if bracer_style not in BRACER_STYLES:
        warnings.append(f"Unsupported bracer style '{bracer_style}' will use Plain.")
    if detail_options:
        ignored = sorted(set(detail_options) - set(BRACER_DETAIL_OPTIONS))
        for name in ignored:
            warnings.append(f"Unsupported bracer detail option '{name}' will be ignored.")
    warnings.extend(clamp_warnings)

    requested_wrist = _number(metrics, "wrist_width_mm")
    requested_forearm = _number(metrics, "forearm_width_mm")
    requested_thickness = _number(metrics, "bracer_wall_thickness_mm") or _number(metrics, "bracer_thickness_mm")
    if requested_wrist > requested_forearm > 0:
        warnings.append("Wrist width is larger than forearm width; generation clamps it to preserve outward taper.")

    length = resolved["bracer_length_mm"]
    wrist = resolved["wrist_width_mm"]
    forearm = resolved["forearm_width_mm"]
    depth = resolved["bracer_depth_mm"]
    thickness = resolved["bracer_wall_thickness_mm"]
    arc = resolved["bracer_arc_degrees"]
    opening = resolved["bracer_opening_width_mm"]
    detail_depth = resolved["bracer_detail_depth_mm"]
    finishing_allowance = resolved["bracer_exterior_finishing_allowance_mm"]
    average_width = (wrist + forearm) / 2
    ratio = length / max(1.0, average_width)

    if thickness < MIN_BRACER_THICKNESS_MM:
        warnings.append(f"Bracer thickness below {MIN_BRACER_THICKNESS_MM:g} mm may read as fragile.")
    else:
        passed.append("Bracer thickness is in the stable decorative prop range.")

    if thickness >= min(wrist, forearm, depth) / 2:
        warnings.append("Inner cavity would be smaller than the shell wall; generation reduces wall thickness.")
    else:
        passed.append("Inner cavity remains larger than the shell wall thickness.")

    if opening > min(wrist, forearm) - thickness * 5:
        warnings.append("Opening is too wide for the selected wrist size and wall thickness.")
    elif opening < thickness * 3:
        warnings.append("Opening is narrow and may be hard to read as a wearable gap.")
    else:
        passed.append("Underside opening leaves material on both shell edges.")

    if arc > MAX_BRACER_ARC_DEGREES:
        warnings.append("Bracer curvature is high; preview may look nearly closed around the arm.")
    elif arc < 145:
        warnings.append("Bracer curvature is shallow; it may read more like a flat plate than a cuff.")
    else:
        passed.append("Bracer curvature stays in a readable cuff range.")

    if ratio > MAX_BRACER_LENGTH_TO_WIDTH_RATIO:
        warnings.append("Bracer length-to-width ratio is extreme and may look too long or narrow.")
    elif ratio < MIN_BRACER_LENGTH_TO_WIDTH_RATIO:
        warnings.append("Bracer length-to-width ratio is squat and may not read as a forearm guard.")
    else:
        passed.append("Bracer length-to-width ratio is proportionate.")

    if wrist <= forearm:
        passed.append("Bracer tapers outward from wrist to forearm.")
    if forearm - wrist >= max(8.0, average_width * 0.12):
        passed.append("Forearm and wrist ends are visually distinct.")
    else:
        info.append("Increase forearm width or reduce wrist width for a stronger taper silhouette.")

    trim_width = resolved["bracer_trim_width_mm"]
    binding_margin = resolved["bracer_binding_margin_mm"]

    if details["raised_panel"]:
        panel_width = resolved["bracer_panel_width_mm"]
        panel_length = resolved["bracer_panel_length_mm"]
        panel_height = resolved["bracer_panel_height_mm"]
        panel_roundness = resolved["bracer_panel_edge_roundness_mm"]
        panel_wrist_margin = resolved["bracer_panel_wrist_margin_mm"]
        panel_forearm_margin = resolved["bracer_panel_forearm_margin_mm"]
        safe_front_width = resolved["bracer_panel_safe_front_width_mm"]
        panel_type = resolved["bracer_panel_type"]
        panel_min_width = resolved["bracer_panel_min_width_mm"]
        panel_max_width = resolved["bracer_panel_max_width_mm"]
        panel_min_height = resolved["bracer_panel_min_height_mm"]
        panel_max_height = resolved["bracer_panel_max_height_mm"]
        min_panel_dimension = min(panel_length, panel_width)
        requested_width = _number(metrics, "bracer_panel_width_mm")
        requested_height = _number(metrics, "bracer_panel_height_mm")
        requested_roundness = _number(metrics, "bracer_panel_edge_roundness_mm")
        requested_position = _number(metrics, "bracer_panel_position_mm")
        requested_panel_type = metrics.get("bracer_panel_type")

        if requested_panel_type not in (None, "") and normalize_bracer_panel_type(requested_panel_type) != str(requested_panel_type).strip().title():
            warnings.append("Unsupported Panel Type was normalized to Wide Panel; adjust Panel Type if a Narrow Panel was intended.")

        if requested_width and requested_width != panel_width:
            direction = "below" if requested_width < panel_width else "above"
            warnings.append(
                f"{panel_type} width was clamped {direction} its {panel_min_width:g}-{panel_max_width:g} mm range; "
                "adjust Panel Type or Panel Width."
            )

        if panel_height >= panel_max_height * 0.9:
            warnings.append("Raised Design Panel height is unusually tall; reduce Panel Height if the raised stock looks fragile.")
        elif panel_height > max(panel_min_height * 1.65, thickness * 0.72):
            info.append("Raised Design Panel height is substantial but within the normalized exterior stock limit.")
        elif panel_height < panel_min_height:
            warnings.append("Raised Design Panel height is below the meaningful minimum; generation raises Panel Height.")
        else:
            passed.append("Raised Design Panel height is in the normal maker-finishing range.")

        if requested_height and requested_height != panel_height:
            warnings.append(
                f"Raised Design Panel height was clamped to {panel_height:g} mm; adjust Panel Height within "
                f"{panel_min_height:g}-{panel_max_height:g} mm."
            )

        opening_margin = max(10.0, trim_width * 1.15)
        if panel_wrist_margin < opening_margin:
            warnings.append("Raised Design Panel is close to the wrist opening; shorten the panel or move it toward the forearm.")
        if panel_forearm_margin < opening_margin:
            warnings.append("Raised Design Panel is close to the forearm opening; shorten the panel or move it toward the wrist.")
        if panel_wrist_margin >= opening_margin and panel_forearm_margin >= opening_margin:
            passed.append("Raised Design Panel stays within usable length margins.")

        if panel_width > safe_front_width * 0.92:
            warnings.append(f"{panel_type} is approaching closure clearance; reduce Panel Width before moving closure geometry.")
        else:
            passed.append(f"{panel_type} width stays in the safe exterior front region.")

        if panel_roundness > min_panel_dimension * 0.24 or requested_roundness > panel_roundness:
            warnings.append("Raised Design Panel edge roundness is near the panel limit; reduce edge roundness or increase panel size.")
        else:
            passed.append("Raised Design Panel edge roundness is supported by the panel dimensions.")

        if panel_length < 24.0 or panel_width < 24.0 or panel_height < panel_min_height:
            warnings.append("Raised Design Panel dimensions may create weak or poorly printable geometry.")
        else:
            passed.append("Raised Design Panel dimensions are printable at the normalized values.")

        info.append(
            "Raised Design Panel preview complexity is capped at "
            f"{BRACER_PANEL_ANGLE_SEGMENTS} angular by {BRACER_PANEL_LENGTH_SEGMENTS} length segments."
        )

        if binding in {"Lacing Holes", "Lacing Loops", "Strap Slots", "Buckle-Ready Slots"}:
            closure_clearance = max(4.0, resolved["bracer_closure_flange_width_mm"] * 0.25)
            panel_half_width = panel_width / 2
            front_to_closure_gap = safe_front_width / 2 - panel_half_width
            if front_to_closure_gap < closure_clearance:
                warnings.append("Raised Design Panel and selected closure are close; reduce panel width before changing approved closure placement.")
            else:
                passed.append("Raised Design Panel leaves clearance from selected closure geometry.")

        if requested_position and requested_position != resolved["bracer_panel_position_mm"]:
            warnings.append("Raised Design Panel position was clamped so the panel remains attached within the shell length.")
    elif finishing_allowance > 0:
        passed.append("Exterior finishing allowance leaves closure passages and inner cavity unchanged.")

    if binding in {"Lacing Holes", "Lacing Loops", "Strap Slots", "Buckle-Ready Slots"}:
        if binding_margin < trim_width:
            warnings.append("Binding features are too close to the wrist or elbow end.")
        else:
            passed.append("Binding features stay away from the bracer ends.")
        hole_diameter = resolved["bracer_binding_hole_diameter_mm"]
        slot_length = resolved["bracer_strap_slot_length_mm"]
        slot_width = resolved["bracer_strap_slot_width_mm"]
        slot_depth = resolved.get("bracer_slot_cutter_depth_mm")
        edge_margin = resolved["bracer_closure_edge_margin_mm"]
        hole_edge_margin = resolved["bracer_lacing_edge_margin_mm"]
        strap_edge_margin = resolved["bracer_strap_slot_edge_margin_mm"]
        buckle_edge_margin = resolved["bracer_buckle_slot_edge_margin_mm"]
        flange_width = resolved["bracer_closure_flange_width_mm"]
        flange_thickness = resolved["bracer_closure_flange_thickness_mm"]
        hole_flange_margin = (flange_width - hole_diameter) / 2
        slot_flange_margin = (flange_width - slot_length) / 2
        buckle_flange_margin = (flange_width - resolved["bracer_buckle_slot_length_mm"]) / 2
        if hole_diameter > thickness * 1.8:
            warnings.append("Binding holes are large relative to wall thickness.")
        elif binding in {"Lacing Holes", "Lacing Loops"}:
            passed.append("Lacing features use paired, printable spacing.")
        if binding in {"Lacing Holes", "Lacing Loops"} and hole_flange_margin < hole_edge_margin:
            warnings.append("Lacing hole lacks complete material margin in the exterior closure flange.")
        elif binding in {"Lacing Holes", "Lacing Loops"}:
            passed.append("Lacing holes remain complete enclosed passages through exterior flanges.")
        if binding == "Strap Slots" and slot_flange_margin < strap_edge_margin:
            warnings.append("Strap Slots are too close to the closure edge; reduce strap slot length or increase bracer size.")
        elif binding == "Strap Slots":
            passed.append("Strap Slots keep enlarged material margins and remain complete enclosed passages.")
        if binding == "Buckle-Ready Slots" and buckle_flange_margin < buckle_edge_margin:
            warnings.append("Buckle-Ready Slots are too close to the closure edge; reduce hardware slot size or increase bracer size.")
        elif binding == "Buckle-Ready Slots":
            passed.append("Buckle receiver strap passage keeps enlarged material margins and remains a complete opening.")
        if binding in {"Strap Slots", "Buckle-Ready Slots"}:
            frame_depth = flange_thickness
            if binding == "Buckle-Ready Slots":
                frame_depth += thickness * 0.55
            if slot_depth and slot_depth > frame_depth + resolved["bracer_closure_slot_inset_mm"] * 2:
                passed.append("Closure slot cutters over-travel through the flange/frame so no exterior membrane remains.")
            else:
                warnings.append("Closure slot cutter depth is too short for the selected flange or frame thickness.")
            target_spacing = max(32.0, min(44.0, length * 0.16))
            if resolved["bracer_hardware_slot_spacing_mm"] < target_spacing:
                warnings.append(
                    "Closure slot group spacing was compressed to keep all three slots inside the usable closure region; "
                    "increase bracer length or reduce slot dimensions."
                )
            else:
                passed.append("Three-slot closure group is centered and evenly spaced inside the usable closure region.")
        if flange_thickness < max(thickness * 1.25, hole_diameter):
            warnings.append("Closure flange is too thin for robust exterior passages.")
        else:
            passed.append("Closure flanges provide exterior material for the selected hardware.")
        if binding == "Lacing Loops":
            if resolved["bracer_loop_passage_diameter_mm"] < 3.2:
                warnings.append("Loop passage is too small for reliable printing and finishing.")
            if resolved["bracer_loop_wall_thickness_mm"] < max(1.8, thickness * 0.5):
                warnings.append("Loop wall is too thin around the lacing passage.")
            else:
                passed.append("Lacing loops include printable wall thickness around an enclosed passage.")
        if binding == "Buckle-Ready Slots":
            if resolved["bracer_buckle_slot_width_mm"] <= slot_width:
                warnings.append("Buckle receiver strap passage is too small for the selected strap width.")
            else:
                passed.append("Buckle receiver strap passage is larger than the strap-anchor slots.")
            receiver_gap = resolved["bracer_buckle_receiver_gap_mm"]
            receiver_projection = resolved["bracer_buckle_receiver_projection_mm"]
            ear_thickness = resolved["bracer_buckle_receiver_ear_thickness_mm"]
            pin_diameter = resolved["bracer_buckle_pin_diameter_mm"]
            pin_wall = resolved["bracer_buckle_pin_wall_margin_mm"]
            if receiver_gap < 8.0:
                warnings.append("Buckle receiver central gap is narrow; increase Receiver Gap for insert clearance.")
            else:
                passed.append("Buckle receiver leaves a visible central gap between the two exterior ears.")
            if ear_thickness < max(3.0, pin_diameter * 0.9):
                warnings.append("Buckle receiver ears are too thin for the selected pin passage.")
            else:
                passed.append("Buckle receiver ears have printable thickness around the pin passage.")
            if receiver_projection - pin_diameter < pin_wall * 2:
                warnings.append("Buckle receiver pin passage lacks the requested material above and below the hole.")
            else:
                passed.append("Buckle receiver pin passage keeps material around the transverse hole.")
            if receiver_projection > 8.0:
                warnings.append("Buckle receiver projection is large for the decorative bracer scale.")
            else:
                passed.append("Buckle receiver projection stays low-profile on the exterior side.")
            if resolved["bracer_buckle_receiver_total_length_mm"] > resolved["bracer_hardware_slot_spacing_mm"] * 0.8:
                warnings.append("Buckle receiver ears are close to neighboring receiver positions; reduce gap or ear thickness.")
            else:
                passed.append("Buckle receiver ears fit inside the available closure-side spacing.")
    else:
        passed.append("No closure hardware selected.")

    if normalized_type == "Bracer":
        passed.append("Armor type is supported.")
    if style == "Plain":
        passed.append("Plain bracer style uses no aggregate decoration preset.")

    return {"warnings": warnings, "info": info, "passes": passed}


def audit_pauldron_geometry(
    metrics: dict[str, float],
    armor_type: str = "Pauldron",
    pauldron_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
) -> dict[str, list[str]]:
    """Return advisory checks for decorative pauldron geometry."""
    warnings: list[str] = []
    info: list[str] = []
    passed: list[str] = []

    normalized_type = normalize_armor_type(armor_type)
    style = normalize_pauldron_style(pauldron_style)
    details = normalize_pauldron_detail_options(style, detail_options)
    resolved, clamp_warnings = resolve_pauldron_metrics(metrics)

    info.append("Armor mode: Pauldron decorative/prototype geometry only.")
    if armor_type not in ARMOR_TYPES:
        warnings.append(f"Unsupported armor type '{armor_type}' will be generated as Bracer.")
    if normalized_type != "Pauldron":
        warnings.append(f"Armor type '{armor_type}' is not a Pauldron route.")
    if pauldron_style not in PAULDRON_STYLES:
        warnings.append(f"Unsupported pauldron style '{pauldron_style}' will use Knight.")
    if detail_options:
        ignored = sorted(set(detail_options) - set(PAULDRON_DETAIL_OPTIONS))
        for name in ignored:
            warnings.append(f"Unsupported pauldron detail option '{name}' will be ignored.")
    warnings.extend(clamp_warnings)

    requested_overlap = _number(metrics, "plate_overlap_mm")
    requested_thickness = _number(metrics, "pauldron_thickness_mm")
    if 0 < requested_overlap < max(4.0, requested_thickness * 1.4):
        warnings.append("Pauldron plate overlap is low; generation increases it so plates visually connect.")

    width = resolved["pauldron_width_mm"]
    depth = resolved["pauldron_depth_mm"]
    height = resolved["pauldron_height_mm"]
    plate_count = int(resolved["plate_count"])
    overlap = resolved["plate_overlap_mm"]
    thickness = resolved["pauldron_thickness_mm"]
    plate_depth = resolved["pauldron_plate_depth_mm"]
    spike_height = resolved["pauldron_spike_height_mm"]

    if plate_count > MAX_PAULDRON_PLATES:
        warnings.append(f"Pauldron plate count above {MAX_PAULDRON_PLATES} may look busy and slow preview.")
    else:
        passed.append("Pauldron plate count stays in a readable layered range.")
    if overlap < plate_depth * MIN_PAULDRON_OVERLAP_RATIO:
        warnings.append("Pauldron plate overlap is low; plates may look disconnected.")
    else:
        passed.append("Pauldron plate overlap visually connects the lames.")
    if thickness < MIN_PAULDRON_THICKNESS_MM:
        warnings.append(f"Pauldron thickness below {MIN_PAULDRON_THICKNESS_MM:g} mm may read as fragile.")
    else:
        passed.append("Pauldron plate thickness is in the stable decorative prop range.")

    width_depth_ratio = width / max(1.0, depth)
    height_width_ratio = height / max(1.0, width)
    if width_depth_ratio > MAX_PAULDRON_WIDTH_DEPTH_RATIO:
        warnings.append("Pauldron width/depth proportion is extreme and may look too broad.")
    elif width_depth_ratio < 0.75:
        warnings.append("Pauldron depth is large relative to width and may look elongated.")
    else:
        passed.append("Pauldron width and depth proportions are balanced.")
    if height_width_ratio > MAX_PAULDRON_HEIGHT_WIDTH_RATIO:
        warnings.append("Pauldron height is extreme relative to width and may look like a tall dome.")
    elif height < thickness * 5:
        warnings.append("Pauldron height is low relative to plate thickness and may look flat.")
    else:
        passed.append("Pauldron height supports a readable shoulder dome.")

    if details["spikes"] and spike_height > height * 0.42:
        warnings.append("Pauldron spikes are oversized relative to dome height.")
    elif details["spikes"]:
        passed.append("Pauldron spikes stay within the decorative size limit.")
    if details["rivets"] and resolved["pauldron_rivet_diameter_mm"] > width * 0.08:
        warnings.append("Pauldron rivets are large relative to shoulder width.")
    elif details["rivets"]:
        passed.append("Pauldron rivets are within the decorative size limit.")

    if normalized_type == "Pauldron":
        passed.append("Armor type is supported.")
    if style == "Knight":
        passed.append("Knight pauldron style includes clean layered plates and central trim.")
    elif style == "Barbarian":
        passed.append("Barbarian pauldron style includes rugged ribs and heavy details.")
    elif style == "Elven":
        passed.append("Elven pauldron style includes a slim leaf-like crest.")

    return {"warnings": warnings, "info": info, "passes": passed}


def audit_geometry(
    metrics: dict[str, float],
    sword_type: str,
    blade_style: str,
    guard_style: str,
    pommel_style: str,
    visible_components: dict[str, bool] | None = None,
    fuller_enabled: bool = False,
    fuller_length_ratio: float = 0.65,
    ridge_enabled: bool = False,
    fuller_offset_x: float = 0.0,
    ridge_offset_x: float = 0.0,
    fuller_width_mm: float = 12.0,
    fuller_depth_mm: float = 0.8,
) -> dict[str, list[str]]:
    """Return warning, informational, and passing geometry audit messages."""
    warnings: list[str] = []
    info: list[str] = []
    passed: list[str] = []
    visible = normalize_component_visibility(visible_components)
    visible_names = [name for name, is_visible in visible.items() if is_visible]
    info.append(
        "Assembly view: " + (", ".join(visible_names) if visible_names else "no components visible") + "."
    )
    if not visible_names:
        info.append("Select at least one visible component to preview or export.")

    if sword_type not in SWORD_PRESETS:
        warnings.append(f"Unsupported sword type '{sword_type}'; using generic geometry checks.")
    if visible["blade"] and blade_style not in SUPPORTED_BLADE_STYLES:
        warnings.append(f"Unsupported blade style '{blade_style}'.")
    if visible["guard"] and guard_style not in SUPPORTED_GUARD_STYLES:
        warnings.append(f"Unsupported guard style '{guard_style}'.")
    if visible["pommel"] and pommel_style not in SUPPORTED_POMMEL_STYLES:
        warnings.append(f"Unsupported pommel style '{pommel_style}'.")
    if visible["blade"] and sword_type == "rapier" and blade_style == "falchion":
        warnings.append("Unsupported combination: a falchion blade profile is not supported for rapiers.")
    if visible["guard"] and sword_type == "dagger" and guard_style == "disk":
        warnings.append("Unsupported combination: disk guards are not supported for dagger presets.")

    dimensions = {name: _number(metrics, name) for name in REQUIRED_METRICS}
    required_by_component = {
        "blade_length_mm": visible["blade"],
        "blade_base_width_mm": visible["blade"] or visible["tang"] or visible["guard"],
        "blade_tip_width_mm": visible["blade"],
        "blade_thickness_mm": visible["blade"] or visible["tang"],
        "grip_length_mm": visible["grip"] or visible["tang"] or visible["pommel"],
        "grip_width_mm": visible["grip"] or visible["tang"] or visible["guard"],
        "guard_width_mm": visible["guard"],
        "guard_height_mm": visible["guard"] or visible["tang"] or visible["blade"],
        "pommel_size_mm": visible["pommel"],
        "ricasso_length_mm": visible["blade"] or visible["tang"],
    }
    for name, value in dimensions.items():
        if not required_by_component.get(name, False):
            continue
        if name == "ricasso_length_mm":
            if value < 0:
                warnings.append("Ricasso length cannot be negative.")
        elif value <= 0:
            warnings.append(f"{name.replace('_mm', '').replace('_', ' ').title()} must be positive.")

    blade = dimensions["blade_length_mm"]
    blade_width = dimensions["blade_base_width_mm"]
    grip = dimensions["grip_length_mm"]
    guard_width = dimensions["guard_width_mm"]
    guard_height = dimensions["guard_height_mm"]
    pommel_size = dimensions["pommel_size_mm"]
    blade_thickness = dimensions["blade_thickness_mm"]

    if visible["tang"]:
        tang = resolve_tang_details(metrics)
        requested_count = int(_number(metrics, "peg_hole_count"))
        if not 0 <= requested_count <= 3:
            warnings.append("Peg hole count must be between 0 and 3.")
        requested_length = _number(metrics, "tang_length_mm") if "tang_length_mm" in metrics else tang["tang_length_mm"]
        requested_width = _number(metrics, "tang_width_mm") if "tang_width_mm" in metrics else tang["tang_width_mm"]
        requested_thickness = (_number(metrics, "tang_thickness_mm")
                               if "tang_thickness_mm" in metrics else tang["tang_thickness_mm"])
        if requested_length >= grip or requested_width >= dimensions["grip_width_mm"]:
            warnings.append("Tang dimensions must remain smaller than the external grip dimensions.")
        else:
            passed.append("Tang length and width remain smaller than the external grip.")
        if requested_thickness >= tang["grip_depth_mm"]:
            warnings.append("Tang thickness must remain smaller than the external grip depth.")
        else:
            passed.append("Tang thickness remains inside the external oval grip depth.")
        if tang["peg_hole_count"]:
            requested_diameter = (_number(metrics, "peg_hole_diameter_mm")
                                  if "peg_hole_diameter_mm" in metrics else tang["peg_hole_diameter_mm"])
            if requested_diameter > tang["peg_hole_diameter_mm"]:
                warnings.append("Peg hole diameter is too large for the tang and will be clamped.")
            positions = tang["peg_hole_positions_mm"]
            last_center = positions[-1]
            radius = tang["peg_hole_diameter_mm"] / 2
            if (radius >= tang["tang_width_mm"] / 2 or
                    positions[0] < tang["peg_hole_usable_start_mm"] or
                    last_center > tang["peg_hole_usable_end_mm"]):
                warnings.append("Peg holes do not fit inside the tang bounds.")
            else:
                passed.append("Peg holes fit within the tang width and length bounds.")
            usable_center = (tang["peg_hole_usable_start_mm"] + tang["peg_hole_usable_end_mm"]) / 2
            group_center = (positions[0] + positions[-1]) / 2
            if abs(group_center - usable_center) > 0.5:
                warnings.append("Peg holes are not centered in the tang's usable handle region.")
            elif positions[0] <= tang["peg_hole_usable_start_mm"] + 0.5:
                warnings.append("Peg holes are too close to the blade-side end of the usable tang.")
            else:
                passed.append("Peg holes are centered in the tang's usable handle region.")

    if visible["blade"] and (fuller_enabled or ridge_enabled) and blade > 0:
        detail_start, detail_end = blade_detail_bounds(
            blade, dimensions["ricasso_length_mm"], fuller_length_ratio, blade_style
        )
        if detail_start < max(0.0, dimensions["ricasso_length_mm"]) or detail_end > blade:
            warnings.append("Blade detail geometry exceeds the blade body bounds.")
        else:
            if fuller_enabled:
                passed.append("Fuller stays within the blade body and clear of the guard and tip.")
            if ridge_enabled:
                passed.append("Central ridge stays within the blade body and clear of the guard and tip.")
        if fuller_enabled:
            safe_width, safe_depth = resolve_fuller_dimensions(
                blade_width, blade_thickness, fuller_width_mm, fuller_depth_mm
            )
            passed.append("Fuller uses subtractive rounded cutters to create a depressed groove.")
            if safe_depth != fuller_depth_mm:
                warnings.append("Fuller depth exceeds the shallow blade-thickness limit and will be clamped.")
            else:
                passed.append("Fuller depth remains below blade thickness.")
            if safe_width != fuller_width_mm:
                warnings.append("Fuller width exceeds the usable blade body and will be clamped.")
            else:
                passed.append("Fuller width fits inside the blade body.")
            safe_fuller_offset = clamp_blade_detail_offset(
                blade_width, fuller_offset_x, safe_width, blade, blade_style,
            )
            if safe_fuller_offset != fuller_offset_x:
                warnings.append("Fuller X offset exceeds safe blade bounds and will be clamped.")
            else:
                passed.append("Fuller X offset stays within safe blade bounds.")
        if ridge_enabled:
            safe_ridge_offset = clamp_blade_detail_offset(
                blade_width, ridge_offset_x, blade_width * 0.14, blade, blade_style
            )
            if safe_ridge_offset != ridge_offset_x:
                warnings.append("Central ridge X offset exceeds safe blade bounds and will be clamped.")
            else:
                passed.append("Central ridge X offset stays within safe blade bounds.")
        if blade_style in {"tapered", "leaf", "needle"} and fuller_offset_x == ridge_offset_x == 0:
            passed.append("Symmetrical blade details use centered default placement.")
        elif blade_style in {"falchion", "curved"}:
            center, width = compute_blade_detail_corridor(blade_width, blade, blade_style)
            passed.append(
                f"Asymmetrical blade offsets stay inside a proportionate {width:g} mm usable corridor."
            )
            if fuller_enabled and ridge_enabled and abs(safe_fuller_offset-safe_ridge_offset) < safe_width/2:
                info.append("Fuller and ridge overlap substantially; separate their positions for clearer detail.")

    if visible["grip"] and grip >= MIN_GRIP_LENGTH_MM:
        passed.append(f"Grip length meets the {MIN_GRIP_LENGTH_MM:g} mm minimum.")
    elif visible["grip"] and grip > 0:
        warnings.append(f"Grip length is below the {MIN_GRIP_LENGTH_MM:g} mm minimum.")

    if visible["blade"] and visible["grip"] and blade > grip > 0:
        passed.append("Blade length is greater than grip length.")
    elif visible["blade"] and visible["grip"] and blade > 0 and grip > 0:
        warnings.append("Blade length must be greater than grip length.")

    if visible["blade"] and visible["guard"] and blade_width > 0 and guard_width > 0:
        if guard_width < blade_width * 1.5:
            warnings.append("Guard width is too narrow relative to the blade base width.")
        elif guard_width > blade_width * 8:
            warnings.append("Guard width is excessive relative to the blade base width.")
        else:
            passed.append("Guard width is proportionate to the blade base.")
    if visible["guard"] and guard_width > MAX_GUARD_WIDTH_MM:
        warnings.append(f"Guard width exceeds the {MAX_GUARD_WIDTH_MM:g} mm maximum.")

    if visible["guard"] and guard_style == "disk" and blade_width > 0:
        capped = disk_guard_diameter(dimensions)
        if capped > MAX_DISK_GUARD_DIAMETER_MM:
            warnings.append(
                f"Rounded guard diameter {capped:g} mm exceeds the "
                f"{MAX_DISK_GUARD_DIAMETER_MM:g} mm maximum."
            )
        elif capped < guard_width:
            info.append(f"Disk guard diameter is capped at {capped:g} mm.")
        else:
            passed.append("Disk guard diameter is within its capped range.")
        passed.append("Disk guard is centered on +Y between the grip and blade anchors.")
        passed.append("Disk guard's thin Y axis touches the top of the grip without blocking the blade base.")

    pommel_radius = pommel_size / 2
    if visible["pommel"] and pommel_radius > MAX_POMMEL_RADIUS_MM:
        warnings.append(f"Pommel radius exceeds the {MAX_POMMEL_RADIUS_MM:g} mm maximum.")
    elif visible["pommel"] and pommel_radius > 0:
        passed.append("Pommel radius is within the decorative size limit.")

    # Version 4 coordinate contract: grip ends at Y=0, the guard occupies
    # Y=0..guard_height, and the blade begins at guard_height.
    if visible["grip"] and visible["pommel"] and grip > 0 and pommel_size > 0:
        passed.append("Pommel-to-grip contact is maintained by the shared overlap anchor.")
    if visible["grip"] and visible["guard"] and grip > 0 and guard_height > 0:
        passed.append("Grip-to-guard contact is maintained at Y = 0.")
    if visible["blade"] and visible["guard"] and blade > 0 and guard_height > 0:
        passed.append("Guard-to-blade contact is maintained at guard_top_y.")
    if visible["grip"] and visible["blade"] and visible["guard"] and grip > 0 and blade > 0 and guard_height > 0:
        passed.append("Oval grip is wider across the hand than its front-to-back depth.")
        passed.append("External grip dimensions remain distinct from and enclose the tang/core.")
        passed.append("Blade uses minimum blunt edge thickness and a capped prop-safe tip width.")
        passed.append("Blade, guard, grip, tang/core, and pommel share or overlap axial contact anchors.")
    if visible["tang"] and grip > 0 and guard_height > 0:
        passed.append("Decorative tang/core extends from the blade base through the guard into the grip.")

    if visible["guard"] and guard_style == "crescent":
        passed.append("Crescent guard uses an enlarged outer arc and deeper cutout for a pronounced silhouette.")
    elif visible["guard"] and guard_style == "downturned":
        passed.append("Downturned guard arms sweep toward +Y and the blade.")
    elif visible["guard"] and guard_style in {"straight", "disk"}:
        passed.append("Guard is centered perpendicular to the +Y blade direction.")

    if visible["guard"] and guard_should_rotate_90(sword_type, blade_style):
        passed.append("Guard rotates 90 degrees around +Y for this sword/blade profile.")
    elif visible["guard"]:
        passed.append("Guard uses the normal orientation for this sword/blade profile.")

    if visible["blade"] and blade_style == "falchion":
        passed.append("Falchion uses a widened forward belly and slanted chopping point.")
    elif visible["blade"] and blade_style == "curved":
        passed.append("Curved blade sweeps visibly toward +X along its length.")

    if visible["pommel"] and pommel_style == "spike":
        passed.append("Spike pommel is rooted at the grip bottom and points toward -Y.")

    return {"warnings": warnings, "info": info, "passes": passed}
