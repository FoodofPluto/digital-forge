"""Named, ready-to-generate configurations used by the preset gallery."""

from dataclasses import dataclass

from scad_generator import generate_scad
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS


@dataclass(frozen=True)
class ShowcasePreset:
    name: str
    sword_type: str
    blade_style: str
    guard_style: str
    pommel_style: str
    description: str
    fuller_enabled: bool = False
    ridge_enabled: bool = False

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "_")


SHOWCASE_PRESETS = (
    ShowcasePreset(
        "Straight Sword", "arming_sword", "tapered", "straight", "wheel",
        "A compact, balanced baseline with a simple crossguard.",
        fuller_enabled=True,
    ),
    ShowcasePreset(
        "Falchion", "falchion", "falchion", "downturned", "wheel",
        "A broad, forward-heavy chopping profile with a clipped point.",
    ),
    ShowcasePreset(
        "Curved Saber", "falchion", "curved", "downturned", "wheel",
        "A swept blade paired with a guard aligned to its curved profile.",
    ),
    ShowcasePreset(
        "Crescent Guard Sword", "longsword", "tapered", "crescent", "sphere",
        "A two-handed sword defined by a pronounced crescent guard.",
    ),
    ShowcasePreset(
        "Disk Guard Sword", "rapier", "needle", "disk", "wheel",
        "A narrow thrusting blade with a compact circular guard.",
        ridge_enabled=True,
    ),
    ShowcasePreset(
        "Spike Pommel Sword", "longsword", "tapered", "straight", "spike",
        "A classic longsword silhouette finished with a pointed pommel.",
    ),
    ShowcasePreset(
        "Leaf Blade Sword", "arming_sword", "leaf", "straight", "sphere",
        "A symmetrical leaf profile that widens before tapering to the point.",
        ridge_enabled=True,
    ),
)


def preset_metrics(preset: ShowcasePreset) -> dict[str, float]:
    """Return a fresh set of generator metrics for a showcase preset."""
    source = SWORD_PRESETS[preset.sword_type]
    return {name: source[name]["default"] for name in REQUIRED_METRICS}


def generate_showcase_scad(preset: ShowcasePreset) -> str:
    """Generate a gallery model through the same path as the main designer."""
    return generate_scad(
        preset.sword_type,
        preset_metrics(preset),
        preset.blade_style,
        preset.guard_style,
        preset.pommel_style,
        fuller_enabled=preset.fuller_enabled,
        ridge_enabled=preset.ridge_enabled,
    )
