"""Short, user-facing explanations of selected sword designs."""

TYPE_NOTES = {
    "arming_sword": "a one-handed grip and compact crossguard create a versatile sidearm silhouette",
    "longsword": "a two-handed grip and broad crossguard create a balanced cut-and-thrust silhouette",
    "greatsword": "the long blade, extended grip, and visible ricasso create a large two-handed silhouette",
    "dagger": "the short blade and one-handed grip create a compact close-range silhouette",
    "rapier": "the narrow blade and long reach create a thrust-oriented silhouette",
    "falchion": "the forward-heavy blade profile creates a chopping-oriented silhouette",
}


def get_design_notes(
    sword_type: str, blade_style: str, guard_style: str, pommel_style: str
) -> str:
    """Describe why a selected combination reads as its chosen sword type."""
    identity = TYPE_NOTES.get(sword_type, "its selected proportions create a distinct silhouette")
    return (
        f"This design reads as a {sword_type.replace('_', ' ')} because {identity}. "
        f"The {blade_style} blade, {guard_style} guard, and {pommel_style} pommel give it a clear decorative character."
    )
