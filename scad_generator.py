"""Generate decorative OpenSCAD swords using one shared coordinate contract."""

BLADE_STYLES = ("tapered", "leaf", "needle", "curved", "falchion")
GUARD_STYLES = ("straight", "crescent", "downturned", "disk")
POMMEL_STYLES = ("sphere", "wheel", "ring", "spike")
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
    max_diameter = max(0.0, min(tang_width * 0.55, tang_length / (count + 1) * 0.6))
    diameter = clamp(float(metrics.get("peg_hole_diameter_mm", 4.0)), 0.0, max_diameter)
    edge_margin = max(diameter, 2.0)
    usable_length = max(0.0, tang_length - 2 * edge_margin)
    default_spacing = usable_length / max(1, count - 1) if count > 1 else 0.0
    spacing = clamp(
        float(metrics.get("peg_hole_spacing_mm", default_spacing)),
        diameter,
        usable_length / max(1, count - 1) if count > 1 else 0.0,
    ) if count > 1 else 0.0
    default_offset = max(edge_margin, (tang_length - spacing * max(0, count - 1)) / 2)
    offset = clamp(
        float(metrics.get("peg_hole_offset_from_guard_mm", default_offset)),
        edge_margin,
        max(edge_margin, tang_length - edge_margin - spacing * max(0, count - 1)),
    )
    return {
        "grip_depth_mm": grip_depth,
        "tang_length_mm": tang_length,
        "tang_width_mm": tang_width,
        "tang_thickness_mm": tang_thickness,
        "peg_hole_count": count,
        "peg_hole_diameter_mm": diameter,
        "peg_hole_spacing_mm": spacing,
        "peg_hole_offset_from_guard_mm": offset,
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
        fuller = """
module fuller_geometry() {
    channel_length = max(1, (blade_length_mm-ricasso_length_mm)*fuller_length_ratio);
    channel_depth = max(0.4, blade_thickness_mm*0.18);
    channel_start = ricasso_length_mm + (blade_length_mm-ricasso_length_mm)*0.04;
    for (face=[-1, 1]) translate([0, channel_start+channel_length/2,
        face*(blade_thickness_mm/2-channel_depth/2)])
        cube([fuller_width_mm, channel_length, channel_depth], center=true);
}
"""
        fuller_call = "fuller_geometry();"

    ridge = ""
    ridge_call = ""
    if ridge_enabled:
        ridge = """
module ridge_geometry() {
    translate([0, 0, blade_thickness_mm/2])
        linear_extrude(height=max(0.6, blade_thickness_mm*0.16))
            polygon([[-blade_base_width_mm*0.07, ricasso_length_mm],
                     [0, blade_length_mm*0.92],
                     [blade_base_width_mm*0.07, ricasso_length_mm]]);
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
        f"\nfuller_width_mm = {fuller_width_mm:g};"
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
