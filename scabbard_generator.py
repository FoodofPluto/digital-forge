"""Parametric scabbard generation derived from Digital Forge blade profiles."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import re
import shutil
from uuid import uuid4

from scad_generator import clamp


SUPPORTED_SCABBARD_BLADE_STYLES = ("tapered", "leaf", "curved", "falchion")
SCABBARD_BLADE_LABELS = {
    "Symmetrical Tapered": "tapered",
    "Tapered": "tapered",
    "tapered": "tapered",
    "Leaf": "leaf",
    "leaf": "leaf",
    "Curved": "curved",
    "Curved Saber": "curved",
    "curved": "curved",
    "Falchion": "falchion",
    "falchion": "falchion",
}
SCABBARD_FIT_MODES = ("Fitted Scabbard", "Straight Exterior")
SCABBARD_SPLIT_MODES = ("Single Piece", "Left/Right Halves", "Front/Back Halves", "Two Piece")
SCABBARD_STL_OBJECT_TYPES = ("Blade only",)
CUSTOM_STL_PREVIEW_MODES = ("Scabbard Only", "Imported Blade Only", "Blade Fit Diagnostic")
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
DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM = 0.25
MAX_SCABBARD_SEAM_ALLOWANCE_MM = 1.5
SCABBARD_PROFILE_STATIONS = 24
EPSILON_MM = 0.05
CSG_EPSILON_MM = EPSILON_MM
THROAT_CUT_OVERSHOOT_MM = 6.0
SPLIT_CUTTER_OVERSHOOT_MM = 40.0
MAX_CUSTOM_STL_UPLOAD_BYTES = 8 * 1024 * 1024
CUSTOM_STL_DIR = Path(__file__).resolve().parent / "generated" / "uploaded_stl"

# Scabbard coordinate convention:
# X = blade/scabbard width, centered on the blade centerline for symmetrical blades.
# Y = blade/scabbard length, with the throat at negative Y and the tip at positive Y.
# Z = shell depth/thickness, produced by linear_extrude(..., center=true).


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
    fit_mode: str = "Fitted Scabbard"
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM
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


@dataclass(frozen=True)
class CustomStlScabbardParameters:
    stl_path: Path
    object_type: str = "Blade only"
    rotate_x_deg: float = 0.0
    rotate_y_deg: float = 0.0
    rotate_z_deg: float = 0.0
    scale: float = 1.0
    clearance_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM
    throat_length_mm: float = DEFAULT_THROAT_LENGTH_MM
    split_mode: str = "Single Piece"
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM
    preview_mode: str = "Scabbard Only"


@dataclass(frozen=True)
class ScabbardBounds:
    throat_y_mm: float
    tip_y_mm: float
    max_outer_half_width_mm: float
    max_cavity_half_width_mm: float
    outer_half_depth_mm: float
    cavity_half_depth_mm: float
    split_length_bound_mm: float
    split_width_bound_mm: float
    split_depth_bound_mm: float


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
        supported = ", ".join(("Symmetrical Tapered", "Leaf", "Curved", "Falchion"))
        raise ValueError(f"Unsupported scabbard blade type '{blade_type}'. Supported scabbards: {supported}.")
    return normalized


def normalize_scabbard_fit_mode(fit_mode: str | None) -> str:
    value = str(fit_mode or "Fitted Scabbard").strip()
    if value in SCABBARD_FIT_MODES:
        return value
    if value.lower() in {"fitted", "fit", "blade-fitted"}:
        return "Fitted Scabbard"
    if value.lower() in {"straight", "simple", "straight scabbard"}:
        return "Straight Exterior"
    return "Fitted Scabbard"


def normalize_scabbard_split_mode(split_mode: str | None) -> str:
    value = str(split_mode or "Single Piece").strip()
    if value == "Two Piece":
        return "Left/Right Halves"
    return value if value in SCABBARD_SPLIT_MODES else "Single Piece"


def inherit_blade_profile(blade_type: str, sword_metrics: dict[str, float]) -> ScabbardBladeProfile:
    """Inherit the same blade dimensions and prop clamps used by sword generation."""
    style = normalize_scabbard_blade_type(blade_type)
    length = max(1.0, _finite_float(sword_metrics.get("blade_length_mm"), 1.0))
    base_width = max(1.0, _finite_float(sword_metrics.get("blade_base_width_mm"), 1.0))
    tip_width = max(0.0, _finite_float(sword_metrics.get("blade_tip_width_mm"), 0.0))
    thickness = max(1.0, _finite_float(sword_metrics.get("blade_thickness_mm"), 1.0))
    ricasso = clamp(max(0.0, _finite_float(sword_metrics.get("ricasso_length_mm"), 0.0)), 0.0, length * 0.85)
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
    fit_mode: str = "Fitted Scabbard",
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
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

    mode = normalize_scabbard_split_mode(split_mode)
    if mode != split_mode and not (mode == "Left/Right Halves" and split_mode == "Two Piece"):
        warnings.append("Unsupported scabbard split mode was normalized to Single Piece.")

    fit = normalize_scabbard_fit_mode(fit_mode)
    if fit != fit_mode:
        warnings.append("Unsupported scabbard fit mode was normalized to Fitted Scabbard.")

    requested_seam = _finite_float(seam_allowance_mm, DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM)
    seam = clamp(requested_seam, 0.0, MAX_SCABBARD_SEAM_ALLOWANCE_MM)
    if seam != requested_seam:
        warnings.append(f"Scabbard seam allowance was clamped to {seam:g} mm.")

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
            fit_mode=fit,
            seam_allowance_mm=seam,
        ),
        warnings,
    )


def blade_profile_points(profile: ScabbardBladeProfile) -> list[tuple[float, float]]:
    """Return blade-local 2D points matching scad_generator._blade_polygon."""
    w = profile.base_width_mm
    tip = profile.prop_tip_width_mm
    length = profile.length_mm
    ricasso = profile.ricasso_length_mm
    if profile.blade_type == "tapered":
        return [(-w / 2, ricasso), (-tip / 2, length), (tip / 2, length), (w / 2, ricasso)]
    if profile.blade_type == "leaf":
        return [
            (-w / 2, ricasso),
            (-w * 0.42, length * 0.42),
            (-w * 0.64, length * 0.70),
            (-tip / 2, length),
            (tip / 2, length),
            (w * 0.64, length * 0.70),
            (w * 0.42, length * 0.42),
            (w / 2, ricasso),
        ]
    if profile.blade_type == "curved":
        return [
            (-w * 0.50, ricasso),
            (-w * 0.38, length * 0.30),
            (-w * 0.12, length * 0.62),
            (w * 0.38, length * 0.88),
            (w * 0.72, length),
            (w * 0.80, length * 0.84),
            (w * 0.62, length * 0.55),
            (w * 0.50, ricasso),
        ]
    if profile.blade_type == "falchion":
        return [
            (-w * 0.42, ricasso),
            (-w * 0.44, length * 0.38),
            (-w * 0.58, length * 0.66),
            (-w * 0.78, length * 0.84),
            (-w * 0.70, length * 0.96),
            (-w * 0.22, length),
            (w * 0.58, length * 0.88),
            (w * 0.68, length * 0.72),
            (w * 0.52, length * 0.40),
            (w * 0.42, ricasso),
        ]
    raise ValueError(f"Unsupported scabbard blade type '{profile.blade_type}'.")


def _edge_intersections(points: list[tuple[float, float]], y_mm: float) -> list[float]:
    xs: list[float] = []
    y = y_mm
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        if abs(y1 - y0) < EPSILON_MM:
            if abs(y - y0) < EPSILON_MM:
                xs.extend([x0, x1])
            continue
        low, high = sorted((y0, y1))
        if low - EPSILON_MM <= y <= high + EPSILON_MM:
            t = clamp((y - y0) / (y1 - y0), 0.0, 1.0)
            xs.append(x0 + (x1 - x0) * t)
    return xs


def blade_edges_at(profile: ScabbardBladeProfile, y_mm: float) -> tuple[float, float]:
    """Return minimum and maximum blade X at a blade-local Y station."""
    y = clamp(float(y_mm), 0.0, profile.length_mm)
    if y <= profile.ricasso_length_mm:
        return -profile.base_width_mm / 2, profile.base_width_mm / 2
    xs = _edge_intersections(blade_profile_points(profile), y)
    if len(xs) < 2:
        half = profile.prop_tip_width_mm / 2
        return -half, half
    return min(xs), max(xs)


def blade_half_width_at(profile: ScabbardBladeProfile, y_mm: float) -> float:
    """Return half of the blade's full X envelope at a blade-local Y position."""
    left, right = blade_edges_at(profile, y_mm)
    return (right - left) / 2


def blade_center_offset_at(profile: ScabbardBladeProfile, y_mm: float) -> float:
    left, right = blade_edges_at(profile, y_mm)
    return (left + right) / 2


def blade_envelope(profile: ScabbardBladeProfile) -> tuple[float, float]:
    """Return the full sampled X envelope needed for blade insertion through the throat."""
    length = profile.length_mm
    stations = {
        0.0,
        profile.ricasso_length_mm,
        length * 0.30,
        length * 0.38,
        length * 0.42,
        length * 0.55,
        length * 0.62,
        length * 0.66,
        length * 0.70,
        length * 0.72,
        length * 0.84,
        length * 0.88,
        length * 0.96,
        length,
    }
    for index in range(SCABBARD_PROFILE_STATIONS + 1):
        stations.add(length * index / SCABBARD_PROFILE_STATIONS)
    edges = [blade_edges_at(profile, y) for y in stations]
    return min(left for left, _right in edges), max(right for _left, right in edges)


def cavity_edges_at(params: ScabbardParameters, y_mm: float) -> tuple[float, float]:
    if y_mm < 0:
        left, right = blade_envelope(params.blade_profile)
    elif y_mm > params.blade_profile.length_mm:
        left, right = blade_edges_at(params.blade_profile, params.blade_profile.length_mm)
    else:
        left, right = blade_edges_at(params.blade_profile, y_mm)
    return left - params.clearance_per_side_mm, right + params.clearance_per_side_mm


def outer_edges_at(params: ScabbardParameters, y_mm: float) -> tuple[float, float]:
    left, right = cavity_edges_at(params, y_mm)
    if params.fit_mode == "Straight Exterior":
        max_half = max(cavity_half_width_at(params, sample) for sample in scabbard_profile_samples(params))
        center = 0.0 if params.blade_profile.blade_type != "curved" else blade_center_offset_at(
            params.blade_profile, min(max(y_mm, 0.0), params.blade_profile.length_mm)
        )
        return center - max_half - params.wall_thickness_mm, center + max_half + params.wall_thickness_mm
    return left - params.wall_thickness_mm, right + params.wall_thickness_mm


def cavity_half_width_at(params: ScabbardParameters, y_mm: float) -> float:
    left, right = cavity_edges_at(params, y_mm)
    return (right - left) / 2 + 1e-9


def outer_half_width_at(params: ScabbardParameters, y_mm: float) -> float:
    left, right = outer_edges_at(params, y_mm)
    return (right - left) / 2 + 1e-9


def scabbard_profile_samples(params: ScabbardParameters) -> list[float]:
    length = params.blade_profile.length_mm
    base_samples = {
        0.0,
        params.blade_profile.ricasso_length_mm,
        length * 0.25,
        length * 0.30,
        length * 0.38,
        length * 0.42,
        length * 0.55,
        length * 0.62,
        length * 0.66,
        length * 0.70,
        length * 0.72,
        length * 0.84,
        length * 0.88,
        length * 0.96,
        length,
        params.cavity_end_y_mm,
    }
    for index in range(SCABBARD_PROFILE_STATIONS + 1):
        base_samples.add(length * index / SCABBARD_PROFILE_STATIONS)
    return sorted({round(clamp(y, 0.0, params.cavity_end_y_mm), 6) for y in base_samples})


def scabbard_inner_profile_points(params: ScabbardParameters) -> list[tuple[float, float]]:
    return _profile_points(params, outer=False)


def scabbard_outer_profile_points(params: ScabbardParameters) -> list[tuple[float, float]]:
    return _profile_points(params, outer=True)


def scabbard_geometry_bounds(params: ScabbardParameters) -> ScabbardBounds:
    """Return deterministic bounds used for throat and split cutters."""
    samples = [params.throat_start_y_mm, 0.0] + scabbard_profile_samples(params)
    max_outer = max(outer_half_width_at(params, y) for y in samples)
    max_cavity = max(cavity_half_width_at(params, y) for y in samples)
    length_span = params.outer_end_y_mm - params.throat_start_y_mm
    return ScabbardBounds(
        throat_y_mm=params.throat_start_y_mm,
        tip_y_mm=params.outer_end_y_mm,
        max_outer_half_width_mm=max_outer,
        max_cavity_half_width_mm=max_cavity,
        outer_half_depth_mm=params.outer_half_thickness_mm,
        cavity_half_depth_mm=params.cavity_half_thickness_mm,
        split_length_bound_mm=length_span + SPLIT_CUTTER_OVERSHOOT_MM,
        split_width_bound_mm=max_outer * 2 + SPLIT_CUTTER_OVERSHOOT_MM,
        split_depth_bound_mm=params.outer_half_thickness_mm * 2 + SPLIT_CUTTER_OVERSHOOT_MM,
    )


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

    max_blade_width = 0.0
    throat_half = cavity_half_width_at(params, params.throat_start_y_mm)
    for y in scabbard_profile_samples(params):
        blade_left, blade_right = blade_edges_at(profile, min(y, profile.length_mm))
        cavity_left, cavity_right = cavity_edges_at(params, y)
        outer_left, outer_right = outer_edges_at(params, y)
        max_blade_width = max(max_blade_width, blade_right - blade_left)
        if cavity_left > blade_left - params.clearance_per_side_mm + EPSILON_MM:
            warnings.append(f"Cavity left edge is too tight at y={y:g} mm for the inherited blade plus clearance.")
        if cavity_right < blade_right + params.clearance_per_side_mm - EPSILON_MM:
            warnings.append(f"Cavity right edge is too tight at y={y:g} mm for the inherited blade plus clearance.")
        if cavity_left - outer_left + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
            warnings.append(f"Left scabbard side wall is below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm at y={y:g} mm.")
        if outer_right - cavity_right + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
            warnings.append(f"Right scabbard side wall is below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm at y={y:g} mm.")

    if throat_half * 2 + EPSILON_MM < max_blade_width + params.clearance_per_side_mm * 2:
        warnings.append("Throat opening is smaller than the widest required blade insertion width; increase clearance or use fitted mode.")
    else:
        passed.append("Throat opening clears the widest sampled blade section for insertion.")

    if profile.blade_type == "leaf":
        y_base = max(profile.ricasso_length_mm, 0.0)
        y_widest = profile.length_mm * 0.70
        y_later = profile.length_mm * 0.92
        blade_base = blade_half_width_at(profile, y_base)
        blade_belly = blade_half_width_at(profile, y_widest)
        blade_later = blade_half_width_at(profile, y_later)
        cavity_base = cavity_half_width_at(params, y_base)
        cavity_belly = cavity_half_width_at(params, y_widest)
        cavity_later = cavity_half_width_at(params, y_later)
        outer_base = outer_half_width_at(params, y_base)
        outer_belly = outer_half_width_at(params, y_widest)
        outer_later = outer_half_width_at(params, y_later)
        if not (blade_belly > blade_base + EPSILON_MM and blade_belly > blade_later + EPSILON_MM):
            warnings.append("Leaf blade profile failed to preserve the widened belly before scabbard generation.")
        elif not (cavity_belly > cavity_base + EPSILON_MM and cavity_belly > cavity_later + EPSILON_MM):
            warnings.append("Leaf fitted cavity failed to preserve the blade belly; generation would taper inward incorrectly.")
        elif params.fit_mode == "Fitted Scabbard" and not (
            outer_belly > outer_base + EPSILON_MM and outer_belly > outer_later + EPSILON_MM
        ):
            warnings.append("Leaf fitted outer profile failed to preserve the belly; generation would taper inward incorrectly.")
        else:
            passed.append("Leaf scabbard widens through the blade belly before narrowing toward the tip.")
    if profile.blade_type == "falchion":
        belly_y = profile.length_mm * 0.84
        if cavity_half_width_at(params, belly_y) + EPSILON_MM < blade_half_width_at(profile, belly_y) + params.clearance_per_side_mm:
            warnings.append("Falchion belly clearance is insufficient; increase clearance or wall thickness.")
        else:
            passed.append("Falchion belly corridor is included in the fitted cavity.")
    if profile.blade_type == "curved":
        offsets = [abs(blade_center_offset_at(profile, y)) for y in scabbard_profile_samples(params)]
        max_offset = max(offsets) if offsets else 0.0
        if max_offset > max(45.0, profile.base_width_mm * 1.2) and params.wall_thickness_mm < 3.0:
            warnings.append("Curved scabbard has high centerline sweep for the requested wall thickness; increase wall thickness.")
        else:
            passed.append("Curved scabbard follows the sampled blade centerline instead of a straight shell.")

    if params.cavity_half_thickness_mm + EPSILON_MM < profile.prop_blade_thickness_mm / 2 + params.clearance_per_side_mm:
        warnings.append("Cavity is too thin for the inherited blade thickness plus clearance.")
    if params.outer_half_thickness_mm - params.cavity_half_thickness_mm + EPSILON_MM < MIN_SCABBARD_WALL_THICKNESS_MM:
        warnings.append(f"Scabbard face wall is below {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm.")

    if params.throat_enabled:
        bounds = scabbard_geometry_bounds(params)
        if params.throat_start_y_mm >= 0:
            warnings.append("Throat cut misses the shell because the throat plane is not before the blade base.")
        elif bounds.max_cavity_half_width_mm >= bounds.max_outer_half_width_mm:
            warnings.append("Cavity does not fit inside the outer volume at the throat.")
        else:
            passed.append("Throat cut overlaps the blade-entry shell and extends through the full shell depth.")
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

    if params.split_mode != "Single Piece":
        bounds = scabbard_geometry_bounds(params)
        length_span = params.outer_end_y_mm - params.throat_start_y_mm
        if bounds.split_length_bound_mm <= length_span:
            warnings.append("Split cutter does not cover the full shell length; split result may be a tiny fragment.")
        if bounds.split_width_bound_mm <= bounds.max_outer_half_width_mm * 2:
            warnings.append("Split cutter does not cover the full shell width; split result may be a tiny fragment.")
        if bounds.split_depth_bound_mm <= params.outer_half_thickness_mm * 2:
            warnings.append("Split cutter does not cover the full shell depth; split result may be a tiny fragment.")
        if params.seam_allowance_mm > params.wall_thickness_mm * 0.45:
            warnings.append("Split seam allowance is large relative to wall thickness; reduce seam allowance.")
        else:
            passed.append(f"{params.split_mode} split keeps a nonzero seam allowance and avoids coplanar cuts.")

    if not warnings:
        passed.append("Blade profile fits the scabbard cavity at sampled positions with configured per-side clearance.")
        passed.append("Outer shell remains at or above the safe minimum wall thickness at sampled positions.")

    info.append("Scabbard mode: fitted geometry is derived from the selected blade profile, not separate scabbard presets.")
    info.append(
        f"Clearance is interpreted as {params.clearance_per_side_mm:g} mm per side around blade width and thickness."
    )
    if params.fit_mode == "Straight Exterior":
        info.append("Straight Exterior simplifies only the outside silhouette; the internal cavity still follows the blade.")
    return {"warnings": warnings, "info": info, "passes": passed}


def _polygon_literal(points: list[tuple[float, float]]) -> str:
    return "[" + ", ".join(f"[{x:g}, {y:g}]" for x, y in points) + "]"


def _profile_points(
    params: ScabbardParameters,
    *,
    outer: bool,
    collar: bool = False,
    cavity_throat_overshoot: bool = False,
) -> list[tuple[float, float]]:
    y_start = params.throat_start_y_mm
    if cavity_throat_overshoot and not outer:
        y_start -= THROAT_CUT_OVERSHOOT_MM
    y_end = params.outer_end_y_mm if outer else params.cavity_end_y_mm
    samples = [y_start, 0.0] + scabbard_profile_samples(params)
    if outer and params.end_cap_enabled:
        samples.append(params.outer_end_y_mm)
    samples = sorted({round(clamp(y, y_start, y_end), 6) for y in samples})
    right: list[tuple[float, float]] = []
    left: list[tuple[float, float]] = []
    for y in samples:
        if outer:
            lx, rx = outer_edges_at(params, min(y, params.cavity_end_y_mm))
        else:
            lx, rx = cavity_edges_at(params, y)
        if collar:
            lx -= params.throat_reinforcement_mm
            rx += params.throat_reinforcement_mm
        left.append((lx, y))
        right.append((rx, y))
    return left + list(reversed(right))


def _assignments(params: ScabbardParameters) -> str:
    profile = params.blade_profile
    bounds = scabbard_geometry_bounds(params)
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
        "scabbard_throat_start_y_mm": params.throat_start_y_mm,
        "scabbard_throat_reinforcement_mm": params.throat_reinforcement_mm,
        "scabbard_tip_clearance_mm": params.tip_clearance_mm,
        "scabbard_seam_allowance_mm": params.seam_allowance_mm,
        "scabbard_cavity_end_y_mm": params.cavity_end_y_mm,
        "scabbard_outer_end_y_mm": params.outer_end_y_mm,
        "scabbard_max_outer_half_width_mm": bounds.max_outer_half_width_mm,
        "scabbard_max_cavity_half_width_mm": bounds.max_cavity_half_width_mm,
        "scabbard_split_length_bound_mm": bounds.split_length_bound_mm,
        "scabbard_split_width_bound_mm": bounds.split_width_bound_mm,
        "scabbard_split_depth_bound_mm": bounds.split_depth_bound_mm,
        "scabbard_throat_cut_overshoot_mm": THROAT_CUT_OVERSHOOT_MM,
        "scabbard_split_cutter_overshoot_mm": SPLIT_CUTTER_OVERSHOOT_MM,
        "eps": EPSILON_MM,
    }
    return "\n".join(f"{name} = {value:g};" for name, value in values.items())


def _split_modules(params: ScabbardParameters) -> str:
    y_center = "(scabbard_outer_end_y_mm + scabbard_throat_start_y_mm) / 2"
    preview_offset = "scabbard_max_outer_half_width_mm + scabbard_wall_thickness_mm*2"
    if params.split_mode == "Left/Right Halves":
        return f"""
module scabbard_part_a() {{
    intersection() {{
        scabbard_final_single_piece();
        scabbard_split_halfspace_a();
    }}
}}

module scabbard_part_b() {{
    intersection() {{
        scabbard_final_single_piece();
        scabbard_split_halfspace_b();
    }}
}}

module scabbard_split_halfspace_a() {{
    translate([-(scabbard_split_width_bound_mm/4 + scabbard_seam_allowance_mm/2), {y_center}, 0])
        cube([scabbard_split_width_bound_mm/2, scabbard_split_length_bound_mm, scabbard_split_depth_bound_mm], center=true);
}}

module scabbard_split_halfspace_b() {{
    translate([(scabbard_split_width_bound_mm/4 + scabbard_seam_allowance_mm/2), {y_center}, 0])
        cube([scabbard_split_width_bound_mm/2, scabbard_split_length_bound_mm, scabbard_split_depth_bound_mm], center=true);
}}

module scabbard_left_half() {{ scabbard_part_a(); }}
module scabbard_right_half() {{ scabbard_part_b(); }}
module scabbard_two_piece() {{
    translate([-{preview_offset}, 0, 0]) scabbard_part_a();
    translate([{preview_offset}, 0, 0]) scabbard_part_b();
}}

scabbard_two_piece();"""
    if params.split_mode == "Front/Back Halves":
        return f"""
module scabbard_part_a() {{
    intersection() {{
        scabbard_final_single_piece();
        scabbard_split_halfspace_a();
    }}
}}

module scabbard_part_b() {{
    intersection() {{
        scabbard_final_single_piece();
        scabbard_split_halfspace_b();
    }}
}}

module scabbard_split_halfspace_a() {{
    translate([0, {y_center}, -(scabbard_split_depth_bound_mm/4 + scabbard_seam_allowance_mm/2)])
        cube([scabbard_split_width_bound_mm, scabbard_split_length_bound_mm, scabbard_split_depth_bound_mm/2], center=true);
}}

module scabbard_split_halfspace_b() {{
    translate([0, {y_center}, (scabbard_split_depth_bound_mm/4 + scabbard_seam_allowance_mm/2)])
        cube([scabbard_split_width_bound_mm, scabbard_split_length_bound_mm, scabbard_split_depth_bound_mm/2], center=true);
}}

module scabbard_two_piece() {{
    translate([0, 0, -scabbard_outer_half_thickness_mm*1.8]) scabbard_part_a();
    translate([0, 0, scabbard_outer_half_thickness_mm*1.8]) scabbard_part_b();
}}

scabbard_two_piece();"""
    return """
module scabbard_single_piece() {
    scabbard_final_single_piece();
}

scabbard_single_piece();"""


def generate_scabbard_scad(
    blade_type: str,
    sword_metrics: dict[str, float],
    clearance_per_side_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM,
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    split_mode: str = "Single Piece",
    throat_enabled: bool = True,
    end_cap_enabled: bool = True,
    fit_mode: str = "Fitted Scabbard",
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
) -> str:
    """Build a complete OpenSCAD program for a matching blade-driven scabbard."""
    params, warnings = normalize_scabbard_parameters(
        blade_type,
        sword_metrics,
        clearance_per_side_mm,
        wall_thickness_mm,
        split_mode,
        throat_enabled,
        end_cap_enabled,
        fit_mode,
        seam_allowance_mm,
    )
    profile = params.blade_profile
    cavity_points = _polygon_literal(_profile_points(params, outer=False))
    cavity_cut_points = _polygon_literal(_profile_points(params, outer=False, cavity_throat_overshoot=True))
    outer_points = _polygon_literal(_profile_points(params, outer=True))
    collar_points = _polygon_literal(_profile_points(params, outer=True, collar=True))
    blade_points = _polygon_literal(blade_profile_points(profile))
    warnings_text = "\n".join(f"// Warning: {message}" for message in warnings)
    throat_cut_call = "scabbard_throat_cut();" if params.throat_enabled else "// Throat cut disabled."

    return f"""// Digital Forge Scabbard Version 2
// Supported scabbard blade type: {profile.blade_type}
// Scabbard fit mode: {params.fit_mode}
// Cavity is sampled from the selected blade profile: blade_profile_points -> scabbard_inner_profile_points.
// Fitted Scabbard follows blade profile, curvature, belly, and tip; Straight Exterior simplifies only the outside.
// Clearance is per side, not total diametric clearance.
// Wall thickness is measured from the blade cavity to the exterior shell on sides and faces.
// Coordinate convention: X=scabbard width, Y=throat-to-tip length, Z=shell depth.
// Split mode: {params.split_mode}
// Throat enabled: {params.throat_enabled}
// End cap enabled: {params.end_cap_enabled}
{warnings_text}
$fn = 56;
{_assignments(params)}

function blade_envelope_marker() = "{profile.blade_type}_style_aware_profile";
blade_profile_points = {blade_points};
scabbard_cavity_points = {cavity_points};
scabbard_cavity_cut_points = {cavity_cut_points};
scabbard_outer_points = {outer_points};

module blade_reference_profile_2d() {{
    polygon(points=blade_profile_points);
}}

module scabbard_cavity_profile_2d() {{
    polygon(points=scabbard_cavity_points);
}}

module scabbard_cavity_cut_profile_2d() {{
    polygon(points=scabbard_cavity_cut_points);
}}

module scabbard_outer_profile_2d() {{
    polygon(points=scabbard_outer_points);
}}

module scabbard_throat_outer_profile_2d() {{
    polygon(points={collar_points});
}}

module blade_reference_geometry() {{
    color("silver", 0.35)
        linear_extrude(height=prop_blade_thickness_mm, center=true)
            blade_reference_profile_2d();
}}

module scabbard_inner_cavity() {{
    linear_extrude(height=scabbard_cavity_half_thickness_mm*2+eps*2, center=true)
        scabbard_cavity_cut_profile_2d();
}}

module scabbard_outer_volume() {{
    linear_extrude(height=scabbard_outer_half_thickness_mm*2, center=true)
        scabbard_outer_profile_2d();
}}

module scabbard_hollow_shell() {{
    difference() {{
        scabbard_outer_volume();
        scabbard_inner_cavity();
    }}
}}

module scabbard_throat_cut() {{
    translate([0, scabbard_throat_start_y_mm, 0])
        cube([scabbard_max_cavity_half_width_mm*2 + eps*4,
              scabbard_throat_cut_overshoot_mm*2,
              scabbard_outer_half_thickness_mm*2 + scabbard_throat_cut_overshoot_mm*2], center=true);
}}

module scabbard_final_single_piece() {{
    difference() {{
        scabbard_hollow_shell();
        {throat_cut_call}
    }}
}}

module scabbard_hollow_cutaway() {{
    difference() {{
        scabbard_final_single_piece();
        translate([scabbard_max_outer_half_width_mm/2, (scabbard_outer_end_y_mm+scabbard_throat_start_y_mm)/2, 0])
            cube([scabbard_max_outer_half_width_mm, scabbard_split_length_bound_mm, scabbard_split_depth_bound_mm], center=true);
    }}
    %scabbard_inner_cavity();
}}

module scabbard_diagnostic_inner_cavity_only() {{
    %blade_reference_geometry();
    #scabbard_inner_cavity();
}}

module scabbard_diagnostic_outer_volume_only() {{
    %blade_reference_geometry();
    scabbard_outer_volume();
}}

module scabbard_diagnostic_hollow_shell_before_throat_cut() {{
    %blade_reference_geometry();
    scabbard_hollow_shell();
}}

module scabbard_diagnostic_throat_cut_only() {{
    %blade_reference_geometry();
    #scabbard_throat_cut();
}}

{_split_modules(params)}
"""


def sanitize_stl_filename(filename: str) -> str:
    """Return a safe STL filename without path components."""
    stem = Path(str(filename or "uploaded_blade.stl")).name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    if not safe.lower().endswith(".stl"):
        safe += ".stl"
    return safe or "uploaded_blade.stl"


def validate_custom_stl_upload(filename: str, size_bytes: int | None = None) -> list[str]:
    warnings: list[str] = []
    if not str(filename or "").lower().endswith(".stl"):
        warnings.append("Custom STL scabbards accept only .stl files.")
    if size_bytes is not None and size_bytes > MAX_CUSTOM_STL_UPLOAD_BYTES:
        warnings.append(f"Uploaded STL is larger than {MAX_CUSTOM_STL_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return warnings


def save_uploaded_stl(uploaded_file, directory: Path = CUSTOM_STL_DIR) -> tuple[Path | None, list[str]]:
    """Copy a Streamlit UploadedFile into the controlled generated/uploaded_stl directory."""
    name = getattr(uploaded_file, "name", "")
    try:
        size = int(getattr(uploaded_file, "size", 0) or 0)
    except (TypeError, ValueError):
        size = None
    warnings = validate_custom_stl_upload(name, size)
    if warnings:
        return None, warnings
    directory.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid4().hex}_{sanitize_stl_filename(name)}"
    target = (directory / safe_name).resolve()
    if directory.resolve() not in target.parents:
        return None, ["Uploaded STL path failed safety validation."]
    try:
        with target.open("wb") as output:
            if hasattr(uploaded_file, "getbuffer"):
                output.write(uploaded_file.getbuffer())
            else:
                shutil.copyfileobj(uploaded_file, output)
    except (OSError, PermissionError) as exc:
        return None, [f"Uploaded STL could not be saved: {exc}"]
    return target, []


def _scad_path_literal(path: Path) -> str:
    controlled = CUSTOM_STL_DIR.resolve()
    resolved = Path(path).resolve()
    if controlled not in resolved.parents:
        raise ValueError("Custom STL path is outside the controlled upload directory.")
    return resolved.as_posix().replace("\\", "/").replace('"', "")


def normalize_custom_stl_scabbard_parameters(
    stl_path: str | Path,
    object_type: str = "Blade only",
    rotate_x_deg: float = 0.0,
    rotate_y_deg: float = 0.0,
    rotate_z_deg: float = 0.0,
    scale: float = 1.0,
    clearance_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM,
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    throat_length_mm: float = DEFAULT_THROAT_LENGTH_MM,
    split_mode: str = "Single Piece",
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
    preview_imported_mesh: bool = False,
    preview_mode: str | None = None,
) -> tuple[CustomStlScabbardParameters | None, list[str]]:
    warnings = []
    path = Path(stl_path)
    try:
        safe_path = Path(_scad_path_literal(path))
    except ValueError as exc:
        return None, [str(exc)]
    if not path.exists():
        warnings.append("Uploaded STL is missing or was deleted; upload the blade STL again.")
    if object_type not in SCABBARD_STL_OBJECT_TYPES:
        warnings.append("Custom STL scabbards currently support blade-only STL files; full sword STL files are not wrapped.")
        object_type = "Blade only"
    requested_scale = _finite_float(scale, 1.0)
    safe_scale = clamp(requested_scale, 0.05, 20.0)
    if safe_scale != requested_scale:
        warnings.append(f"STL scale was clamped to {safe_scale:g}.")
    requested_clearance = _finite_float(clearance_mm, DEFAULT_SCABBARD_CLEARANCE_MM)
    clearance = clamp(requested_clearance, MIN_SCABBARD_CLEARANCE_MM, MAX_SCABBARD_CLEARANCE_MM)
    if clearance != requested_clearance:
        warnings.append(f"STL cavity clearance was clamped to {clearance:g} mm.")
    requested_wall = _finite_float(wall_thickness_mm, DEFAULT_SCABBARD_WALL_THICKNESS_MM)
    wall = clamp(requested_wall, MIN_SCABBARD_WALL_THICKNESS_MM, MAX_SCABBARD_WALL_THICKNESS_MM)
    if wall != requested_wall:
        warnings.append(f"STL wall thickness was clamped to {wall:g} mm.")
    seam = clamp(_finite_float(seam_allowance_mm, DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM), 0.0, MAX_SCABBARD_SEAM_ALLOWANCE_MM)
    throat = clamp(_finite_float(throat_length_mm, DEFAULT_THROAT_LENGTH_MM), 0.0, 80.0)
    if throat <= 0:
        warnings.append("STL throat opening length was raised to 1 mm so the blade-entry cap is removed.")
        throat = 1.0
    mode = str(preview_mode or "").strip()
    if not mode:
        mode = "Blade Fit Diagnostic" if preview_imported_mesh else "Scabbard Only"
    if mode not in CUSTOM_STL_PREVIEW_MODES:
        warnings.append("Unsupported STL preview mode was normalized to Scabbard Only.")
        mode = "Scabbard Only"
    return (
        CustomStlScabbardParameters(
            stl_path=safe_path,
            object_type=object_type,
            rotate_x_deg=_finite_float(rotate_x_deg, 0.0),
            rotate_y_deg=_finite_float(rotate_y_deg, 0.0),
            rotate_z_deg=_finite_float(rotate_z_deg, 0.0),
            scale=safe_scale,
            clearance_mm=clearance,
            wall_thickness_mm=wall,
            throat_length_mm=throat,
            split_mode=normalize_scabbard_split_mode(split_mode),
            seam_allowance_mm=seam,
            preview_mode=mode,
        ),
        warnings,
    )


def generate_custom_stl_scabbard_scad(**kwargs) -> tuple[str, list[str]]:
    """Return an experimental SCAD wrapper around a controlled blade-only STL import."""
    params, warnings = normalize_custom_stl_scabbard_parameters(**kwargs)
    if params is None:
        return "// Custom STL scabbard could not be generated safely.", warnings
    try:
        import_path = _scad_path_literal(params.stl_path)
    except ValueError as exc:
        return "// Custom STL scabbard could not be generated safely.", [str(exc)]
    if warnings and any("missing" in message.lower() for message in warnings):
        return "// Uploaded STL is missing; upload the blade STL again.", warnings

    clearance_radius = params.clearance_mm
    shell_radius = params.clearance_mm + params.wall_thickness_mm
    split = params.split_mode
    final_call = "custom_stl_scabbard_final();"
    if split != "Single Piece":
        axis = "x" if split == "Left/Right Halves" else "z"
        final_call = f"custom_stl_split_preview(\"{axis}\");"
    if params.preview_mode == "Imported Blade Only":
        top_level_call = "imported_blade_mesh();"
    elif params.preview_mode == "Blade Fit Diagnostic":
        top_level_call = f"""%color("silver", 0.35) imported_blade_mesh();
{final_call}"""
    else:
        top_level_call = final_call
    return f"""// Digital Forge Experimental STL-Derived Scabbard
// Status: experimental blade-only STL workflow.
// Requirements: watertight, manifold, correctly oriented blade mesh in the expected Digital Forge axis.
// OpenSCAD has no robust general mesh offset; this MVP uses minkowski() clearance around the imported mesh.
// Full sword STL files are intentionally unsupported because guard/grip/pommel geometry would create an invalid scabbard.
// Preview mode: {params.preview_mode}
// Final STL export contains only the hollow scabbard in Scabbard Only mode.
$fn = 32;
stl_scale = {params.scale:g};
stl_clearance_mm = {clearance_radius:g};
stl_shell_wall_mm = {params.wall_thickness_mm:g};
stl_shell_radius_mm = {shell_radius:g};
stl_seam_allowance_mm = {params.seam_allowance_mm:g};
stl_throat_length_mm = {params.throat_length_mm:g};
eps = {EPSILON_MM:g};

module imported_blade_mesh() {{
    // Controlled import, orientation, and scaling only. This module is a construction operand.
    rotate([{params.rotate_x_deg:g}, {params.rotate_y_deg:g}, {params.rotate_z_deg:g}])
        scale([stl_scale, stl_scale, stl_scale])
            import("{import_path}", convexity=8);
}}

module imported_blade_expanded(radius_mm) {{
    minkowski() {{
        imported_blade_mesh();
        sphere(r=radius_mm, $fn=24);
    }}
}}

module stl_inner_cavity() {{
    imported_blade_expanded(stl_clearance_mm);
}}

module stl_outer_volume() {{
    imported_blade_expanded(stl_shell_radius_mm);
}}

module stl_throat_opening_cut() {{
    // Expected blade axis is +Y. This removes the base cap and over-travels past the cavity.
    translate([0, -5000 + stl_throat_length_mm/2, 0])
        cube([10000, 10000 + stl_throat_length_mm, 10000], center=true);
}}

module stl_scabbard_raw_shell() {{
    difference() {{
        stl_outer_volume();
        stl_inner_cavity();
    }}
}}

module custom_stl_scabbard_final() {{
    difference() {{
        stl_scabbard_raw_shell();
        stl_throat_opening_cut();
    }}
}}

module custom_stl_split_preview(axis=\"x\") {{
    if (axis == \"x\") {{
        translate([-stl_shell_wall_mm*1.4, 0, 0])
            intersection() {{ custom_stl_scabbard_final(); translate([-5000-stl_seam_allowance_mm/2, 0, 0]) cube([10000, 10000, 10000], center=true); }}
        translate([stl_shell_wall_mm*1.4, 0, 0])
            intersection() {{ custom_stl_scabbard_final(); translate([5000+stl_seam_allowance_mm/2, 0, 0]) cube([10000, 10000, 10000], center=true); }}
    }} else {{
        translate([0, 0, -stl_shell_wall_mm*1.4])
            intersection() {{ custom_stl_scabbard_final(); translate([0, 0, -5000-stl_seam_allowance_mm/2]) cube([10000, 10000, 10000], center=true); }}
        translate([0, 0, stl_shell_wall_mm*1.4])
            intersection() {{ custom_stl_scabbard_final(); translate([0, 0, 5000+stl_seam_allowance_mm/2]) cube([10000, 10000, 10000], center=true); }}
    }}
}}

{top_level_call}
""", warnings
