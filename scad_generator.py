"""Generate decorative OpenSCAD fantasy prop geometry."""

BLADE_STYLES = ("tapered", "leaf", "needle", "curved", "falchion")
GUARD_STYLES = ("straight", "crescent", "downturned", "disk")
POMMEL_STYLES = ("sphere", "wheel", "ring", "spike")
ARMOR_TYPES = ("Bracer", "Pauldron")
BRACER_STYLES = ("Plain",)
BRACER_DETAIL_OPTIONS = ("raised_trim", "rivets", "center_ridge", "spikes", "runes")
BRACER_BINDING_STYLES = ("None", "Lacing Holes", "Lacing Loops", "Strap Slots", "Buckle-Ready Slots")
DEFAULT_BRACER_METRICS = {
    "bracer_length_mm": 180.0,
    "wrist_width_mm": 70.0,
    "forearm_width_mm": 100.0,
    "bracer_depth_mm": 48.0,
    "bracer_thickness_mm": 4.0,
    "bracer_wall_thickness_mm": 4.0,
    "bracer_arc_degrees": 220.0,
    "bracer_opening_width_mm": 34.0,
    "bracer_detail_depth_mm": 2.2,
    "bracer_exterior_finishing_allowance_mm": 0.5,
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


def normalize_bracer_style(bracer_style: str = "Plain") -> str:
    """Return the supported bracer aggregate style, falling legacy values back to Plain."""
    return "Plain"


def normalize_pauldron_style(pauldron_style: str = "Knight") -> str:
    """Return a supported pauldron style name."""
    normalized = str(pauldron_style or "Knight").strip().title()
    return normalized if normalized in PAULDRON_STYLES else "Knight"


def normalize_armor_type(armor_type: str = "Bracer") -> str:
    """Return a supported armor type name."""
    normalized = str(armor_type or "Bracer").strip().title()
    return normalized if normalized in ARMOR_TYPES else "Bracer"


def normalize_bracer_binding_style(binding_style: str = "None") -> str:
    """Return a supported bracer binding/closure style."""
    normalized = str(binding_style or "None").strip().title()
    aliases = {
        "None": "None",
        "Lacing Holes": "Lacing Holes",
        "Lacing Hole": "Lacing Holes",
        "Lacing Loops": "Lacing Loops",
        "Lacing Loop": "Lacing Loops",
        "Strap Slots": "Strap Slots",
        "Strap Slot": "Strap Slots",
        "Buckle-Ready Slots": "Buckle-Ready Slots",
        "Buckle Ready Slots": "Buckle-Ready Slots",
        "Buckle Tabs": "Buckle-Ready Slots",
        "Buckle Tab": "Buckle-Ready Slots",
    }
    return aliases.get(normalized, "None")


def normalize_bracer_detail_options(
    bracer_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Return complete bracer detail flags. Legacy aggregate styles no longer add details."""
    defaults = {
        "raised_trim": False,
        "rivets": False,
        "center_ridge": False,
        "spikes": False,
        "runes": False,
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
    depth_default = max(28.0, min(90.0, (wrist + forearm) * 0.28))
    depth = clamp(_finite_float(source.get("bracer_depth_mm"), depth_default), 24.0, 140.0)
    thickness_source = (
        metrics.get("bracer_wall_thickness_mm")
        if metrics and "bracer_wall_thickness_mm" in metrics
        else source.get("bracer_thickness_mm")
    )
    thickness = clamp(_finite_float(thickness_source, 4.0), 2.4, 12.0)
    arc = clamp(_finite_float(source.get("bracer_arc_degrees"), 220.0), 120.0, 260.0)
    opening_default = max(24.0, min(wrist, forearm) * 0.48)
    opening = clamp(_finite_float(source.get("bracer_opening_width_mm"), opening_default), 16.0, 120.0)
    detail_depth = clamp(_finite_float(source.get("bracer_detail_depth_mm"), thickness * 0.55), 0.8, 6.0)
    finishing_allowance = clamp(
        _finite_float(source.get("bracer_exterior_finishing_allowance_mm"), 0.5),
        0.0,
        1.5,
    )

    requested = {
        "bracer_length_mm": source.get("bracer_length_mm"),
        "wrist_width_mm": source.get("wrist_width_mm"),
        "forearm_width_mm": source.get("forearm_width_mm"),
        "bracer_depth_mm": source.get("bracer_depth_mm"),
        "bracer_thickness_mm": source.get("bracer_thickness_mm"),
        "bracer_wall_thickness_mm": source.get("bracer_wall_thickness_mm", source.get("bracer_thickness_mm")),
        "bracer_arc_degrees": source.get("bracer_arc_degrees"),
        "bracer_opening_width_mm": source.get("bracer_opening_width_mm"),
        "bracer_detail_depth_mm": source.get("bracer_detail_depth_mm"),
        "bracer_exterior_finishing_allowance_mm": source.get("bracer_exterior_finishing_allowance_mm"),
    }
    resolved = {
        "bracer_length_mm": length,
        "wrist_width_mm": wrist,
        "forearm_width_mm": forearm,
        "bracer_depth_mm": depth,
        "bracer_thickness_mm": thickness,
        "bracer_wall_thickness_mm": thickness,
        "bracer_arc_degrees": arc,
        "bracer_opening_width_mm": opening,
        "bracer_detail_depth_mm": detail_depth,
        "bracer_exterior_finishing_allowance_mm": finishing_allowance,
    }
    for name, value in resolved.items():
        fallback = DEFAULT_BRACER_METRICS.get(name, value)
        requested_value = thickness_source if name == "bracer_wall_thickness_mm" else requested[name]
        if _finite_float(requested_value, fallback) != value:
            warnings.append(f"{name} was clamped to {value:g}.")

    if wrist > forearm:
        wrist = max(35.0, forearm * 0.82)
        resolved["wrist_width_mm"] = wrist
        warnings.append("wrist_width_mm was reduced so the bracer tapers outward from wrist to elbow.")

    min_outer_half = min(wrist, forearm, depth) / 2
    max_wall = max(2.4, min_outer_half - 4.0)
    if thickness > max_wall:
        thickness = max_wall
        resolved["bracer_thickness_mm"] = thickness
        resolved["bracer_wall_thickness_mm"] = thickness
        warnings.append(f"bracer_wall_thickness_mm was reduced to {thickness:g} so the inner cavity fits.")

    estimated_hole = clamp(thickness * 1.25, 3.0, 7.0)
    estimated_slot_length = clamp(thickness * 1.8, 6.0, 10.0)
    estimated_bridge = max(thickness, estimated_hole / 2, estimated_slot_length / 2, 3.0)
    closure_side_width = estimated_bridge + max(estimated_hole, estimated_slot_length) + finishing_allowance * 2
    safe_opening = max(16.0, min(wrist, forearm) - closure_side_width * 2)
    if opening > safe_opening:
        opening = safe_opening
        resolved["bracer_opening_width_mm"] = opening
        warnings.append(
            f"bracer_opening_width_mm was reduced to {opening:g} "
            "to leave material around closure passages."
        )

    max_detail = max(0.8, thickness * 1.1)
    if detail_depth > max_detail:
        detail_depth = max_detail
        resolved["bracer_detail_depth_mm"] = detail_depth
        warnings.append(f"bracer_detail_depth_mm was reduced to {detail_depth:g} to keep decoration printable.")

    max_finishing = max(0.0, min(1.5, thickness * 0.28))
    if finishing_allowance > max_finishing:
        finishing_allowance = max_finishing
        resolved["bracer_exterior_finishing_allowance_mm"] = finishing_allowance
        warnings.append(
            f"bracer_exterior_finishing_allowance_mm was reduced to {finishing_allowance:g} "
            "to preserve closure edge material."
        )

    trim_width = clamp(length * 0.075, 6.0, 18.0)
    panel_length = max(12.0, length - trim_width * 3.4)
    rivet_diameter = clamp(thickness * 1.35, 3.0, min(8.5, min(wrist, forearm) * 0.09))
    spike_height = clamp(thickness * 2.3, 5.0, min(18.0, depth * 0.26))
    shell_side_width = max(0.0, (min(wrist, forearm) - opening) / 2)
    binding_hole_diameter = clamp(thickness * 1.25, 3.0, 7.0)
    flange_width = clamp(max(thickness * 3.0, binding_hole_diameter * 2.6), 10.0, 20.0)
    flange_thickness = clamp(max(thickness * 1.35, binding_hole_diameter * 1.45), 6.0, 12.0)
    flange_outward_offset = flange_thickness / 2 + finishing_allowance + thickness * 0.28
    min_hole_bridge = max(2.4, binding_hole_diameter * 0.45, min(thickness * 0.6, 4.5))
    safe_hole_diameter = max(2.6, flange_width - 2 * min_hole_bridge)
    if binding_hole_diameter > safe_hole_diameter:
        binding_hole_diameter = safe_hole_diameter
        warnings.append(
            f"bracer_binding_hole_diameter_mm was reduced to {binding_hole_diameter:g} "
            "so lacing holes stay enclosed in the closure flange."
        )
    flange_width = clamp(max(thickness * 3.0, binding_hole_diameter * 2.6), 10.0, 20.0)
    flange_thickness = clamp(max(thickness * 1.35, binding_hole_diameter * 1.45), 6.0, 12.0)
    flange_outward_offset = flange_thickness / 2 + finishing_allowance + thickness * 0.28
    strap_width = clamp(min(wrist, forearm) * 0.22, 10.0, 24.0)
    strap_length = clamp(thickness * 1.8, 5.5, min(10.0, flange_width * 0.58))
    strap_clearance = clamp(strap_width * 0.14, 2.0, 4.0)
    strap_slot_width = strap_width + strap_clearance
    min_slot_bridge = max(2.4, strap_length * 0.35, min(thickness * 0.6, 4.5))
    safe_slot_length = max(5.0, flange_width - 2 * min_slot_bridge)
    if strap_length > safe_slot_length:
        strap_length = safe_slot_length
        warnings.append(
            f"bracer_strap_slot_length_mm was reduced to {strap_length:g} "
            "so strap slots stay enclosed in the closure flange."
        )
    wrist_margin = max(trim_width * 1.35, binding_hole_diameter * 2.0, length * 0.14, 16.0)
    elbow_margin = max(trim_width * 1.35, binding_hole_diameter * 2.0, length * 0.14, 16.0)
    usable_binding_span = max(0.0, length - wrist_margin - elbow_margin)
    binding_count = max(2, min(6, int(usable_binding_span // max(34.0, binding_hole_diameter * 5.2)) + 1))
    if usable_binding_span < max(34.0, binding_hole_diameter * 5.2):
        binding_count = 2
        warnings.append("bracer_binding_count was reduced to 2 because the bracer is short near the closure ends.")
    binding_margin = wrist_margin
    loop_passage = max(3.2, binding_hole_diameter)
    loop_wall = clamp(max(1.8, thickness * 0.45), 1.8, 3.2)
    loop_height = clamp(loop_passage + loop_wall * 1.2, 5.0, flange_thickness * 1.1)
    loop_length = clamp(loop_passage + loop_wall * 2.2, 7.5, max(8.0, usable_binding_span / max(2, binding_count) * 0.42))
    resolved.update(
        bracer_trim_width_mm=trim_width,
        bracer_panel_length_mm=panel_length,
        bracer_panel_width_mm=clamp(min(wrist, forearm) * 0.30, 14.0, 44.0),
        bracer_rivet_diameter_mm=rivet_diameter,
        bracer_spike_height_mm=spike_height,
        bracer_binding_hole_diameter_mm=binding_hole_diameter,
        bracer_binding_margin_mm=binding_margin,
        bracer_closure_wrist_margin_mm=wrist_margin,
        bracer_closure_elbow_margin_mm=elbow_margin,
        bracer_closure_usable_length_mm=usable_binding_span,
        bracer_binding_count=binding_count,
        bracer_closure_edge_margin_mm=max(min_hole_bridge, min_slot_bridge),
        bracer_closure_flange_width_mm=flange_width,
        bracer_closure_flange_thickness_mm=flange_thickness,
        bracer_closure_flange_outward_offset_mm=flange_outward_offset,
        bracer_strap_width_nominal_mm=strap_width,
        bracer_strap_slot_width_mm=strap_slot_width,
        bracer_strap_slot_length_mm=strap_length,
        bracer_buckle_slot_width_mm=strap_slot_width + max(3.0, strap_clearance),
        bracer_buckle_slot_length_mm=min(flange_width * 0.72, strap_length + max(2.0, thickness * 0.35)),
        bracer_loop_passage_diameter_mm=loop_passage,
        bracer_loop_wall_thickness_mm=loop_wall,
        bracer_loop_height_mm=loop_height,
        bracer_loop_length_mm=loop_length,
    )
    return resolved, warnings


def bracer_closure_layout_metrics(metrics: dict[str, float] | None = None) -> dict[str, object]:
    """Return deterministic bracer closure placement metrics for tests and audits."""
    resolved, _ = resolve_bracer_metrics(metrics)
    count = int(resolved["bracer_binding_count"])
    wrist_margin = resolved["bracer_closure_wrist_margin_mm"]
    usable = resolved["bracer_closure_usable_length_mm"]
    positions = [
        wrist_margin + index * usable / max(1, count - 1)
        for index in range(count)
    ]
    flange_width = resolved["bracer_closure_flange_width_mm"]
    flange_thickness = resolved["bracer_closure_flange_thickness_mm"]
    hole_diameter = resolved["bracer_binding_hole_diameter_mm"]
    strap_length = resolved["bracer_strap_slot_length_mm"]
    buckle_length = resolved["bracer_buckle_slot_length_mm"]
    return {
        "metrics": resolved,
        "positions_y": positions,
        "usable_midpoint_y": wrist_margin + usable / 2,
        "hole_flange_margin_mm": (flange_width - hole_diameter) / 2,
        "strap_slot_flange_margin_mm": (flange_width - strap_length) / 2,
        "buckle_slot_flange_margin_mm": (flange_width - buckle_length) / 2,
        "cutter_axis": "radial_flange_normal_xz",
        "legacy_shell_tangent_axis": "z",
        "cutter_crosses_flange_thickness": flange_thickness + 2 * resolved["bracer_exterior_finishing_allowance_mm"] + 4.0,
        "loop_outside_cavity": True,
        "loop_has_passage": True,
    }


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
    """Return a style note; detail flags control bracer geometry."""
    return "// Plain bracer aggregate style; decoration is controlled only by the decoration preset."


def _bracer_detail_geometry(detail_options: dict[str, bool]) -> str:
    """Return optional detail geometry selected by UI flags."""
    details: list[str] = []
    if detail_options["raised_trim"]:
        details.append("""// Optional raised trim: end bands and two longitudinal side rails.
        bracer_trim_band(bracer_trim_width_mm/2);
        bracer_trim_band(bracer_length_mm-bracer_trim_width_mm/2);
        for (side=[-1, 1])
            bracer_side_rail(side);""")
    if detail_options["center_ridge"]:
        details.append("""// Optional center ridge: longitudinal faceted crest on the top centerline.
        bracer_center_ridge();""")
    if detail_options["rivets"]:
        details.append("""// Optional rivet detail: paired rows of low rounded caps.
        for (side=[-1, 1])
            for (y=[bracer_trim_width_mm*1.7, bracer_length_mm*0.38,
                    bracer_length_mm*0.62, bracer_length_mm-bracer_trim_width_mm*1.7])
                bracer_rivet(side, y);""")
    if detail_options["spikes"]:
        details.append("""// Optional controlled ornamental spikes with broad attached bases.
        for (y=[bracer_length_mm*0.32, bracer_length_mm*0.5, bracer_length_mm*0.68])
            bracer_spike(y);""")
    if detail_options["runes"]:
        details.append("""// Optional raised rune / motif: repeated symmetrical chevrons in a bounded panel.
        for (y=[bracer_length_mm*0.38, bracer_length_mm*0.5, bracer_length_mm*0.62])
            bracer_chevron_rune(y);""")
    return "\n".join(details) if details else "// Plain bracer: no decorative geometry beyond the tapered shell."


def _bracer_binding_positive(binding_style: str) -> str:
    flange_call = """// Explicit exterior closure flanges: continuous rails outside the arm cavity.
        bracer_closure_flanges();"""
    if binding_style == "Lacing Loops":
        return f"""{flange_call}
        // Compact external lacing loops: low eyelets attached to the flange exterior.
        for (side=[-1, 1])
            for (i=[0:bracer_binding_count-1])
                bracer_lacing_loop(side, bracer_binding_y(i));"""
    if binding_style == "Buckle-Ready Slots":
        return f"""{flange_call}
        // Buckle-ready reinforced frames: anchor side and larger hardware-access side.
        for (i=[0:2])
            bracer_strap_anchor_frame(-1, bracer_binding_y(i+1));
        for (i=[0:2])
            bracer_buckle_access_frame(1, bracer_binding_y(i+1));"""
    if binding_style in {"Lacing Holes", "Strap Slots"}:
        return flange_call
    return "// No positive bracer binding hardware selected."


def _bracer_binding_subtractive(binding_style: str) -> str:
    if binding_style == "Lacing Holes":
        return """// Lacing holes: paired subtractive round holes through both opening edges.
        for (side=[-1, 1])
            for (i=[0:bracer_binding_count-1])
                bracer_lacing_hole(side, bracer_binding_y(i));"""
    if binding_style == "Strap Slots":
        return """// Strap slots: paired subtractive rectangular slots through both opening edges.
        for (side=[-1, 1])
            for (i=[0:2])
                bracer_strap_slot(side, bracer_binding_y(i+1));"""
    if binding_style == "Buckle-Ready Slots":
        return """// Complete enclosed anchor slots and larger buckle-access passages.
        for (i=[0:2])
            bracer_strap_anchor_slot(-1, bracer_binding_y(i+1));
        for (i=[0:2])
            bracer_buckle_access_slot(1, bracer_binding_y(i+1));"""
    return "// No subtractive bracer binding features selected."


def make_bracer(
    bracer_style: str,
    detail_options: dict[str, bool] | None = None,
    binding_style: str = "None",
) -> str:
    """Return tapered decorative bracer modules rooted from wrist Y=0 to forearm +Y."""
    style = normalize_bracer_style(bracer_style)
    details = normalize_bracer_detail_options(style, detail_options)
    binding = normalize_bracer_binding_style(binding_style)
    return f"""function bracer_width_at(y) = wrist_width_mm
    + (forearm_width_mm-wrist_width_mm) * y / bracer_length_mm;
function bracer_half_width_at(y) = bracer_width_at(y)/2;
function bracer_half_depth() = bracer_depth_mm/2;
function bracer_opening_angle_at(y) = 2*asin(min(0.92, bracer_opening_width_mm/max(1, bracer_width_at(y))));
function bracer_covered_angle_at(y) = min(bracer_arc_degrees, 360-bracer_opening_angle_at(y));
function bracer_angle_for_index(i, y) = -bracer_covered_angle_at(y)/2
    + bracer_covered_angle_at(y)*i/bracer_shell_steps;
function bracer_shell_x(y, angle) = bracer_half_width_at(y) * sin(angle);
function bracer_shell_z(y, angle) = bracer_half_depth() * cos(angle);
function bracer_surface_z(x, y) = let(
    rx=bracer_half_width_at(y),
    rz=bracer_half_depth(),
    limited_x=max(-rx*0.96, min(rx*0.96, x)))
    rz*sqrt(max(0, 1-(limited_x*limited_x)/(rx*rx)));
function bracer_edge_x(side, y) = bracer_shell_x(y, side*bracer_covered_angle_at(y)/2);
function bracer_edge_z(y) = bracer_shell_z(y, bracer_covered_angle_at(y)/2);
function bracer_opening_edge_angle(side, y) = side*bracer_covered_angle_at(y)/2;
function bracer_outward_normal_x(side, y) = sin(bracer_opening_edge_angle(side, y));
function bracer_outward_normal_z(side, y) = cos(bracer_opening_edge_angle(side, y));
function bracer_longitudinal_position(i) = bracer_binding_y(i);
function bracer_flange_center_x(side, y) =
    bracer_edge_x(side, y) + bracer_outward_normal_x(side, y)*bracer_closure_flange_outward_offset_mm;
function bracer_flange_center_z(side, y) =
    bracer_edge_z(y) + bracer_outward_normal_z(side, y)*bracer_closure_flange_outward_offset_mm;
function bracer_closure_center_x(side, y, passage_depth) = bracer_flange_center_x(side, y);
function bracer_closure_center_z(side, y) = bracer_flange_center_z(side, y);
function bracer_external_feature_center_x(side, y, height) =
    bracer_flange_center_x(side, y)
        + bracer_outward_normal_x(side, y)*(bracer_closure_flange_thickness_mm/2 + height/2);
function bracer_external_feature_center_z(side, y, height) =
    bracer_flange_center_z(side, y)
        + bracer_outward_normal_z(side, y)*(bracer_closure_flange_thickness_mm/2 + height/2);
function bracer_lacing_hole_cutter_diameter() =
    bracer_binding_hole_diameter_mm + 2*bracer_exterior_finishing_allowance_mm;
function bracer_slot_cutter_width(width) = width + 2*bracer_exterior_finishing_allowance_mm;
function bracer_slot_cutter_length(length) = length + 2*bracer_exterior_finishing_allowance_mm;
function bracer_shell_point_diameter() = bracer_wall_thickness_mm + 2*bracer_exterior_finishing_allowance_mm;
function bracer_binding_y(i) = bracer_closure_wrist_margin_mm
    + i*bracer_closure_usable_length_mm/max(1, bracer_binding_count-1);
function bracer_flange_start_y() = bracer_closure_wrist_margin_mm*0.72;
function bracer_flange_end_y() = bracer_length_mm - bracer_closure_elbow_margin_mm*0.72;
function bracer_flange_length() = bracer_flange_end_y() - bracer_flange_start_y();
function bracer_closure_cutter_depth() =
    bracer_closure_flange_thickness_mm + 2*bracer_exterior_finishing_allowance_mm + 4;
bracer_shell_steps = 16;

module bracer_surface_detail(x, y, diameter, height) {{
    translate([x, y, bracer_surface_z(x, y)+bracer_wall_thickness_mm/2])
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

module bracer_center_ridge() {{
    hull() {{
        bracer_surface_detail(0, bracer_trim_width_mm*1.55,
            bracer_wall_thickness_mm*1.05, bracer_detail_depth_mm);
        bracer_surface_detail(0, bracer_length_mm/2,
            bracer_wall_thickness_mm*1.35, bracer_detail_depth_mm*1.15);
        bracer_surface_detail(0, bracer_length_mm-bracer_trim_width_mm*1.55,
            bracer_wall_thickness_mm*1.05, bracer_detail_depth_mm);
    }}
}}

module bracer_side_rail(side) {{
    hull() {{
        for (y=[bracer_trim_width_mm*1.4, bracer_length_mm-bracer_trim_width_mm*1.4])
            bracer_surface_detail(side*bracer_panel_width_mm*1.28, y,
                bracer_wall_thickness_mm*1.05, bracer_detail_depth_mm*0.72);
    }}
}}

module bracer_rivet(side, y) {{
    bracer_surface_detail(side*bracer_panel_width_mm*1.35, y,
        bracer_rivet_diameter_mm, bracer_rivet_diameter_mm*0.34);
}}

module bracer_spike(y) {{
    translate([0, y, bracer_surface_z(0, y)+bracer_wall_thickness_mm*0.55]) {{
        cylinder(h=bracer_wall_thickness_mm*0.65,
            r=bracer_wall_thickness_mm*1.05);
        translate([0, 0, bracer_wall_thickness_mm*0.45])
            cylinder(h=bracer_spike_height_mm,
                r1=bracer_wall_thickness_mm*0.95, r2=bracer_wall_thickness_mm*0.16);
    }}
}}

module bracer_rune_stroke(x1, y1, x2, y2) {{
    hull() {{
        bracer_surface_detail(x1, y1, bracer_wall_thickness_mm*0.72, bracer_detail_depth_mm*0.45);
        bracer_surface_detail(x2, y2, bracer_wall_thickness_mm*0.72, bracer_detail_depth_mm*0.45);
    }}
}}

module bracer_chevron_rune(y) {{
    rune_w = bracer_panel_width_mm*0.46;
    rune_h = bracer_trim_width_mm*0.72;
    bracer_rune_stroke(-rune_w, y-rune_h, 0, y);
    bracer_rune_stroke(rune_w, y-rune_h, 0, y);
    bracer_rune_stroke(-rune_w, y+rune_h, 0, y);
    bracer_rune_stroke(rune_w, y+rune_h, 0, y);
}}

module bracer_shell_point(y, angle) {{
    translate([bracer_shell_x(y, angle), y,
            bracer_shell_z(y, angle)+bracer_exterior_finishing_allowance_mm])
        sphere(d=bracer_shell_point_diameter());
}}

module bracer_shell() {{
    // Tapered hollow shell: separate curved strips leave an open inner forearm gap.
    union() {{
        for (i=[0:bracer_shell_steps-1])
            hull() {{
                bracer_shell_point(0, bracer_angle_for_index(i, 0));
                bracer_shell_point(0, bracer_angle_for_index(i+1, 0));
                bracer_shell_point(bracer_length_mm, bracer_angle_for_index(i, bracer_length_mm));
                bracer_shell_point(bracer_length_mm, bracer_angle_for_index(i+1, bracer_length_mm));
            }}
    }}
}}

module bracer_trim_band(y) {{
    // Raised end trim bands reinforce the wrist and forearm ends visually.
    bracer_plate_patch(y, bracer_trim_width_mm,
        bracer_width_at(y)*0.72, bracer_detail_depth_mm);
}}

module bracer_outer_plate() {{
    {_bracer_style_geometry(style)}
    {_bracer_detail_geometry(details)}
}}

module bracer_flange_section(side, y, section_length) {{
    // Coordinate audit: Y is wrist-to-elbow. The opening edge is at low Z.
    // The flange face normal is the radial XZ vector from the shell center through the opening edge.
    translate([bracer_flange_center_x(side, y), y, bracer_flange_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            cube([bracer_closure_flange_width_mm, section_length,
                bracer_closure_flange_thickness_mm], center=true);
}}

module bracer_closure_flange(side) {{
    // Continuous exterior rail: outside the arm cavity and stopped before wrist/elbow ends.
    hull() {{
        bracer_flange_section(side, bracer_flange_start_y(), bracer_wall_thickness_mm*1.2);
        bracer_flange_section(side, bracer_flange_end_y(), bracer_wall_thickness_mm*1.2);
    }}
}}

module bracer_closure_flanges() {{
    for (side=[-1, 1])
        bracer_closure_flange(side);
}}

module bracer_lacing_hole(side, y) {{
    // Cutter axis: radial XZ flange-face normal, crossing the complete flange thickness.
    translate([bracer_closure_center_x(side, y, bracer_lacing_hole_cutter_diameter()),
            y, bracer_closure_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            cylinder(h=bracer_closure_cutter_depth(),
                d=bracer_lacing_hole_cutter_diameter(), center=true);
}}

module bracer_rounded_slot_cutter(width, length, through_depth) {{
    hull() {{
        for (end=[-1, 1])
            translate([0, end*max(0, width-length)/2, 0])
                cylinder(h=through_depth, d=length, center=true);
    }}
}}

module bracer_strap_slot(side, y) {{
    // Slot cutter axis: radial XZ flange normal; slot long axis follows Y for strap width.
    translate([bracer_closure_center_x(side, y, bracer_slot_cutter_length(bracer_strap_slot_length_mm)),
            y, bracer_closure_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            bracer_rounded_slot_cutter(
                bracer_slot_cutter_width(bracer_strap_slot_width_mm),
                bracer_slot_cutter_length(bracer_strap_slot_length_mm),
                bracer_closure_cutter_depth());
}}

module bracer_lacing_loop(side, y) {{
    // Compact eyelet body sits outside the flange; its passage runs along Y under the bridge.
    translate([bracer_external_feature_center_x(side, y, bracer_loop_height_mm),
            y, bracer_external_feature_center_z(side, y, bracer_loop_height_mm)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
        difference() {{
            cube([bracer_loop_length_mm,
                bracer_loop_passage_diameter_mm + bracer_loop_wall_thickness_mm*2,
                bracer_loop_height_mm], center=true);
            translate([0, 0, -bracer_loop_height_mm*0.16])
                rotate([90, 0, 0])
                    cylinder(h=bracer_loop_passage_diameter_mm + bracer_loop_wall_thickness_mm*4,
                        d=bracer_loop_passage_diameter_mm, center=true);
        }}
}}

module bracer_reinforced_slot_frame(side, y, slot_width, slot_length, extra) {{
    translate([bracer_flange_center_x(side, y), y, bracer_flange_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            cube([slot_length + bracer_wall_thickness_mm*2.2 + extra,
                slot_width + bracer_wall_thickness_mm*1.2 + extra,
                bracer_closure_flange_thickness_mm + bracer_wall_thickness_mm*0.55], center=true);
}}

module bracer_strap_anchor_frame(side, y) {{
    bracer_reinforced_slot_frame(side, y, bracer_strap_slot_width_mm, bracer_strap_slot_length_mm, 0);
}}

module bracer_buckle_access_frame(side, y) {{
    bracer_reinforced_slot_frame(side, y, bracer_buckle_slot_width_mm, bracer_buckle_slot_length_mm,
        bracer_wall_thickness_mm*0.45);
}}

module bracer_strap_anchor_slot(side, y) {{
    // Anchor slot is enclosed by the exterior flange/frame and drilled across rail thickness.
    translate([bracer_closure_center_x(side, y, bracer_slot_cutter_length(bracer_strap_slot_length_mm)),
            y, bracer_closure_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            bracer_rounded_slot_cutter(
                bracer_slot_cutter_width(bracer_strap_slot_width_mm),
                bracer_slot_cutter_length(bracer_strap_slot_length_mm),
                bracer_closure_cutter_depth());
}}

module bracer_buckle_access_slot(side, y) {{
    // Buckle side uses larger enclosed access passages, not decorative polygon tabs.
    translate([bracer_closure_center_x(side, y, bracer_slot_cutter_length(bracer_buckle_slot_length_mm)),
            y, bracer_closure_center_z(side, y)])
        rotate([0, bracer_opening_edge_angle(side, y), 0])
            bracer_rounded_slot_cutter(
                bracer_slot_cutter_width(bracer_buckle_slot_width_mm),
                bracer_slot_cutter_length(bracer_buckle_slot_length_mm),
                bracer_closure_cutter_depth());
}}

module bracer_binding_positive() {{
    {_bracer_binding_positive(binding)}
}}

module bracer_binding_cutters() {{
    {_bracer_binding_subtractive(binding)}
}}

module bracer_closure_debug_geometry() {{
    %bracer_closure_flanges();
    #bracer_binding_cutters();
    for (side=[-1, 1])
        for (i=[0:bracer_binding_count-1]) {{
            y = bracer_binding_y(i);
            translate([bracer_flange_center_x(side, y), y, bracer_flange_center_z(side, y)])
                sphere(d=bracer_wall_thickness_mm*0.9);
            hull() {{
                translate([bracer_flange_center_x(side, y), y, bracer_flange_center_z(side, y)])
                    sphere(d=bracer_wall_thickness_mm*0.45);
                translate([bracer_flange_center_x(side, y) + bracer_outward_normal_x(side, y)*bracer_closure_flange_thickness_mm,
                        y, bracer_flange_center_z(side, y) + bracer_outward_normal_z(side, y)*bracer_closure_flange_thickness_mm])
                    sphere(d=bracer_wall_thickness_mm*0.45);
            }}
        }}
    %translate([0, bracer_length_mm/2, -bracer_half_depth()+bracer_wall_thickness_mm/2])
        cube([bracer_opening_width_mm, bracer_length_mm, bracer_wall_thickness_mm], center=true);
}}

module bracer() {{
    color("gainsboro") difference() {{
        union() {{
            bracer_shell();
            bracer_outer_plate();
            bracer_binding_positive();
        }}
        bracer_binding_cutters();
    }}
}}
"""


def generate_armor_scad(
    armor_type: str = "Bracer",
    metrics: dict[str, float] | None = None,
    bracer_style: str = "Plain",
    pauldron_style: str = "Knight",
    detail_options: dict[str, bool] | None = None,
    debug_geometry: bool = False,
    bracer_binding_style: str = "None",
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
    binding = normalize_bracer_binding_style(bracer_binding_style)
    values, warnings = resolve_bracer_metrics(metrics)
    assignments = "\n".join(f"{name} = {value:g};" for name, value in values.items())
    detail_text = ", ".join(name for name, enabled in details.items() if enabled) or "none"
    warning_text = "\n".join(f"// Warning: {warning}" for warning in warnings)
    debug_call = """
// DEBUG GEOMETRY ENABLED
bracer_closure_debug_geometry();
""" if debug_geometry else ""
    return f"""// Digital Forge Armor Version 1: {resolved_type}
// Armor type: {resolved_type}
// Bracer style: {style}
// Bracer details: {detail_text}
// Bracer binding: {binding}
// Decorative/prototype fantasy prop geometry only; not wearable protective equipment.
// Coordinate contract:
// - The wrist end starts at Y=0 and the forearm end extends toward +Y.
// - Width tapers from wrist_width_mm to forearm_width_mm.
// - Depth, opening width, and coverage angle define a tapered open shell.
$fn = 48;
{assignments}
{warning_text}

{make_bracer(style, details, binding)}
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
