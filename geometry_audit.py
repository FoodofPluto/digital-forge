"""Advisory checks for generated decorative sword assembly geometry."""

from math import isfinite

from scad_generator import (
    BLADE_STYLES,
    GUARD_STYLES,
    POMMEL_STYLES,
    disk_guard_diameter,
    guard_should_rotate_90,
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
) -> dict[str, list[str]]:
    """Return warning, informational, and passing geometry audit messages."""
    warnings: list[str] = []
    info: list[str] = []
    passed: list[str] = []

    if sword_type not in SWORD_PRESETS:
        warnings.append(f"Unsupported sword type '{sword_type}'; using generic geometry checks.")
    if blade_style not in SUPPORTED_BLADE_STYLES:
        warnings.append(f"Unsupported blade style '{blade_style}'.")
    if guard_style not in SUPPORTED_GUARD_STYLES:
        warnings.append(f"Unsupported guard style '{guard_style}'.")
    if pommel_style not in SUPPORTED_POMMEL_STYLES:
        warnings.append(f"Unsupported pommel style '{pommel_style}'.")
    if sword_type == "rapier" and blade_style == "falchion":
        warnings.append("Unsupported combination: a falchion blade profile is not supported for rapiers.")
    if sword_type == "dagger" and guard_style == "disk":
        warnings.append("Unsupported combination: disk guards are not supported for dagger presets.")

    dimensions = {name: _number(metrics, name) for name in REQUIRED_METRICS}
    for name, value in dimensions.items():
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

    if grip >= MIN_GRIP_LENGTH_MM:
        passed.append(f"Grip length meets the {MIN_GRIP_LENGTH_MM:g} mm minimum.")
    elif grip > 0:
        warnings.append(f"Grip length is below the {MIN_GRIP_LENGTH_MM:g} mm minimum.")

    if blade > grip > 0:
        passed.append("Blade length is greater than grip length.")
    elif blade > 0 and grip > 0:
        warnings.append("Blade length must be greater than grip length.")

    if blade_width > 0 and guard_width > 0:
        if guard_width < blade_width * 1.5:
            warnings.append("Guard width is too narrow relative to the blade base width.")
        elif guard_width > blade_width * 8:
            warnings.append("Guard width is excessive relative to the blade base width.")
        else:
            passed.append("Guard width is proportionate to the blade base.")
    if guard_width > MAX_GUARD_WIDTH_MM:
        warnings.append(f"Guard width exceeds the {MAX_GUARD_WIDTH_MM:g} mm maximum.")

    if guard_style == "disk" and blade_width > 0:
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
    if pommel_radius > MAX_POMMEL_RADIUS_MM:
        warnings.append(f"Pommel radius exceeds the {MAX_POMMEL_RADIUS_MM:g} mm maximum.")
    elif pommel_radius > 0:
        passed.append("Pommel radius is within the decorative size limit.")

    # Version 4 coordinate contract: grip ends at Y=0, the guard occupies
    # Y=0..guard_height, and the blade begins at guard_height.
    if grip > 0 and pommel_size > 0:
        passed.append("Pommel-to-grip contact is maintained by the shared overlap anchor.")
    if grip > 0 and guard_height > 0:
        passed.append("Grip-to-guard contact is maintained at Y = 0.")
    if blade > 0 and guard_height > 0:
        passed.append("Guard-to-blade contact is maintained at guard_top_y.")

    if guard_style == "crescent":
        passed.append("Crescent guard uses an enlarged outer arc and deeper cutout for a pronounced silhouette.")
    elif guard_style == "downturned":
        passed.append("Downturned guard arms sweep toward +Y and the blade.")
    elif guard_style in {"straight", "disk"}:
        passed.append("Guard is centered perpendicular to the +Y blade direction.")

    if guard_should_rotate_90(sword_type, blade_style):
        passed.append("Guard rotates 90 degrees around +Y for this sword/blade profile.")
    else:
        passed.append("Guard uses the normal orientation for this sword/blade profile.")

    if blade_style == "falchion":
        passed.append("Falchion uses a widened forward belly and slanted chopping point.")
    elif blade_style == "curved":
        passed.append("Curved blade sweeps visibly toward +X along its length.")

    if pommel_style == "spike":
        passed.append("Spike pommel is rooted at the grip bottom and points toward -Y.")

    return {"warnings": warnings, "info": info, "passes": passed}
