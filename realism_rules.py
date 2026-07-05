"""Non-blocking realism checks for sword dimensions."""

from sword_presets import REQUIRED_METRICS, SWORD_PRESETS


def check_realism(
    sword_type: str,
    metrics: dict[str, float],
    fuller_enabled: bool = False,
    fuller_length_ratio: float = 0.65,
) -> list[str]:
    """Return friendly range and proportion warnings for a design."""
    if sword_type not in SWORD_PRESETS:
        return [f"No realism preset is available for '{sword_type}'."]

    warnings = []
    preset = SWORD_PRESETS[sword_type]
    for name in REQUIRED_METRICS:
        if name not in metrics:
            warnings.append(f"{name.replace('_', ' ').title()} is missing.")
            continue
        value = metrics[name]
        limits = preset[name]
        if value < limits["min"] or value > limits["max"]:
            label = name.replace("_mm", "").replace("_", " ").title()
            warnings.append(
                f"{label} ({value:g} mm) is outside the typical {sword_type.replace('_', ' ')} "
                f"range of {limits['min']:g}-{limits['max']:g} mm."
            )

    blade_length = metrics.get("blade_length_mm", 0)
    blade_width = metrics.get("blade_base_width_mm", 0)
    grip_length = metrics.get("grip_length_mm", 0)
    guard_width = metrics.get("guard_width_mm", 0)
    ricasso_length = metrics.get("ricasso_length_mm", 0)

    minimum_grip_ratio = 0.16 if sword_type in {"longsword", "greatsword"} else 0.09
    if blade_length > 0 and grip_length / blade_length < minimum_grip_ratio:
        warnings.append("The grip is unusually short relative to the blade and may not suit this sword type.")
    if blade_width > 0 and guard_width < blade_width * 2.5:
        warnings.append("The guard is narrow relative to the blade base and may offer little visual protection.")
    if sword_type == "rapier" and blade_width > 40:
        warnings.append("This blade is unusually wide for a rapier, which normally has a narrow thrusting profile.")
    if sword_type == "greatsword" and 0 < blade_length < 1000:
        warnings.append("This blade is short for a greatsword and may read as a longsword instead.")
    if sword_type == "dagger" and blade_length > 500:
        warnings.append("This dagger blade is unusually long and may read as a short sword.")
    if fuller_enabled and fuller_length_ratio > 1:
        warnings.append("The fuller length is longer than the blade; reduce its length ratio to 1.0 or less.")
    if blade_length > 0 and ricasso_length > blade_length * 0.25:
        warnings.append("The ricasso is unusually long relative to the blade.")
    return warnings

