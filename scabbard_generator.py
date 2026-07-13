"""Parametric scabbard generation for straight Digital Forge blade profiles."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from scad_generator import clamp


SUPPORTED_SCABBARD_BLADE_STYLES = ("tapered", "leaf")
SCABBARD_BLADE_LABELS = {
    "Symmetrical Tapered": "tapered",
    "Tapered": "tapered",
    "tapered": "tapered",
    "Leaf": "leaf",
    "leaf": "leaf",
}
SCABBARD_SPLIT_MODES = ("Single Piece", "Two Piece")
MIN_SCABBARD_CLEARANCE_MM = 0.35
DEFAULT_SCABBARD_CLEARANCE_MM = 0.6
MAX_SCABBARD_CLEARANCE_MM = 3.0
MIN_SCABBARD_WALL_THICKNESS_MM = 2.4
DEFAULT_SCABBARD_WALL_THICKNESS_MM = 3.2
MAX_SCABBARD_WALL_THICKNESS_MM = 12.0
MIN_PROP_TIP_WIDTH_MM = 3.0
MIN_PROP_BLADE_THICKNESS_MM = 2.4
DEFAULT_THROAT_LENGTH_MM = 18.0
DEFAULT_THROAT_REINFORCEMENT_MM = 1.2
DEFAULT_TIP_CLEARANCE_MM = 4.0
EPSILON_MM = 0.05


@dataclass(frozen=True)
class ScabbardBladeProfile:
    """Blade dimensions inherited from the normalized sword generation path."""

    blade_type: str
    length_mm: float
    base_width_mm: float
    tip_width_mm: float
    thickness_mm: float
    ricasso_length_mm: float
    prop_tip_width_mm: float
    prop_blade_thickness_mm: float


@dataclass(frozen=True)
class ScabbardParameters:
    blade_profile: ScabbardBladeProfile
    clearance_per_side_mm: float
    wall_thickness_mm: float
    split_mode: str
    throat_enabled: bool
    end_cap_enabled: bool
    throat_length_mm: float = DEFAULT_THROAT_LENGTH_MM
    throat_reinforcement_mm: float = DEFAULT_THROAT_REINFORCEMENT_MM
    tip_clearance_mm: float = DEFAULT_TIP_CLEARANCE_MM

    @property
    def cavity_half_thickness_mm(self) -> float:
        return self.blade_profile.prop_blade_thickness_mm / 2 + self.clearance_per_side_mm

    @property
    def outer_half_thickness_mm(self) -> float:
        return self.cavity_half_thickness_mm + self.wall_thickness_mm

    @property
    def cavity_end_y_mm(self) -> float:
        return self.blade_profile.length_mm + self.tip_clearance_mm

    @property
    def outer_end_y_mm(self) -> float:
        cap_wall = self.wall_thickness_mm if self.end_cap_enabled else 0.0
        return self.cavity_end_y_mm + cap_wall

    @property
    def throat_start_y_mm(self) -> float:
        return -self.throat_length_mm if self.throat_enabled else 0.0


def _finite_float(value: object, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if isfinite(number) else fallback


def normalize_scabbard_blade_type(blade_type: str | None) -> str:
    """Return the internal supported blade style or raise a clear validation error."""
    value = str(blade_type or "").strip()
    normalized = SCABBARD_BLADE_LABELS.get(value) or SCABBARD_BLADE_LABELS.get(value.title())
    if normalized not in SUPPORTED_SCABBARD_BLADE_STYLES:
        supported = ", ".join(("Symmetrical Tapered", "Leaf"))
        raise ValueError(f"Unsupported scabbard blade type '{blade_type}'. Supported scabbards: {supported}.")
    return normalized


def inherit_blade_profile(blade_type: str, sword_metrics: dict[str, float]) -> ScabbardBladeProfile:
    """Inherit the same blade dimensions and prop clamps used by sword generation."""
    style = normalize_scabbard_blade_type(blade_type)
    length = max(1.0, _finite_float(sword_metrics.get("blade_length_mm"), 1.0))
    base_width = max(1.0, _finite_float(sword_metrics.get("blade_base_width_mm"), 1.0))
    tip_width = max(0.0, _finite_float(sword_metrics.get("blade_tip_width_mm"), 0.0))
    thickness = max(1.0, _finite_float(sword_metrics.get("blade_thickness_mm"), 1.0))
    ricasso = max(0.0, _finite_float(sword_metrics.get("ricasso_length_mm"), 0.0))
    return ScabbardBladeProfile(
        blade_type=style,
        length_mm=length,
        base_width_mm=base_width,
        tip_width_mm=tip_width,
        thickness_mm=thickness,
        ricasso_length_mm=ricasso,
        prop_tip_width_mm=max(tip_width, MIN_PROP_TIP_WIDTH_MM),
        prop_blade_thickness_mm=max(thickness, MIN_PROP_BLADE_THICKNESS_MM),
    )


def normalize_scabbard_parameters(
    blade_type: str,
    sword_metrics: dict[str, float],
    clearance_per_side_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM,
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    split_mode: str = "Single Piece",
    throat_enabled: bool = True,
    end_cap_enabled: bool = True,
) -> tuple[ScabbardParameters, list[str]]:
    """Return normalized scabbard parameters and non-fatal clamp messages."""
    warnings: list[str] = []
    profile = inherit_blade_profile(blade_type, sword_metrics)
    requested_clearance = _finite_float(clearance_per_side_mm, DEFAULT_SCABBARD_CLEARANCE_MM)
    clearance = clamp(requested_clearance, MIN_SCABBARD_CLEARANCE_MM, MAX_SCABBARD_CLEARANCE_MM)
    if clearance != requested_clearance:
        warnings.append(
            f"Scabbard clearance was clamped to {clearance:g} mm per side; use "
            f"{MIN_SCABBARD_CLEARANCE_MM:g}-{MAX_SCABBARD_CLEARANCE_MM:g} mm."
        )

    requested_wall = _finite_float(wall_thickness_mm, DEFAULT_SCABBARD_WALL_THICKNESS_MM)
    wall = clamp(requested_wall, MIN_SCABBARD_WALL_THICKNESS_MM, MAX_SCABBARD_WALL_THICKNESS_MM)
    if wall != requested_wall:
        warnings.append(
            f"Scabbard wall thickness was clamped to {wall:g} mm; use "
            f"{MIN_SCABBARD_WALL_THICKNESS_MM:g}-{MAX_SCABBARD_WALL_THICKNESS_MM:g} mm."
        )

    mode = split_mode if split_mode in SCABBARD_SPLIT_MODES else "Single Piece"
    if mode != split_mode:
        warnings.append("Unsupported scabbard split mode was normalized to Single Piece.")

    if profile.ricasso_length_mm >= profile.length_mm:
        warnings.append("Ricasso length is at or beyond blade length; reduce ricasso or increase blade length.")

    return (
        ScabbardParameters(
            blade_profile=profile,
            clearance_per_side_mm=clearance,
            wall_thickness_mm=wall,
            split_mode=mode,
            throat_enabled=bool(throat_enabled),
            end_cap_enabled=bool(end_cap_enabled),
        ),
        warnings,
    )


def blade_half_width_at(profile: ScabbardBladeProfile, y_mm: float) -> float:
    """Return the inherited blade half-width at a blade-local Y position."""
    y = clamp(float(y_mm), 0.0, profile.length_mm)
    if y <= profile.ricasso_length_mm:
        return profile.base_width_mm / 2
    if profile.blade_type == "tapered":
        body = max(1.0, profile.length_mm - profile.ricasso_length_mm)
        t = clamp((y - profile.ricasso_length_mm) / body, 0.0, 1.0)
        width = profile.base_width_mm + (profile.prop_tip_width_mm - profile.base_width_mm) * t
        return width / 2
    if profile.blade_type == "leaf":
        points = [
            (0.0, profile.base_width_mm),
            (profile.ricasso_length_mm, profile.base_width_mm),
            (profile.length_mm * 0.42, profile.base_width_mm * 0.84),
            (profile.length_mm * 0.70, profile.base_width_mm * 1.28),
            (profile.length_mm, profile.prop_tip_width_mm),
        ]
        points = sorted((max(0.0, min(profile.length_mm, py)), width) for py, width in points)
        for (y0, w0), (y1, w1) in zip(points, points[1:]):
            if y <= y1:
                if y1 <= y0:
                    return max(w0, w1) / 2
                t = (y - y0) / (y1 - y0)
                return (w0 + (w1 - w0) * t) / 2
        return profile.prop_tip_width_mm / 2
    raise ValueError(f"Unsupported scabbard blade type '{profile.blade_type}'.")


def cavity_half_width_at(params: ScabbardParameters, y_mm: float) -> float:
    if y_mm < 0:
        blade_half_width = params.blade_profile.base_width_mm / 2
    elif y_mm > params.blade_profile.length_mm:
        blade_half_width = params.blade_profile.prop_tip_width_mm / 2
    else:
        blade_half_width = blade_half_width_at(params.blade_profile, y_mm)
    return blade_half_width + params.clearance_per_side_mm


def outer_half_width_at(params: ScabbardParameters, y_mm: float) -> float:
    return cavity_half_width_at(params, y_mm) + params.wall_thickness_mm


def scabbard_profile_samples(params: ScabbardParameters) -> list[float]:
    length = params.blade_profile.length_mm
    samples = [
        0.0,
        params.blade_profile.ricasso_length_mm,
        length * 0.25,
        length * 0.42,
        length * 0.70,
        length * 0.88,
        length,
        params.cavity_end_y_mm,
    ]
    return sorted({round(clamp(y, 0.0, params.cavity_end_y_mm), 6) for y in samples})


def validate_scabbard_fit(params: ScabbardParameters) -> dict[str, list[str]]:
    """Perform deterministic profile-level fit and wall-thickness checks."""
    warnings: list[str] = []
    info: list[str] = []
    passed: list[str] = []
    profile = params.blade_profile

    if profile.blade_type not in SUPPORTED_SCABBARD_BLADE_STYLES:
        warnings.append(f"Unsupported scabbard blade type '{profile.blade_type}'.")
    if profile.length_mm <= 0 or profile.base_width_mm <= 0 or profile.prop_blade_thickness_mm <= 0:
        warnings.append("Invalid internal cavity dimensions; blade length, width, and thickness must be positive.")

    for y in scabbard_profile_samples(params):
        blade_half = blade_half_width_at(profile, min(y, profile.length_mm))
        cavity_half = cavity_half_width_at(params, y)
        outer_half = outer_half_width_at(params, y)
        if cavity_half + EPSILON_MM < blade_half + params.clearance_per_side_mm:
            warnings.append(f"Cavity is too narrow at y={y:g} mm for the inherited blade plus clearance.")
        if outer_half - cavity_half + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
            warnings.append(f"Scabbard side wall is below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm at y={y:g} mm.")

    if params.cavity_half_thickness_mm + EPSILON_MM < profile.prop_blade_thickness_mm / 2 + params.clearance_per_side_mm:
        warnings.append("Cavity is too thin for the inherited blade thickness plus clearance.")
    if params.outer_half_thickness_mm - params.cavity_half_thickness_mm + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
        warnings.append(f"Scabbard face wall is below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm.")

    if params.throat_enabled:
        throat_wall = params.wall_thickness_mm + params.throat_reinforcement_mm
        if throat_wall < MIN_SCABBARD_WALL_THICKNESS_MM:
            warnings.append("Throat wall becoming too thin; increase wall thickness or throat reinforcement.")
        else:
            passed.append("Throat entry remains open with reinforced wall thickness.")
    else:
        info.append("Throat collar is disabled; blade-entry path is still open at the scabbard mouth.")

    if params.end_cap_enabled:
        tip_wall = params.outer_end_y_mm - params.cavity_end_y_mm
        if tip_wall + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
            warnings.append("Tip/end-cap wall is below the safe minimum.")
        else:
            passed.append("End cap closes beyond the required tip-clearance zone.")
    else:
        info.append("End cap is disabled; the cavity is open past the blade tip.")

    if params.split_mode == "Two Piece":
        if outer_half_width_at(params, 0.0) <= 0 or params.outer_half_thickness_mm <= 0:
            warnings.append("Split mode would produce disconnected or empty halves.")
        else:
            passed.append("Two-piece split keeps both shell halves non-empty and cavity-open at the split plane.")

    if not warnings:
        passed.append("Blade profile fits the scabbard cavity at sampled positions with configured per-side clearance.")
        passed.append("Outer shell remains at or above the safe minimum wall thickness at sampled positions.")

    info.append(
        f"Clearance is interpreted as {params.clearance_per_side_mm:g} mm per side around blade width and thickness."
    )
    return {"warnings": warnings, "info": info, "passes": passed}


def _polygon_literal(points: list[tuple[float, float]]) -> str:
    return "[" + ", ".join(f"[{x:g}, {y:g}]" for x, y in points) + "]"


def _profile_points(params: ScabbardParameters, *, outer: bool, collar: bool = False) -> list[tuple[float, float]]:
    y_start = params.throat_start_y_mm
    y_end = params.outer_end_y_mm if outer else params.cavity_end_y_mm
    samples = [y_start, 0.0] + scabbard_profile_samples(params)
    if outer and params.end_cap_enabled:
        samples.append(params.outer_end_y_mm)
    samples = sorted({round(clamp(y, y_start, y_end), 6) for y in samples})
    right: list[tuple[float, float]] = []
    left: list[tuple[float, float]] = []
    for y in samples:
        half = outer_half_width_at(params, min(y, params.cavity_end_y_mm)) if outer else cavity_half_width_at(params, y)
        if collar:
            half += params.throat_reinforcement_mm
        right.append((half, y))
        left.append((-half, y))
    return left + list(reversed(right))


def _assignments(params: ScabbardParameters) -> str:
    profile = params.blade_profile
    values = {
        "blade_length_mm": profile.length_mm,
        "blade_base_width_mm": profile.base_width_mm,
        "blade_tip_width_mm": profile.tip_width_mm,
        "blade_thickness_mm": profile.thickness_mm,
        "ricasso_length_mm": profile.ricasso_length_mm,
        "prop_tip_width_mm": profile.prop_tip_width_mm,
        "prop_blade_thickness_mm": profile.prop_blade_thickness_mm,
        "scabbard_clearance_per_side_mm": params.clearance_per_side_mm,
        "scabbard_wall_thickness_mm": params.wall_thickness_mm,
        "scabbard_cavity_half_thickness_mm": params.cavity_half_thickness_mm,
        "scabbard_outer_half_thickness_mm": params.outer_half_thickness_mm,
        "scabbard_throat_length_mm": params.throat_length_mm,
        "scabbard_throat_reinforcement_mm": params.throat_reinforcement_mm,
        "scabbard_tip_clearance_mm": params.tip_clearance_mm,
        "scabbard_cavity_end_y_mm": params.cavity_end_y_mm,
        "scabbard_outer_end_y_mm": params.outer_end_y_mm,
        "eps": EPSILON_MM,
    }
    return "\n".join(f"{name} = {value:g};" for name, value in values.items())


def generate_scabbard_scad(
    blade_type: str,
    sword_metrics: dict[str, float],
    clearance_per_side_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM,
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    split_mode: str = "Single Piece",
    throat_enabled: bool = True,
    end_cap_enabled: bool = True,
) -> str:
    """Build a complete OpenSCAD program for a matching straight-blade scabbard."""
    params, warnings = normalize_scabbard_parameters(
        blade_type,
        sword_metrics,
        clearance_per_side_mm,
        wall_thickness_mm,
        split_mode,
        throat_enabled,
        end_cap_enabled,
    )
    profile = params.blade_profile
    cavity_points = _polygon_literal(_profile_points(params, outer=False))
    outer_points = _polygon_literal(_profile_points(params, outer=True))
    collar_points = _polygon_literal(_profile_points(params, outer=True, collar=True))
    warnings_text = "\n".join(f"// Warning: {message}" for message in warnings)
    throat_call = "scabbard_throat();" if params.throat_enabled else "// Throat collar disabled."
    body_call = "scabbard_body();"
    solid_call = f"""module scabbard_solid() {{
    union() {{
        {body_call}
        {throat_call}
    }}
}}"""
    if params.split_mode == "Two Piece":
        final_modules = """
module scabbard_left_half() {
    intersection() {
        scabbard_solid();
        translate([-5000, (scabbard_outer_end_y_mm+scabbard_throat_length_mm)/2-scabbard_throat_length_mm, 0])
            cube([10000, scabbard_outer_end_y_mm+scabbard_throat_length_mm+20, scabbard_outer_half_thickness_mm*4], center=true);
    }
}

module scabbard_right_half() {
    intersection() {
        scabbard_solid();
        translate([5000, (scabbard_outer_end_y_mm+scabbard_throat_length_mm)/2-scabbard_throat_length_mm, 0])
            cube([10000, scabbard_outer_end_y_mm+scabbard_throat_length_mm+20, scabbard_outer_half_thickness_mm*4], center=true);
    }
}

module scabbard_two_piece() {
    // Halves are shown separated for printing; remove translations to digitally reassemble.
    translate([-scabbard_wall_thickness_mm*1.25, 0, 0]) scabbard_left_half();
    translate([scabbard_wall_thickness_mm*1.25, 0, 0]) scabbard_right_half();
}

scabbard_two_piece();"""
    else:
        final_modules = """
module scabbard_single_piece() {
    scabbard_solid();
}

scabbard_single_piece();"""

    return f"""// Digital Forge Scabbard Version 1
// Supported scabbard blade type: {profile.blade_type}
// Inherited sword dimensions are normalized with the same prop-safe tip/thickness clamps used by sword generation.
// Clearance is per side, not total diametric clearance.
// Wall thickness is measured from the blade cavity to the exterior shell on sides and faces.
// Split mode: {params.split_mode}
// Throat enabled: {params.throat_enabled}
// End cap enabled: {params.end_cap_enabled}
{warnings_text}
$fn = 56;
{_assignments(params)}

module scabbard_cavity_profile_2d() {{
    polygon(points={cavity_points});
}}

module scabbard_outer_profile_2d() {{
    polygon(points={outer_points});
}}

module scabbard_throat_outer_profile_2d() {{
    polygon(points={collar_points});
}}

module scabbard_body() {{
    difference() {{
        linear_extrude(height=scabbard_outer_half_thickness_mm*2, center=true)
            scabbard_outer_profile_2d();
        translate([0, 0, 0])
            linear_extrude(height=scabbard_cavity_half_thickness_mm*2+eps*2, center=true)
                scabbard_cavity_profile_2d();
    }}
}}

module scabbard_throat() {{
    // Modest reinforced collar at the open blade-entry path.
    intersection() {{
        difference() {{
            linear_extrude(height=(scabbard_outer_half_thickness_mm+scabbard_throat_reinforcement_mm)*2, center=true)
                scabbard_throat_outer_profile_2d();
            linear_extrude(height=scabbard_cavity_half_thickness_mm*2+eps*2, center=true)
                scabbard_cavity_profile_2d();
        }}
        translate([0, 0, 0])
            cube([blade_base_width_mm+2*(scabbard_clearance_per_side_mm+scabbard_wall_thickness_mm+scabbard_throat_reinforcement_mm)+eps,
                  scabbard_throat_length_mm*2,
                  (scabbard_outer_half_thickness_mm+scabbard_throat_reinforcement_mm)*2+eps], center=true);
    }}
}}

{solid_call}
{final_modules}
"""
