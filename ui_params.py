"""Small UI parameter helpers kept separate from Streamlit rendering."""

from scad_generator import (
    BRACER_DETAIL_OPTIONS,
    PAULDRON_DETAIL_OPTIONS,
    DEFAULT_BRACER_METRICS,
    DEFAULT_PAULDRON_METRICS,
    normalize_armor_type,
    normalize_bracer_binding_style,
    normalize_bracer_detail_options,
    normalize_bracer_style,
    normalize_pauldron_detail_options,
    normalize_pauldron_style,
    resolve_bracer_metrics,
    resolve_pauldron_metrics,
)
from scabbard_generator import (
    DEFAULT_SCABBARD_CLEARANCE_MM,
    DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
    DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    normalize_scabbard_parameters,
)

GENERATION_CATEGORIES = ("Sword", "Scabbard", "Armor", "Futurewear")
DEFAULT_GENERATION_CATEGORY = "Sword"


def normalize_generation_category(category: str | None = None) -> str:
    """Return a supported generation category, defaulting to Sword."""
    normalized = str(category or DEFAULT_GENERATION_CATEGORY).strip().title()
    return normalized if normalized in GENERATION_CATEGORIES else DEFAULT_GENERATION_CATEGORY


def build_bracer_generation_params(
    armor_type: str = "Bracer",
    bracer_style: str = "Plain",
    metrics: dict[str, float] | None = None,
    detail_options: dict[str, bool] | None = None,
    bracer_binding_style: str = "None",
) -> tuple[dict[str, object], list[str]]:
    """Return normalized armor generation kwargs and non-fatal geometry warnings."""
    style = normalize_bracer_style(bracer_style)
    resolved_metrics, warnings = resolve_bracer_metrics(metrics or DEFAULT_BRACER_METRICS)
    return {
        "armor_type": normalize_armor_type(armor_type),
        "bracer_style": style,
        "metrics": resolved_metrics,
        "detail_options": normalize_bracer_detail_options(style, detail_options),
        "bracer_binding_style": normalize_bracer_binding_style(bracer_binding_style),
    }, warnings


BRACER_DECORATION_PRESETS = {
    "Plain": {"raised_panel": False},
    "Raised Design Panel": {"raised_panel": True},
}


def build_pauldron_generation_params(
    armor_type: str = "Pauldron",
    pauldron_style: str = "Knight",
    metrics: dict[str, float] | None = None,
    detail_options: dict[str, bool] | None = None,
) -> tuple[dict[str, object], list[str]]:
    """Return normalized pauldron generation kwargs and non-fatal geometry warnings."""
    style = normalize_pauldron_style(pauldron_style)
    resolved_metrics, warnings = resolve_pauldron_metrics(metrics or DEFAULT_PAULDRON_METRICS)
    return {
        "armor_type": normalize_armor_type(armor_type),
        "pauldron_style": style,
        "metrics": resolved_metrics,
        "detail_options": normalize_pauldron_detail_options(style, detail_options),
    }, warnings


def build_scabbard_generation_params(
    blade_type: str = "tapered",
    metrics: dict[str, float] | None = None,
    clearance_per_side_mm: float = DEFAULT_SCABBARD_CLEARANCE_MM,
    wall_thickness_mm: float = DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    split_mode: str = "Single Piece",
    throat_enabled: bool = True,
    end_cap_enabled: bool = True,
    fit_mode: str = "Fitted Scabbard",
    seam_allowance_mm: float = DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
) -> tuple[dict[str, object], list[str]]:
    """Return normalized scabbard generation kwargs and non-fatal clamp warnings."""
    params, warnings = normalize_scabbard_parameters(
        blade_type,
        metrics or {},
        clearance_per_side_mm,
        wall_thickness_mm,
        split_mode,
        throat_enabled,
        end_cap_enabled,
        fit_mode,
        seam_allowance_mm,
    )
    profile = params.blade_profile
    return {
        "blade_type": profile.blade_type,
        "sword_metrics": {
            "blade_length_mm": profile.length_mm,
            "blade_base_width_mm": profile.base_width_mm,
            "blade_tip_width_mm": profile.tip_width_mm,
            "blade_thickness_mm": profile.thickness_mm,
            "ricasso_length_mm": profile.ricasso_length_mm,
        },
        "clearance_per_side_mm": params.clearance_per_side_mm,
        "wall_thickness_mm": params.wall_thickness_mm,
        "split_mode": params.split_mode,
        "throat_enabled": params.throat_enabled,
        "end_cap_enabled": params.end_cap_enabled,
        "fit_mode": params.fit_mode,
        "seam_allowance_mm": params.seam_allowance_mm,
    }, warnings


def enabled_bracer_detail_labels(detail_options: dict[str, bool]) -> list[str]:
    """Return stable user-facing labels for enabled bracer detail flags."""
    labels = {"raised_panel": "Raised Design Panel"}
    normalized = {name: bool(detail_options.get(name, False)) for name in BRACER_DETAIL_OPTIONS}
    return [labels[name] for name in BRACER_DETAIL_OPTIONS if normalized[name]]


def enabled_pauldron_detail_labels(detail_options: dict[str, bool]) -> list[str]:
    """Return stable user-facing labels for enabled pauldron detail flags."""
    labels = {
        "raised_trim": "Raised trim",
        "rivets": "Rivets",
        "spikes": "Spikes",
        "runes": "Runes / motif",
    }
    normalized = {name: bool(detail_options.get(name, False)) for name in PAULDRON_DETAIL_OPTIONS}
    return [labels[name] for name in PAULDRON_DETAIL_OPTIONS if normalized[name]]
