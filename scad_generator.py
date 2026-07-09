"""Generate decorative OpenSCAD fantasy prop geometry."""

BLADE_STYLES = ("tapered", "leaf", "needle", "curved", "falchion")
GUARD_STYLES = ("straight", "crescent", "downturned", "disk")
POMMEL_STYLES = ("sphere", "wheel", "ring", "spike")
ARMOR_TYPES = ("Bracer", "Pauldron")
BRACER_STYLES = ("Knight", "Barbarian", "Elven")
BRACER_DETAIL_OPTIONS = ("raised_trim", "rivets", "center_ridge", "spikes", "runes")
DEFAULT_BRACER_METRICS = {
    "bracer_length_mm": 180.0,
    "wrist_width_mm": 70.0,
    "forearm_width_mm": 100.0,
    "bracer_thickness_mm": 4.0,
    "bracer_arc_degrees": 145.0,
}
PAULDRON_STYLES = ("Knight", "Barbarian", "Elven")
PAULDRON_DETAIL_OPTIONS = ("raised_trim", "rivets", "spikes", "runes")
DEFAULT_PAULDRON_METRICS = {
    "pauldron_width_mm": 160.0,
    "pauldron_depth_mm": 120.0,
    "pauldron_height_mm": 55.0,
    "plate_count": 4.0,
    "plate_overlap_mm": 14.0,
    "pauldron_thickness_mm": 4.0,
}
COMPONENT_NAMES = ("blade", "tang", "guard", "grip", "pommel")
FULL_COMPONENT_VISIBILITY = {name: True for name in COMPONENT_NAMES}
VISIBILITY_PRESETS = {
    "Full sword": FULL_COMPONENT_VISIBILITY,
    "Blade + tang only": {"blade": True, "tang": True, "guard": False, "grip": False, "pommel": False},
    "Handle assembly only": {"blade": False, "tang": True, "guard": False, "grip": True, "pommel": True},
    "Guard/hilt only": {"blade": False, "tang": False, "guard": True, "grip": False, "pommel": False},
    "Blade only": {"blade": True, "tang": False, "guard": False, "grip": False, "pommel": False},
    "Tang only": {"blade": False, "tang": True, "guard": False, "grip": False, "pommel": False},
}


def normalize_component_visibility(
    visible_components: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Return a complete visibility mapping; omitted values preserve the full sword."""
    visibility = dict(FULL_COMPONENT_VISIBILITY)
    if visible_components is not None:
        visibility.update(
            {name: bool(visible_components[name]) for name in COMPONENT_NAMES if name in visible_components}
        )
    return visibility


def has_visible_components(visible_components: dict[str, bool] | None = None) -> bool:
    """Return whether the normalized assembly contains at least one component."""
    return any(normalize_component_visibility(visible_components).values())


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Return value constrained to the inclusive range."""
    return max(minimum, min(value, maximum))


def _finite_float(value: object, fallback: float) -> float:
    """Return a finite float, falling back for non-numeric inputs."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number and number not in (float("inf"), float("-inf")) else fallback


def normalize_bracer_style(bracer_style: str = "Knight") -> str:
    """Return a supported bracer style name."""
    normalized = str(bracer_style or "Knight").strip().title()
    return normalized if normalized in BRACER_STYLES else "Knight"


def normalize_pauldron_style(pauldron_style: str = "Knight") -> str:
    """Return a supported pauldron style name."""
    normalized = str(pauldron_style or "Knight").strip().title()
    return normalized if normalized in PAULDRON_STYLES else "Knight"


def normalize_armor_type(armor_type: str = "Bracer") -> str:
    """Return a supported armor type name."""
    normalized = str(armor_type or "Bracer").strip().title()
    return normalized if normalized in ARMOR_TYPES else "Bracer"


def normalize_bracer_detail_options(
    bracer_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Return complete bracer detail flags with style-aware defaults."""
    style = normalize_bracer_style(bracer_style)
    defaults = {
        "raised_trim": True,
        "rivets": style == "Barbarian",
        "center_ridge": style == "Knight",
        "spikes": False,
        "runes": style == "Elven",
    }
    if detail_options:
        defaults.update({name: bool(detail_options[name]) for name in BRACER_DETAIL_OPTIONS if name in detail_options})
    return defaults


def normalize_pauldron_detail_options(
    pauldron_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Return complete pauldron detail flags with style-aware defaults."""
    style = normalize_pauldron_style(pauldron_style)
    defaults = {
        "raised_trim": True,
        "rivets": style == "Barbarian",
        "spikes": style == "Barbarian",
        "runes": style == "Elven",
    }
    if detail_options:
        defaults.update({name: bool(detail_options[name]) for name in PAULDRON_DETAIL_OPTIONS if name in detail_options})
    return defaults


def resolve_bracer_metrics(metrics: dict[str, float] | None = None) -> tuple[dict[str, float], list[str]]:
    """Clamp decorative bracer dimensions and report non-fatal warnings."""
    source = dict(DEFAULT_BRACER_METRICS)
    if metrics:
        source.update(metrics)
    warnings: list[str] = []

    length = clamp(_finite_float(source.get("bracer_length_mm"), 180.0), 60.0, 420.0)
    wrist = clamp(_finite_float(source.get("wrist_width_mm"), 70.0), 35.0, 180.0)
    forearm = clamp(_finite_float(source.get("forearm_width_mm"), 100.0), 45.0, 240.0)
    thickness = clamp(_finite_float(source.get("bracer_thickness_mm"), 4.0), 2.4, 12.0)
    arc = clamp(_finite_float(source.get("bracer_arc_degrees"), 145.0), 80.0, 220.0)

    requested = {
        "bracer_length_mm": source.get("bracer_length_mm"),
        "wrist_width_mm": source.get("wrist_width_mm"),
        "forearm_width_mm": source.get("forearm_width_mm"),
        "bracer_thickness_mm": source.get("bracer_thickness_mm"),
        "bracer_arc_degrees": source.get("bracer_arc_degrees"),
    }
    resolved = {
        "bracer_length_mm": length,
        "wrist_width_mm": wrist,
        "forearm_width_mm": forearm,
        "bracer_thickness_mm": thickness,
        "bracer_arc_degrees": arc,
    }
    for name, value in resolved.items():
        if _finite_float(requested[name], DEFAULT_BRACER_METRICS[name]) != value:
            warnings.append(f"{name} was clamped to {value:g}.")

    if wrist > forearm:
        warnings.append("wrist_width_mm was clamped to forearm_width_mm so the bracer tapers outward.")
        wrist = forearm
        resolved["wrist_width_mm"] = wrist

    trim_width = clamp(length * 0.075, 6.0, 18.0)
    panel_length = max(12.0, length - trim_width * 3.4)
    resolved.update(
        bracer_trim_width_mm=trim_width,
        bracer_panel_length_mm=panel_length,
        bracer_panel_width_mm=clamp(min(wrist, forearm) * 0.34, 14.0, 48.0),
        bracer_rivet_diameter_mm=clamp(thickness * 1.45, 3.2, 10.0),
    )
    return resolved, warnings


def resolve_pauldron_metrics(metrics: dict[str, float] | None = None) -> tuple[dict[str, float], list[str]]:
    """Clamp decorative pauldron dimensions and report non-fatal warnings."""
    source = dict(DEFAULT_PAULDRON_METRICS)
    if metrics:
        source.update(metrics)
    warnings: list[str] = []

    width = clamp(_finite_float(source.get("pauldron_width_mm"), 160.0), 70.0, 320.0)
    depth = clamp(_finite_float(source.get("pauldron_depth_mm"), 120.0), 55.0, 260.0)
    height = clamp(_finite_float(source.get("pauldron_height_mm"), 55.0), 18.0, 130.0)
    plate_count = int(clamp(round(_finite_float(source.get("plate_count"), 4.0)), 2.0, 8.0))
    overlap = clamp(_finite_float(source.get("plate_overlap_mm"), 14.0), 4.0, 45.0)
    thickness = clamp(_finite_float(source.get("pauldron_thickness_mm"), 4.0), 2.4, 12.0)

    requested = {
        "pauldron_width_mm": source.get("pauldron_width_mm"),
        "pauldron_depth_mm": source.get("pauldron_depth_mm"),
        "pauldron_height_mm": source.get("pauldron_height_mm"),
        "plate_count": source.get("plate_count"),
        "plate_overlap_mm": source.get("plate_overlap_mm"),
        "pauldron_thickness_mm": source.get("pauldron_thickness_mm"),
    }
    resolved = {
        "pauldron_width_mm": width,
        "pauldron_depth_mm": depth,
        "pauldron_height_mm": height,
        "plate_count": plate_count,
        "plate_overlap_mm": overlap,
        "pauldron_thickness_mm": thickness,
    }
    for name, value in resolved.items():
        fallback = DEFAULT_PAULDRON_METRICS[name]
        requested_value = round(_finite_float(requested[name], fallback)) if name == "plate_count" else _finite_float(requested[name], fallback)
        if requested_value != value:
            warnings.append(f"{name} was clamped to {value:g}.")

    plate_depth = (depth + overlap * (plate_count - 1)) / plate_count
    min_overlap = max(4.0, thickness * 1.4)
    if overlap >= plate_depth * 0.72:
        overlap = plate_depth * 0.55
        resolved["plate_overlap_mm"] = overlap
        warnings.append(f"plate_overlap_mm was reduced to {overlap:g} so layered plates remain readable.")
    elif overlap < min_overlap:
        overlap = min_overlap
        resolved["plate_overlap_mm"] = overlap
        warnings.append(f"plate_overlap_mm was increased to {overlap:g} so plates visually connect.")
    plate_depth = (depth + overlap * (plate_count - 1)) / plate_count
    resolved.update(
        pauldron_plate_depth_mm=plate_depth,
        pauldron_plate_step_mm=max(1.0, plate_depth - overlap),
        pauldron_rivet_diameter_mm=clamp(thickness * 1.55, 3.2, 11.0),
        pauldron_spike_height_mm=clamp(thickness * 3.2, 8.0, min(32.0, height * 0.45)),
    )
    return resolved, warnings


def disk_guard_diameter(metrics: dict[str, float]) -> float:
    """Calculate a useful disk diameter without inheriting extreme preset widths."""
    blade_width = max(0.0, metrics.get("blade_base_width_mm", 0.0))
    requested = max(0.0, metrics.get("guard_width_mm", 0.0))
    if blade_width <= 0:
        return 0.0
    return clamp(requested, blade_width * 1.5, blade_width * 3.25)


def guard_should_rotate_90(sword_type: str, blade_style: str) -> bool:
    """Return whether the guard should turn around the sword's main axis."""
    return sword_type.lower() == "falchion" or blade_style.lower() in {"falchion", "curved"}


def get_guard_rotation(sword_type: str, blade_style: str) -> int:
    """Return the guard rotation around the +Y sword axis in degrees."""
    return 90 if guard_should_rotate_90(sword_type, blade_style) else 0


def centered_peg_hole_positions(
    tang_length_mm: float,
    peg_hole_count: int,
    peg_hole_diameter_mm: float,
    blade_side_exclusion_mm: float = 0.0,
    requested_spacing_mm: float | None = None,
) -> list[float]:
    """Return hole-center offsets from the tang top, centered in its usable handle region."""
    count = max(0, min(int(peg_hole_count), 3))
    if count == 0:
        return []
    margin = max(float(peg_hole_diameter_mm), 2.0)
    usable_start = min(float(tang_length_mm), max(0.0, blade_side_exclusion_mm) + margin)
    usable_end = max(usable_start, float(tang_length_mm) - margin)
    center = (usable_start + usable_end) / 2
    if count == 1:
        return [center]
    max_spacing = max(0.0, (usable_end - usable_start) / (count - 1))
    default_spacing = max_spacing * 0.72
    spacing = clamp(
        default_spacing if requested_spacing_mm is None else float(requested_spacing_mm),
        min(float(peg_hole_diameter_mm), max_spacing),
        max_spacing,
    )
    group_start = center - spacing * (count - 1) / 2
    return [group_start + index * spacing for index in range(count)]


def blade_detail_bounds(
    blade_length_mm: float, ricasso_length_mm: float, length_ratio: float, blade_style: str
) -> tuple[float, float]:
    """Return conservative blade-local Y bounds for attached decorative details."""
    blade_length = max(1.0, float(blade_length_mm))
    ricasso = clamp(float(ricasso_length_mm), 0.0, blade_length * 0.8)
    body_length = max(1.0, blade_length - ricasso)
    start = min(blade_length, ricasso + max(2.0, body_length * 0.04))
    ratio = clamp(float(length_ratio), 0.35, 0.90)
    tip_margin = max(3.0, body_length * 0.08)
    end = min(blade_length - tip_margin, start + body_length * ratio)
    return start, max(start, end)


def compute_blade_detail_corridor(
    blade_width_mm: float, blade_length_mm: float = 0.0, blade_style: str = "tapered"
) -> tuple[float, float]:
    """Return a conservative (center, width) corridor for long blade details."""
    width = max(1.0, float(blade_width_mm))
    length_factor = clamp(float(blade_length_mm) / (width * 8), 0.72, 1.0) if blade_length_mm else 1.0
    if blade_style == "curved":
        return 0.0, width * 0.42 * length_factor
    if blade_style == "falchion":
        return 0.0, width * 0.46 * length_factor
    if blade_style == "needle":
        return 0.0, width * 0.34 * length_factor
    return 0.0, width * 0.50 * length_factor


def blade_detail_offset_for_position(
    position: str, blade_width_mm: float, blade_length_mm: float = 0.0,
    blade_style: str = "tapered",
) -> float:
    """Map the compact UI position labels to conservative X offsets."""
    center, corridor_width = compute_blade_detail_corridor(
        blade_width_mm, blade_length_mm, blade_style
    )
    offsets = {"Center": 0.0, "Slight left": -0.32, "Slight right": 0.32}
    return center + corridor_width * offsets.get(position, 0.0)


def clamp_blade_detail_offset(
    blade_width_mm: float, requested_offset_x: float, feature_width_mm: float,
    blade_length_mm: float = 0.0, blade_style: str = "tapered",
) -> float:
    """Keep a detail near the blade center with room for its own half-width."""
    corridor_center, corridor_width = compute_blade_detail_corridor(
        blade_width_mm, blade_length_mm, blade_style
    )
    feature_half_width = max(0.0, float(feature_width_mm)) / 2
    travel = max(0.0, corridor_width / 2 - feature_half_width)
    return clamp(float(requested_offset_x), corridor_center - travel, corridor_center + travel)


def resolve_fuller_dimensions(
    blade_width_mm: float, blade_thickness_mm: float,
    fuller_width_mm: float = 12.0, fuller_depth_mm: float = 0.8,
) -> tuple[float, float]:
    """Clamp a visible groove safely inside the prop blade cross-section."""
    width = max(1.0, float(blade_width_mm))
    thickness = max(2.4, float(blade_thickness_mm))
    safe_width = clamp(float(fuller_width_mm), 1.0, width * 0.42)
    safe_depth = clamp(float(fuller_depth_mm), 0.35, thickness * 0.28)
    return safe_width, safe_depth


def resolve_tang_details(metrics: dict[str, float]) -> dict[str, float]:
    """Return bounded, prop-scale tang and peg-hole dimensions."""
    grip_length = max(1.0, float(metrics.get("grip_length_mm", 1.0)))
    grip_width = max(1.0, float(metrics.get("grip_width_mm", 1.0)))
    blade_width = max(1.0, float(metrics.get("blade_base_width_mm", 1.0)))
    blade_thickness = max(1.0, float(metrics.get("blade_thickness_mm", 1.0)))
    grip_depth = max(blade_thickness * 1.8, grip_width * 0.68)

    default_length = grip_length * 0.9
    default_width = min(blade_width * 0.55, grip_width * 0.52)
    default_thickness = min(max(2.4, blade_thickness * 0.72), grip_depth * 0.55)
    tang_length = clamp(float(metrics.get("tang_length_mm", default_length)), 1.0, grip_length * 0.98)
    tang_width = clamp(float(metrics.get("tang_width_mm", default_width)), 1.0, grip_width * 0.9)
    tang_thickness = clamp(
        float(metrics.get("tang_thickness_mm", default_thickness)), 1.0, grip_depth * 0.9
    )

    count = int(clamp(int(metrics.get("peg_hole_count", 0)), 0, 3))
    guard_height = max(0.0, float(metrics.get("guard_height_mm", 0.0)))
    ricasso_length = max(0.0, float(metrics.get("ricasso_length_mm", 0.0)))
    tang_blade_overlap = max(3.0, min(ricasso_length, blade_width * 0.5))
    blade_side_exclusion = min(tang_length * 0.45, guard_height + tang_blade_overlap)
    preliminary_usable = max(0.0, tang_length - blade_side_exclusion - 4.0)
    max_diameter = max(0.0, min(tang_width * 0.55, preliminary_usable / max(1, count) * 0.6))
    diameter = clamp(float(metrics.get("peg_hole_diameter_mm", 4.0)), 0.0, max_diameter)
    positions = centered_peg_hole_positions(
        tang_length, count, diameter, blade_side_exclusion,
        metrics.get("peg_hole_spacing_mm") if "peg_hole_spacing_mm" in metrics else None,
    )
    spacing = positions[1] - positions[0] if len(positions) > 1 else 0.0
    offset = positions[0] if positions else 0.0
    return {
        "grip_depth_mm": grip_depth,
        "tang_length_mm": tang_length,
        "tang_width_mm": tang_width,
        "tang_thickness_mm": tang_thickness,
        "peg_hole_count": count,
        "peg_hole_diameter_mm": diameter,
        "peg_hole_spacing_mm": spacing,
        "peg_hole_offset_from_guard_mm": offset,
        "peg_hole_positions_mm": positions,
        "peg_hole_usable_start_mm": blade_side_exclusion + max(diameter, 2.0),
        "peg_hole_usable_end_mm": tang_length - max(diameter, 2.0),
    }


def _blade_polygon(style: str) -> str:
    profiles = {
        "tapered": """[[-blade_base_width_mm/2, ricasso_length_mm],
        [-prop_tip_width_mm/2, blade_length_mm], [prop_tip_width_mm/2, blade_length_mm],
        [blade_base_width_mm/2, ricasso_length_mm]]""",
        "leaf": """[[-blade_base_width_mm/2, ricasso_length_mm],
        [-blade_base_width_mm*0.42, blade_length_mm*0.42],
        [-blade_base_width_mm*0.64, blade_length_mm*0.70],
        [-prop_tip_width_mm/2, blade_length_mm], [prop_tip_width_mm/2, blade_length_mm],
        [blade_base_width_mm*0.64, blade_length_mm*0.70],
        [blade_base_width_mm*0.42, blade_length_mm*0.42],
        [blade_base_width_mm/2, ricasso_length_mm]]""",
        "needle": """[[-blade_base_width_mm/2, ricasso_length_mm],
        [-blade_tip_width_mm, blade_length_mm*0.72],
        [-prop_tip_width_mm/2, blade_length_mm], [prop_tip_width_mm/2, blade_length_mm],
        [blade_tip_width_mm, blade_length_mm*0.72],
        [blade_base_width_mm/2, ricasso_length_mm]]""",
        # Both edges sweep toward +X, producing an obvious sabre-like curve.
        "curved": """[[-blade_base_width_mm*0.50, ricasso_length_mm],
        [-blade_base_width_mm*0.38, blade_length_mm*0.30],
        [-blade_base_width_mm*0.12, blade_length_mm*0.62],
        [blade_base_width_mm*0.38, blade_length_mm*0.88],
        [blade_base_width_mm*0.72, blade_length_mm],
        [blade_base_width_mm*0.80, blade_length_mm*0.84],
        [blade_base_width_mm*0.62, blade_length_mm*0.55],
        [blade_base_width_mm*0.50, ricasso_length_mm]]""",
        # Decorative forward-heavy falchion with an expanded belly and clipped point.
        "falchion": """[[-blade_base_width_mm*0.42, ricasso_length_mm],
        [-blade_base_width_mm*0.44, blade_length_mm*0.38],
        [-blade_base_width_mm*0.58, blade_length_mm*0.66],
        [-blade_base_width_mm*0.78, blade_length_mm*0.84],
        [-blade_base_width_mm*0.70, blade_length_mm*0.96],
        [-blade_base_width_mm*0.22, blade_length_mm],
        [blade_base_width_mm*0.58, blade_length_mm*0.88],
        [blade_base_width_mm*0.68, blade_length_mm*0.72],
        [blade_base_width_mm*0.52, blade_length_mm*0.40],
        [blade_base_width_mm*0.42, ricasso_length_mm]]""",
    }
    if style not in profiles:
        raise ValueError(f"Unknown blade style: {style}")
    return profiles[style]


def _guard_geometry(style: str) -> str:
    guards = {
        "straight": """// Straight guard: softened capsule bar centered across X.
        rounded_guard_bar(guard_width_mm, guard_height_mm);""",
        "crescent": """// Pronounced crescent stays inside the guard's Y contact envelope.
        difference() {
            scale([1.18, guard_height_mm/guard_width_mm, 1])
                cylinder(h=guard_height_mm, d=guard_width_mm, center=true);
            translate([0, guard_height_mm*0.42, 0])
                scale([0.68, guard_height_mm/guard_width_mm, 1])
                    cylinder(h=guard_height_mm*2, d=guard_width_mm*1.08, center=true);
        }
        cube([grip_width_mm*1.3, guard_height_mm, guard_height_mm], center=true);""",
        "downturned": """// Downturned guard arms sweep toward +Y and the blade.
        for (side=[-1, 1])
            translate([side*guard_width_mm/4, guard_width_mm*0.10, 0])
                rotate([0, 0, side*24])
                    cube([guard_width_mm/2, guard_height_mm, guard_height_mm], center=true);
        sphere(d=guard_height_mm*1.45);""",
        "disk": """// Disk guard: diameter is capped by Python; thin axis follows +Y.
        // It is centered between the grip and blade.
        rotate([90, 0, 0])
            cylinder(h=guard_height_mm, d=disk_guard_diameter_mm, center=true);
        rotate([90, 0, 0])
            cylinder(h=guard_height_mm*1.05, d=grip_width_mm*1.45, center=true);""",
    }
    if style not in guards:
        raise ValueError(f"Unknown guard style: {style}")
    return guards[style]


def _pommel_geometry(style: str) -> str:
    pommels = {
        "sphere": "sphere(d=pommel_size_mm);",
        "wheel": "cylinder(h=pommel_size_mm*0.42, d=pommel_size_mm, center=true);",
        "ring": """difference() {
            cylinder(h=pommel_size_mm*0.34, d=pommel_size_mm, center=true);
            cylinder(h=pommel_size_mm, d=pommel_size_mm*0.52, center=true);
        }""",
        "spike": """// Local Y=0 is the attachment face; point extends toward -Y.
        rotate([90, 0, 0])
            cylinder(h=pommel_size_mm, r1=pommel_size_mm*0.42, r2=0);
        translate([0, -pommel_size_mm*0.24, 0]) sphere(d=pommel_size_mm*0.48);""",
    }
    if style not in pommels:
        raise ValueError(f"Unknown pommel style: {style}")
    return pommels[style]


def make_blade(blade_style: str, fuller_enabled: bool, ridge_enabled: bool) -> str:
    """Return blade modules rooted at local Y=0."""
    fuller = ""
    fuller_call = ""
    if fuller_enabled:
        if blade_style == "curved":
            path_functions = """// Curved blade: quadratic sweep follows the midpoint between its edges.
function fuller_center_x(y) = blade_base_width_mm*0.82*pow(y/blade_length_mm, 2);
function fuller_local_half_width(y) = blade_base_width_mm*(0.50-0.48*(y/blade_length_mm));"""
        elif blade_style == "falchion":
            path_functions = """// Falchion: center follows the forward-heavy local blade corridor.
function fuller_center_x(y) = let(t=y/blade_length_mm)
    blade_base_width_mm*(t <= 0.66 ? 0.08*t : t <= 0.84 ? 0.0528-0.85*(t-0.66) : -0.1002+1.25*(t-0.84));
function fuller_local_half_width(y) = let(t=y/blade_length_mm)
    blade_base_width_mm*(t <= 0.66 ? 0.42+0.12*t : t <= 0.84 ? 0.499+1.0*(t-0.66) : 0.679-3.0*(t-0.84));"""
        else:
            path_functions = """// Symmetric profiles remain on their predictable centerline.
function fuller_center_x(y) = 0;
function fuller_local_half_width(y) = blade_base_width_mm*(0.50-0.32*(y/blade_length_mm));"""
        fuller = "\n" + path_functions + """
function fuller_path_x(y) = fuller_center_x(y)
    + fuller_offset_ratio*2*fuller_local_half_width(y);
function fuller_diameter_at(y) = max(1, min(fuller_width_mm,
    2*(fuller_local_half_width(y)-abs(fuller_path_x(y)-fuller_center_x(y)))-2));
module fuller_geometry() {
    fuller_samples = 18;
    // Rounded capsule cutters are sampled into segments along the local blade centerline. The profile
    // intersection clips the cutter at both edges and the safe Y bounds.
    for (face=[-1, 1])
        intersection() {
            linear_extrude(height=prop_blade_thickness_mm*2, center=true) blade_profile_2d();
            for (sample=[0:fuller_samples-1]) hull()
                for (step=[0, 1])
                    let(y=blade_detail_start_y+fuller_width_mm/2
                        +(blade_detail_end_y-blade_detail_start_y-fuller_width_mm)
                        *(sample+step)/fuller_samples,
                        local_d=fuller_diameter_at(y))
                        translate([fuller_path_x(y), y, face*prop_blade_thickness_mm/2])
                            scale([1, 1, fuller_depth_mm/(local_d/2)])
                                sphere(d=local_d);
        }
}
"""
        fuller_call = "fuller_geometry();"

    ridge = ""
    ridge_call = ""
    if ridge_enabled:
        ridge = """
module ridge_geometry() {
    ridge_height = max(0.6, prop_blade_thickness_mm*0.16);
    translate([0, 0, prop_blade_thickness_mm/2-0.15])
        linear_extrude(height=ridge_height+0.15)
            intersection() {
                blade_profile_2d();
                translate([ridge_offset_x, 0])
                    polygon([[-blade_base_width_mm*0.07, blade_detail_start_y],
                             [0, blade_detail_end_y],
                             [blade_base_width_mm*0.07, blade_detail_start_y]]);
            }
}
"""
        ridge_call = "ridge_geometry();"

    profile_marker = (
        "// Falchion profile: forward-heavy belly with angled clipped point."
        if blade_style == "falchion" else ""
    )
    return f"""{profile_marker}
module blade_profile_2d() {{
    union() {{
        if (ricasso_length_mm > 0)
            translate([0, ricasso_length_mm/2])
                square([blade_base_width_mm, ricasso_length_mm], center=true);
        polygon({_blade_polygon(blade_style)});
    }}
}}
{fuller}{ridge}
module blade() {{
    color("silver") union() {{
        difference() {{
            // A minimum Z thickness and capped 2D tip keep this a blunt printable prop.
            linear_extrude(height=prop_blade_thickness_mm, center=true) blade_profile_2d();
            {fuller_call}
        }}
        {ridge_call}
    }}
}}
"""


def make_guard(guard_style: str) -> str:
    """Return guard geometry centered on the local origin."""
    return f"""module rounded_guard_bar(width, diameter) {{
    hull() {{
        for (side=[-1, 1]) translate([side*(width-diameter)/2, 0, 0])
            sphere(d=diameter);
    }}
}}

module guard() {{
    color("gainsboro") union() {{ {_guard_geometry(guard_style)} }}
}}
"""


def make_grip() -> str:
    """Return a grip module whose local Y extent is centered."""
    return """module grip() {
    // Elliptical sword grip: wider across X, thinner front-to-back along Z.
    color("saddlebrown") rotate([90, 0, 0])
        scale([1, grip_depth_mm/grip_width_mm, 1])
            cylinder(h=grip_length_mm, d=grip_width_mm, center=true);
}
"""


def make_tang(peg_hole_count: int = 0) -> str:
    """Return the decorative internal core joining blade, guard, and grip."""
    if peg_hole_count <= 0:
        return """module tang_core() {
    // Non-functional prop core; the external oval grip encloses this geometry.
    color("dimgray") cube([tang_width_mm, tang_length_mm, tang_thickness_mm], center=true);
}
"""
    return """module tang_core() {
    // Non-functional prop core; the external oval grip encloses this geometry.
    color("dimgray") difference() {
        cube([tang_width_mm, tang_length_mm, tang_thickness_mm], center=true);
        for (peg_index=[0:peg_hole_count-1])
            translate([0, tang_length_mm/2-peg_hole_offset_from_guard_mm-
                peg_index*peg_hole_spacing_mm, 0])
                cylinder(h=tang_thickness_mm+2, d=peg_hole_diameter_mm, center=true);
    }
}
"""


def make_pommel(pommel_style: str) -> str:
    """Return pommel geometry; spike is rooted at its top, others are centered."""
    return f"""module pommel() {{
    color("silver") union() {{ {_pommel_geometry(pommel_style)} }}
}}
"""


def make_debug_markers(include_bounds: bool = True) -> str:
    """Return translucent anchor, centerline, and optional part-bound markers."""
    bounds = """
    // DEBUG BOUNDS: translucent envelopes for blade, guard, grip, and pommel.
    color([0.2, 0.6, 1.0, 0.16])
        translate([0, blade_start_y+blade_length_mm/2, 0])
            cube([blade_base_width_mm, blade_length_mm, blade_thickness_mm*1.8], center=true);
    color([1.0, 0.6, 0.1, 0.18])
        translate([0, guard_center_y, 0])
            cube([effective_guard_width_mm, guard_height_mm, guard_height_mm*1.8], center=true);
    color([0.5, 0.25, 0.1, 0.18])
        translate([0, (grip_start_y+grip_end_y)/2, 0])
            cube([grip_width_mm, grip_length_mm, grip_depth_mm*1.5], center=true);
    color([0.7, 0.2, 1.0, 0.18])
        translate([0, pommel_center_y, 0]) sphere(d=pommel_size_mm*1.08);
""" if include_bounds else ""
    return f"""module debug_anchor(y, marker_color) {{
    color(marker_color) translate([0, y, max(blade_thickness_mm, grip_width_mm)/2+3])
        sphere(d=6);
}}

module debug_markers() {{
    // DEBUG CENTERLINE and named Y-axis assembly anchors.
    color([1, 0, 0, 0.7])
        translate([0, (pommel_bottom_y+blade_tip_y)/2, 0])
            cube([1.2, blade_tip_y-pommel_bottom_y, 1.2], center=true);
    debug_anchor(blade_start_y, "lime");
    debug_anchor(guard_center_y, "orange");
    debug_anchor(grip_start_y, "cyan");
    debug_anchor(grip_end_y, "cyan");
    debug_anchor(pommel_center_y, "magenta");
{bounds}}}
"""


def _bracer_style_geometry(style: str) -> str:
    """Return style-specific decorative bracer features."""
    if style == "Barbarian":
        return """// Barbarian style: heavier side ribs and oversized raised rivets.
    bracer_plate_patch(bracer_length_mm/2, bracer_panel_length_mm*0.72,
        bracer_panel_width_mm*1.12, bracer_thickness_mm*0.44);
    for (side=[-1, 1])
        for (y=[bracer_trim_width_mm*1.6, bracer_length_mm/2, bracer_length_mm-bracer_trim_width_mm*1.6])
            bracer_surface_detail(side*bracer_panel_width_mm*0.95, y, bracer_rivet_diameter_mm,
                bracer_rivet_diameter_mm*0.45);
    for (side=[-1, 1])
        bracer_long_bar(side*bracer_panel_width_mm*0.55, bracer_length_mm/2,
            bracer_panel_length_mm*0.78, bracer_thickness_mm*0.95, bracer_thickness_mm*0.55);"""
    if style == "Elven":
        return """// Elven style: slim leaf-like raised center motif.
    bracer_plate_patch(bracer_length_mm/2, bracer_panel_length_mm*0.80,
        bracer_panel_width_mm*0.72, bracer_thickness_mm*0.30);
    hull() {
        bracer_surface_detail(0, bracer_length_mm*0.20, bracer_thickness_mm*1.2, bracer_thickness_mm*0.42);
        bracer_surface_detail(-bracer_panel_width_mm*0.42, bracer_length_mm*0.50,
            bracer_thickness_mm*1.1, bracer_thickness_mm*0.35);
        bracer_surface_detail(0, bracer_length_mm*0.82, bracer_thickness_mm*1.0, bracer_thickness_mm*0.35);
    }
    hull() {
        bracer_surface_detail(0, bracer_length_mm*0.20, bracer_thickness_mm*1.2, bracer_thickness_mm*0.42);
        bracer_surface_detail(bracer_panel_width_mm*0.42, bracer_length_mm*0.50,
            bracer_thickness_mm*1.1, bracer_thickness_mm*0.35);
        bracer_surface_detail(0, bracer_length_mm*0.82, bracer_thickness_mm*1.0, bracer_thickness_mm*0.35);
    }"""
    return """// Knight style: clean raised center plate and crisp central ridge.
    bracer_plate_patch(bracer_length_mm/2, bracer_panel_length_mm,
        bracer_panel_width_mm, bracer_thickness_mm*0.40);
    bracer_long_bar(0, bracer_length_mm/2, bracer_panel_length_mm*0.92,
        bracer_thickness_mm*1.05, bracer_thickness_mm*1.05);"""


def _bracer_detail_geometry(detail_options: dict[str, bool]) -> str:
    """Return optional detail geometry selected by UI flags."""
    details: list[str] = []
    if detail_options["center_ridge"]:
        details.append("""// Optional center ridge detail.
        bracer_long_bar(0, bracer_length_mm/2, bracer_panel_length_mm*0.88,
            bracer_thickness_mm*0.95, bracer_thickness_mm*0.95);""")
    if detail_options["rivets"]:
        details.append("""// Optional rivet detail.
        for (side=[-1, 1])
            for (y=[bracer_trim_width_mm*1.7, bracer_length_mm*0.38,
                    bracer_length_mm*0.62, bracer_length_mm-bracer_trim_width_mm*1.7])
                bracer_surface_detail(side*bracer_panel_width_mm*1.18, y,
                    bracer_rivet_diameter_mm, bracer_rivet_diameter_mm*0.38);""")
    if detail_options["spikes"]:
        details.append("""// Optional blunt fantasy spike detail.
        for (y=[bracer_length_mm*0.34, bracer_length_mm*0.5, bracer_length_mm*0.66])
            translate([0, y, bracer_surface_z(0, y)+bracer_thickness_mm/2])
                cylinder(h=bracer_thickness_mm*2.2,
                    r1=bracer_thickness_mm*0.85, r2=bracer_thickness_mm*0.22);""")
    if detail_options["runes"]:
        details.append("""// Optional raised rune-like decorative motif.
        for (index=[-1, 0, 1])
            translate([index*bracer_panel_width_mm*0.32, bracer_length_mm*0.52,
                    bracer_surface_z(index*bracer_panel_width_mm*0.32, bracer_length_mm*0.52)
                    + bracer_thickness_mm/2])
                rotate([0, 0, 45-index*18])
                    cube([bracer_thickness_mm*0.55, bracer_panel_width_mm*0.62,
                        bracer_thickness_mm*0.42], center=true);""")
    return "\n".join(details) if details else "// No optional bracer details selected."


def make_bracer(bracer_style: str, detail_options: dict[str, bool] | None = None) -> str:
    """Return tapered decorative bracer modules rooted from wrist Y=0 to forearm +Y."""
    style = normalize_bracer_style(bracer_style)
    details = normalize_bracer_detail_options(style, detail_options)
    trim_calls = (
        """bracer_trim_band(bracer_trim_width_mm/2);
        bracer_trim_band(bracer_length_mm-bracer_trim_width_mm/2);"""
        if details["raised_trim"] else "// Raised trim disabled."
    )
    return f"""function bracer_width_at(y) = wrist_width_mm
    + (forearm_width_mm-wrist_width_mm) * y / bracer_length_mm;
function bracer_radius_at(y) = max(1, (bracer_width_at(y)/2)
    / sin(bracer_arc_degrees/2));
function bracer_surface_z(x, y) = let(width=bracer_width_at(y),
    radius=bracer_radius_at(y),
    limited_x=max(-width*0.49, min(width*0.49, x)))
    sqrt(max(0, radius*radius-limited_x*limited_x))
    - radius*cos(bracer_arc_degrees/2);

module bracer_surface_detail(x, y, diameter, height) {{
    translate([x, y, bracer_surface_z(x, y)+bracer_thickness_mm/2])
        scale([1, 1, max(0.18, height/max(0.1, diameter))])
            sphere(d=diameter);
}}

module bracer_long_bar(x, center_y, length, width, height) {{
    hull() {{
        for (end=[-1, 1])
            bracer_surface_detail(x, center_y+end*length/2, width, height);
    }}
}}

module bracer_plate_patch(center_y, length, width, height) {{
    // Surface-following patch used for end bands and raised center plates.
    hull() {{
        for (side=[-1, 1])
            for (end=[-1, 1])
                bracer_surface_detail(side*width/2, center_y+end*length/2,
                    bracer_thickness_mm*1.35, height);
    }}
}}

module bracer_shell() {{
    // Tapered curved shell: wrist at Y=0, forearm at +Y.
    hull() {{
        for (y=[0, bracer_length_mm])
            for (angle=[-bracer_arc_degrees/2:bracer_arc_degrees/8:bracer_arc_degrees/2])
                let(radius=bracer_radius_at(y),
                    x=radius*sin(angle),
                    z=radius*cos(angle)-radius*cos(bracer_arc_degrees/2))
                    translate([x, y, z]) sphere(d=bracer_thickness_mm);
    }}
}}

module bracer_trim_band(y) {{
    // Raised end trim bands reinforce the wrist and forearm ends visually.
    bracer_plate_patch(y, bracer_trim_width_mm,
        bracer_width_at(y)*0.86, bracer_thickness_mm*0.58);
}}

module bracer_outer_plate() {{
    {_bracer_style_geometry(style)}
    {_bracer_detail_geometry(details)}
}}

module bracer() {{
    color("gainsboro") union() {{
        bracer_shell();
        {trim_calls}
        bracer_outer_plate();
    }}
}}
"""


def generate_armor_scad(
    armor_type: str = "Bracer",
    metrics: dict[str, float] | None = None,
    bracer_style: str = "Knight",
    pauldron_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
    debug_geometry: bool = False,
) -> str:
    """Build a decorative OpenSCAD armor prop program."""
    resolved_type = normalize_armor_type(armor_type)
    if resolved_type == "Pauldron":
        return generate_pauldron_scad(
            metrics=metrics,
            pauldron_style=pauldron_style,
            detail_options=detail_options,
            debug_geometry=debug_geometry,
        )
    style = normalize_bracer_style(bracer_style)
    details = normalize_bracer_detail_options(style, detail_options)
    values, warnings = resolve_bracer_metrics(metrics)
    assignments = "\n".join(f"{name} = {value:g};" for name, value in values.items())
    detail_text = ", ".join(name for name, enabled in details.items() if enabled) or "none"
    warning_text = "\n".join(f"// Warning: {warning}" for warning in warnings)
    debug_call = """
// DEBUG GEOMETRY ENABLED
color([0.2, 0.6, 1.0, 0.16])
    translate([0, bracer_length_mm/2, bracer_thickness_mm])
        cube([forearm_width_mm, bracer_length_mm, bracer_thickness_mm], center=true);
""" if debug_geometry else ""
    return f"""// Digital Forge Armor Version 1: {resolved_type}
// Armor type: {resolved_type}
// Bracer style: {style}
// Bracer details: {detail_text}
// Decorative/prototype fantasy prop geometry only; not wearable protective equipment.
// Coordinate contract:
// - The wrist end starts at Y=0 and the forearm end extends toward +Y.
// - Width tapers from wrist_width_mm to forearm_width_mm.
// - Curvature is controlled by bracer_arc_degrees.
$fn = 48;
{assignments}
{warning_text}

{make_bracer(style, details)}
bracer();
{debug_call}"""


def _pauldron_style_geometry(style: str) -> str:
    """Return style-specific decorative pauldron features."""
    if style == "Barbarian":
        return """// Barbarian style: heavy center rib, rivets, and rugged shoulder mass.
    pauldron_center_rib(pauldron_thickness_mm*1.3, pauldron_thickness_mm*0.9);
    for (side=[-1, 1])
        pauldron_side_rib(side, pauldron_thickness_mm*1.05);"""
    if style == "Elven":
        return """// Elven style: slimmer leaf-like crest following the plate stack.
    pauldron_leaf_crest(pauldron_thickness_mm*0.75);
    for (side=[-1, 1])
        pauldron_surface_detail(side*pauldron_width_mm*0.18,
            pauldron_depth_mm*0.42, pauldron_thickness_mm*1.2,
            pauldron_thickness_mm*0.32);"""
    return """// Knight style: clean layered shoulder plates with a central raised trim.
    pauldron_center_rib(pauldron_thickness_mm*0.95, pauldron_thickness_mm*0.65);"""


def _pauldron_detail_geometry(detail_options: dict[str, bool]) -> str:
    """Return optional pauldron detail geometry selected by UI flags."""
    details: list[str] = []
    if detail_options["raised_trim"]:
        details.append("""// Optional raised trim on each layered plate.
        for (i=[0:plate_count-1])
            pauldron_plate_trim(i);""")
    if detail_options["rivets"]:
        details.append("""// Optional rivets anchored near plate corners.
        for (i=[0:plate_count-1])
            for (side=[-1, 1])
                pauldron_surface_detail(side*pauldron_width_at(i)*0.36,
                    pauldron_plate_center_y(i), pauldron_rivet_diameter_mm,
                    pauldron_rivet_diameter_mm*0.38);""")
    if detail_options["spikes"]:
        details.append("""// Optional blunt fantasy shoulder spikes.
        for (x=[-pauldron_width_mm*0.22, 0, pauldron_width_mm*0.22])
            translate([x, pauldron_depth_mm*0.28,
                    pauldron_surface_z(x, pauldron_depth_mm*0.28)+pauldron_thickness_mm/2])
                cylinder(h=pauldron_spike_height_mm,
                    r1=pauldron_thickness_mm*0.95, r2=pauldron_thickness_mm*0.28);""")
    if detail_options["runes"]:
        details.append("""// Optional raised rune-like decorative motif.
        for (index=[-1, 0, 1])
            translate([index*pauldron_width_mm*0.11, pauldron_depth_mm*0.38,
                    pauldron_surface_z(index*pauldron_width_mm*0.11, pauldron_depth_mm*0.38)
                    + pauldron_thickness_mm/2])
                rotate([0, 0, 35-index*22])
                    cube([pauldron_thickness_mm*0.55, pauldron_width_mm*0.13,
                        pauldron_thickness_mm*0.42], center=true);""")
    return "\n".join(details) if details else "// No optional pauldron details selected."


def make_pauldron(pauldron_style: str, detail_options: dict[str, bool] | None = None) -> str:
    """Return layered decorative pauldron modules rooted at the neck-side plate."""
    style = normalize_pauldron_style(pauldron_style)
    details = normalize_pauldron_detail_options(style, detail_options)
    return f"""function pauldron_width_at(i) = pauldron_width_mm
    * (1 - 0.18 * i / max(1, plate_count-1));
function pauldron_plate_center_y(i) = i * pauldron_plate_step_mm;
function pauldron_surface_z(x, y) = let(
    nx=min(1, abs(x)/(pauldron_width_mm/2)),
    ny=min(1, y/max(1, pauldron_depth_mm)))
    pauldron_height_mm * max(0.18, (1-nx*nx)*0.72 + (1-ny)*0.28);

module pauldron_surface_detail(x, y, diameter, height) {{
    translate([x, y, pauldron_surface_z(x, y)+pauldron_thickness_mm/2])
        scale([1, 1, max(0.18, height/max(0.1, diameter))])
            sphere(d=diameter);
}}

module pauldron_plate(i) {{
    // Layered shoulder lames overlap along +Y from neck side toward upper arm.
    hull() {{
        for (side=[-1, 1])
            for (end=[-1, 1])
                let(x=side*pauldron_width_at(i)/2,
                    y=pauldron_plate_center_y(i)+end*pauldron_plate_depth_mm/2)
                    pauldron_surface_detail(x, y, pauldron_thickness_mm*1.55,
                        pauldron_thickness_mm*0.55);
    }}
}}

module pauldron_plate_trim(i) {{
    hull() {{
        for (side=[-1, 1])
            let(x=side*pauldron_width_at(i)*0.42,
                y=pauldron_plate_center_y(i)-pauldron_plate_depth_mm*0.32)
                pauldron_surface_detail(x, y, pauldron_thickness_mm*1.1,
                    pauldron_thickness_mm*0.42);
    }}
}}

module pauldron_center_rib(width, height) {{
    hull() {{
        for (y=[0, pauldron_depth_mm*0.92])
            pauldron_surface_detail(0, y, width, height);
    }}
}}

module pauldron_side_rib(side, height) {{
    hull() {{
        for (y=[pauldron_depth_mm*0.16, pauldron_depth_mm*0.82])
            pauldron_surface_detail(side*pauldron_width_mm*0.34, y,
                pauldron_thickness_mm*1.2, height);
    }}
}}

module pauldron_leaf_crest(height) {{
    hull() {{
        pauldron_surface_detail(0, pauldron_depth_mm*0.08,
            pauldron_thickness_mm*1.25, height);
        pauldron_surface_detail(-pauldron_width_mm*0.20, pauldron_depth_mm*0.46,
            pauldron_thickness_mm*1.05, height*0.82);
        pauldron_surface_detail(0, pauldron_depth_mm*0.88,
            pauldron_thickness_mm*0.95, height*0.72);
    }}
    hull() {{
        pauldron_surface_detail(0, pauldron_depth_mm*0.08,
            pauldron_thickness_mm*1.25, height);
        pauldron_surface_detail(pauldron_width_mm*0.20, pauldron_depth_mm*0.46,
            pauldron_thickness_mm*1.05, height*0.82);
        pauldron_surface_detail(0, pauldron_depth_mm*0.88,
            pauldron_thickness_mm*0.95, height*0.72);
    }}
}}

module pauldron_style_details() {{
    {_pauldron_style_geometry(style)}
    {_pauldron_detail_geometry(details)}
}}

module pauldron() {{
    color("gainsboro") union() {{
        for (i=[0:plate_count-1])
            pauldron_plate(i);
        pauldron_style_details();
    }}
}}
"""


def generate_pauldron_scad(
    metrics: dict[str, float] | None = None,
    pauldron_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
    debug_geometry: bool = False,
) -> str:
    """Build a decorative OpenSCAD pauldron prop program."""
    style = normalize_pauldron_style(pauldron_style)
    details = normalize_pauldron_detail_options(style, detail_options)
    values, warnings = resolve_pauldron_metrics(metrics)
    assignments = "\n".join(f"{name} = {value:g};" for name, value in values.items())
    detail_text = ", ".join(name for name, enabled in details.items() if enabled) or "none"
    warning_text = "\n".join(f"// Warning: {warning}" for warning in warnings)
    debug_call = """
// DEBUG GEOMETRY ENABLED
color([0.2, 0.6, 1.0, 0.16])
    translate([0, pauldron_depth_mm/2, pauldron_height_mm/2])
        cube([pauldron_width_mm, pauldron_depth_mm, pauldron_height_mm], center=true);
""" if debug_geometry else ""
    return f"""// Digital Forge Armor Version 1: Pauldron
// Armor type: Pauldron
// Pauldron style: {style}
// Pauldron details: {detail_text}
// Decorative/prototype fantasy prop geometry only; not wearable protective equipment.
// Coordinate contract:
// - The shoulder cap is centered on X=0.
// - Layered plates progress along +Y from neck side toward upper arm.
// - Height rises along +Z to form a shoulder dome.
$fn = 48;
{assignments}
{warning_text}

{make_pauldron(style, details)}
pauldron();
{debug_call}"""


def assemble_sword(
    guard_rotation: int,
    debug_geometry: bool = False,
    visible_components: dict[str, bool] | None = None,
) -> str:
    """Return the shared assembly using global anchors on the X=0 centerline."""
    visible = normalize_component_visibility(visible_components)
    debug_call = "\n// DEBUG GEOMETRY ENABLED\ndebug_markers();" if debug_geometry else ""
    calls = {
        "tang": "translate([0, tang_center_y, 0]) tang_core();",
        "blade": "translate([0, blade_start_y, 0]) blade();",
        "guard": f"translate([0, guard_center_y, 0]) rotate([0, {guard_rotation}, 0]) guard();",
        "grip": "translate([0, (grip_start_y+grip_end_y)/2, 0]) grip();",
        "pommel": "// Pommel overlaps the grip by pommel_overlap_mm to prevent rendering gaps.\ntranslate([0, pommel_anchor_y, 0]) pommel();",
    }
    assembly = "\n".join(calls[name] for name in COMPONENT_NAMES if visible[name])
    if not assembly:
        assembly = "// EMPTY ASSEMBLY: select at least one component to preview or export."
    return f"""// Visible components remain at their full-assembly anchors.
{assembly}
{debug_call}
"""


def generate_scad(
    sword_type: str,
    metrics: dict[str, float],
    blade_style: str,
    guard_style: str,
    pommel_style: str,
    fuller_enabled: bool = False,
    fuller_length_ratio: float = 0.65,
    fuller_width_mm: float = 12,
    ridge_enabled: bool = False,
    debug_geometry: bool = False,
    visible_components: dict[str, bool] | None = None,
    fuller_offset_x: float = 0.0,
    ridge_offset_x: float = 0.0,
    fuller_depth_mm: float = 0.8,
) -> str:
    """Build a complete decorative OpenSCAD program from dimensions and styles."""
    values = dict(metrics)
    values.setdefault("ricasso_length_mm", 0)
    grip_width = max(1.0, float(values.get("grip_width_mm", 1.0)))
    blade_width = max(1.0, float(values.get("blade_base_width_mm", 1.0)))
    blade_thickness = max(1.0, float(values.get("blade_thickness_mm", 1.0)))
    grip_length = max(1.0, float(values.get("grip_length_mm", 1.0)))
    guard_height = max(1.0, float(values.get("guard_height_mm", 1.0)))
    ricasso_length = max(0.0, float(values.get("ricasso_length_mm", 0.0)))
    blade_length = max(1.0, float(values.get("blade_length_mm", 1.0)))
    detail_start, detail_end = blade_detail_bounds(
        blade_length, ricasso_length, fuller_length_ratio, blade_style
    )
    resolved_fuller_width, resolved_fuller_depth = resolve_fuller_dimensions(
        blade_width, blade_thickness, fuller_width_mm, fuller_depth_mm
    )
    resolved_fuller_offset = clamp_blade_detail_offset(
        blade_width, fuller_offset_x, resolved_fuller_width, blade_length, blade_style
    )
    fuller_offset_ratio = resolved_fuller_offset / blade_width
    resolved_ridge_offset = clamp_blade_detail_offset(
        blade_width, ridge_offset_x, blade_width * 0.14, blade_length, blade_style
    )
    tang = resolve_tang_details(values)
    tang_blade_overlap = max(3.0, min(ricasso_length, blade_width * 0.5))
    tang_length = tang["tang_length_mm"]
    detail_names = {
        "tang_length_mm", "tang_width_mm", "tang_thickness_mm", "peg_hole_count",
        "peg_hole_diameter_mm", "peg_hole_spacing_mm", "peg_hole_offset_from_guard_mm",
    }
    assignments = "\n".join(
        f"{name} = {value:g};" for name, value in values.items() if name not in detail_names
    )
    assignments += (
        f"\nfuller_length_ratio = {fuller_length_ratio:g};"
        f"\nfuller_width_mm = {resolved_fuller_width:g};"
        f"\nfuller_depth_mm = {resolved_fuller_depth:g};"
        f"\nfuller_offset_x = {resolved_fuller_offset:g};"
        f"\nfuller_offset_ratio = {fuller_offset_ratio:g};"
        f"\nridge_offset_x = {resolved_ridge_offset:g};"
        f"\n// Blade-local detail bounds exclude the guard/ricasso and blunt tip."
        f"\nblade_detail_start_y = {detail_start:g};"
        f"\nblade_detail_end_y = {detail_end:g};"
        f"\ndisk_guard_diameter_mm = {disk_guard_diameter(values):g};"
        f"\n// External grip dimensions remain independent from the internal prop core."
        f"\ngrip_depth_mm = {tang['grip_depth_mm']:g};"
        f"\ntang_width_mm = {tang['tang_width_mm']:g};"
        f"\ntang_thickness_mm = {tang['tang_thickness_mm']:g};"
        f"\ntang_blade_overlap_mm = {tang_blade_overlap:g};"
        f"\ntang_length_mm = {tang_length:g};"
        f"\npeg_hole_count = {tang['peg_hole_count']:g};"
        f"\npeg_hole_diameter_mm = {tang['peg_hole_diameter_mm']:g};"
        f"\npeg_hole_spacing_mm = {tang['peg_hole_spacing_mm']:g};"
        f"\npeg_hole_offset_from_guard_mm = {tang['peg_hole_offset_from_guard_mm']:g};"
        f"\nmin_prop_tip_width_mm = 3;"
        f"\nmin_prop_blade_thickness_mm = 2.4;"
        f"\nprop_tip_width_mm = max(blade_tip_width_mm, min_prop_tip_width_mm);"
        f"\nprop_blade_thickness_mm = max(blade_thickness_mm, min_prop_blade_thickness_mm);"
    )
    debug_module = make_debug_markers() if debug_geometry else ""
    guard_rotation = get_guard_rotation(sword_type, blade_style)
    visible = normalize_component_visibility(visible_components)
    visible_names = ", ".join(name for name in COMPONENT_NAMES if visible[name]) or "none"
    modules = {
        "blade": make_blade(blade_style, fuller_enabled, ridge_enabled),
        "tang": make_tang(tang["peg_hole_count"]),
        "guard": make_guard(guard_style),
        "grip": make_grip(),
        "pommel": make_pommel(pommel_style),
    }
    component_modules = "\n".join(modules[name] for name in COMPONENT_NAMES if visible[name])

    return f"""// Digital Forge Version 4: {sword_type}
// Blade style: {blade_style}
// Guard style: {guard_style}
// Guard rotation around sword axis: {guard_rotation} degrees
// Pommel style: {pommel_style}
// Visible components: {visible_names}
// Coordinate contract:
// - Every part is centered on X=0 unless a style intentionally offsets its detail.
// - The sword points along +Y. From low to high: pommel, grip, guard, blade.
// - Contact boundaries are shared: grip_end_y == guard_bottom_y and
//   blade_start_y == guard_top_y. Dimensions are millimetres.
$fn = 56;
{assignments}

// Shared assembly anchors and bounds.
grip_end_y = 0;
grip_start_y = -grip_length_mm;
guard_bottom_y = grip_end_y;
guard_center_y = guard_bottom_y + guard_height_mm/2;
guard_y = guard_center_y;
guard_top_y = guard_bottom_y + guard_height_mm;
blade_start_y = guard_top_y;
blade_tip_y = blade_start_y + blade_length_mm;
tang_top_y = blade_start_y + tang_blade_overlap_mm;
tang_bottom_y = tang_top_y - tang_length_mm;
tang_center_y = (tang_bottom_y + tang_top_y)/2;
pommel_overlap_mm = min(2, pommel_size_mm/4);
pommel_center_y = grip_start_y - pommel_size_mm/2 + pommel_overlap_mm;
pommel_anchor_y = {("grip_start_y + pommel_overlap_mm" if pommel_style == "spike" else "pommel_center_y")};
pommel_top_y = pommel_center_y + pommel_size_mm/2;
pommel_bottom_y = pommel_center_y - pommel_size_mm/2;
effective_guard_width_mm = {("disk_guard_diameter_mm" if guard_style == "disk" else "guard_width_mm")};

{component_modules}
{debug_module}
{assemble_sword(guard_rotation, debug_geometry, visible)}"""
