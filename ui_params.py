"""Small UI parameter helpers kept separate from Streamlit rendering."""

from scad_generator import (
    BRACER_DETAIL_OPTIONS,
    PAULDRON_DETAIL_OPTIONS,
    DEFAULT_BRACER_METRICS,
    DEFAULT_PAULDRON_METRICS,
    normalize_armor_type,
    normalize_bracer_detail_options,
    normalize_bracer_style,
    normalize_pauldron_detail_options,
    normalize_pauldron_style,
    resolve_bracer_metrics,
    resolve_pauldron_metrics,
)

GENERATION_CATEGORIES = ("Sword", "Armor")
DEFAULT_GENERATION_CATEGORY = "Sword"


def normalize_generation_category(category: str | None = None) -> str:
    """Return a supported generation category, defaulting to Sword."""
    normalized = str(category or DEFAULT_GENERATION_CATEGORY).strip().title()
    return normalized if normalized in GENERATION_CATEGORIES else DEFAULT_GENERATION_CATEGORY


def build_bracer_generation_params(
    armor_type: str = "Bracer",
    bracer_style: str = "Knight",
    metrics: dict[str, float] | None = None,
    detail_options: dict[str, bool] | None = None,
) -> tuple[dict[str, object], list[str]]:
    """Return normalized armor generation kwargs and non-fatal geometry warnings."""
    style = normalize_bracer_style(bracer_style)
    resolved_metrics, warnings = resolve_bracer_metrics(metrics or DEFAULT_BRACER_METRICS)
    return {
        "armor_type": normalize_armor_type(armor_type),
        "bracer_style": style,
        "metrics": resolved_metrics,
        "detail_options": normalize_bracer_detail_options(style, detail_options),
    }, warnings


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


def enabled_bracer_detail_labels(detail_options: dict[str, bool]) -> list[str]:
    """Return stable user-facing labels for enabled bracer detail flags."""
    labels = {
        "raised_trim": "Raised trim",
        "rivets": "Rivets",
        "center_ridge": "Center ridge",
        "spikes": "Spikes",
        "runes": "Runes / motif",
    }
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
