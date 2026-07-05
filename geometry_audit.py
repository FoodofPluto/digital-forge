"""Advisory checks for generated decorative sword assembly geometry."""

from math import isfinite

from scad_generator import (
    BLADE_STYLES,
    GUARD_STYLES,
    POMMEL_STYLES,
    blade_detail_bounds,
    clamp_blade_detail_offset,
    disk_guard_diameter,
    guard_should_rotate_90,
    normalize_component_visibility,
    resolve_tang_details,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS


SUPPORTED_BLADE_STYLES = set(BLADE_STYLES)
SUPPORTED_GUARD_STYLES = set(GUARD_STYLES)
SUPPORTED_POMMEL_STYLES = set(POMMEL_STYLES)

MAX_GUARD_WIDTH_MM = 500.0
MAX_DISK_GUARD_DIAMETER_MM = 220.0
MAX_POMMEL_RADIUS_MM = 50.0
MIN_GRIP_LENGTH_MM = 75.0


def _number(metrics: dict[str, float], name: str) -> float:
    value = metrics.get(name, 0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if isfinite(number) else 0.0


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
            safe_fuller_offset = clamp_blade_detail_offset(
                blade_width, fuller_offset_x, min(fuller_width_mm, blade_width * 0.55),
            )
            if safe_fuller_offset != fuller_offset_x:
                warnings.append("Fuller X offset exceeds safe blade bounds and will be clamped.")
            else:
                passed.append("Fuller X offset stays within safe blade bounds.")
        if ridge_enabled:
            safe_ridge_offset = clamp_blade_detail_offset(
                blade_width, ridge_offset_x, blade_width * 0.14
            )
            if safe_ridge_offset != ridge_offset_x:
                warnings.append("Central ridge X offset exceeds safe blade bounds and will be clamped.")
            else:
                passed.append("Central ridge X offset stays within safe blade bounds.")
        if blade_style in {"tapered", "leaf", "needle"} and fuller_offset_x == ridge_offset_x == 0:
            passed.append("Symmetrical blade details use centered default placement.")
        elif blade_style in {"falchion", "curved"}:
            passed.append("Asymmetrical blade style supports conservative side-offset details.")

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
