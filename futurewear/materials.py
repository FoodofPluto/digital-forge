"""Prototype material and printer profiles for Futurewear connectors."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialProfile:
    name: str
    density_g_cm3: float
    minimum_wall_mm: float
    preferred_wall_mm: float
    minimum_edge_radius_mm: float
    default_fit_clearance_mm: float
    notes: tuple[str, ...]


@dataclass(frozen=True)
class PrintProfile:
    nozzle_diameter_mm: float = 0.4
    layer_height_mm: float = 0.2
    printer_compensation_mm: float = 0.0
    elephant_foot_compensation_mm: float = 0.0
    support_policy: str = "minimal"


MATERIAL_PROFILES: dict[str, MaterialProfile] = {
    "PLA": MaterialProfile(
        name="PLA",
        density_g_cm3=1.24,
        minimum_wall_mm=2.0,
        preferred_wall_mm=2.8,
        minimum_edge_radius_mm=0.6,
        default_fit_clearance_mm=0.30,
        notes=(
            "Prototype-friendly and dimensionally crisp.",
            "Can crack under repeated flexing; use physical tolerance coupons.",
        ),
    ),
    "PETG": MaterialProfile(
        name="PETG",
        density_g_cm3=1.27,
        minimum_wall_mm=2.2,
        preferred_wall_mm=3.0,
        minimum_edge_radius_mm=0.8,
        default_fit_clearance_mm=0.35,
        notes=(
            "Tougher than PLA for wearable prototypes.",
            "Stringing and slight over-extrusion can require looser fit coupons.",
        ),
    ),
}


def material_profile(name: str | None = None) -> MaterialProfile:
    value = str(name or "PLA").strip().upper()
    return MATERIAL_PROFILES.get(value, MATERIAL_PROFILES["PLA"])
