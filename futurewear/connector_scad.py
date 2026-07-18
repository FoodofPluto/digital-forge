"""Self-contained OpenSCAD generation for Futurewear connectors."""

from .constants import MODULAR_STANDARD_VERSION
from .connectors import (
    CUSTOMER_CONNECTOR_NAMES,
    ConnectorParameters,
    ConnectorType,
    derive_male_dimensions,
    derive_receiver_dimensions,
)


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _header(params: ConnectorParameters, title: str) -> str:
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    return f"""// Digital Forge Modular Standard V1: {MODULAR_STANDARD_VERSION}
// {title}
// Connector type: {params.connector_type.value}
// Customer name: {CUSTOMER_CONNECTOR_NAMES[params.connector_type]}
// Connector size: {params.size.value}
// Gender: {params.gender.value}
// Nominal width/depth/engagement: {params.nominal_interface_width_mm:g} / {params.nominal_interface_depth_mm:g} / {params.engagement_length_mm:g} mm
// Generated male width/depth/engagement: {male.width_mm:g} / {male.depth_mm:g} / {male.engagement_length_mm:g} mm
// Generated receiver width/depth/engagement: {receiver.width_mm:g} / {receiver.depth_mm:g} / {receiver.engagement_length_mm:g} mm
// Clearance is per side on width; depth and engagement receive one clearance relief.
// Fit clearance per side: {params.fit_clearance_mm:g} mm
// Printer compensation: {params.printer_compensation_mm:g} mm
"""


def connector_assignments(params: ConnectorParameters) -> str:
    male = derive_male_dimensions(params)
    receiver = derive_receiver_dimensions(params)
    return f"""standard_version = "{MODULAR_STANDARD_VERSION}";
nominal_interface_width_mm = {params.nominal_interface_width_mm:g};
nominal_interface_depth_mm = {params.nominal_interface_depth_mm:g};
engagement_length_mm = {params.engagement_length_mm:g};
fit_clearance_mm = {params.fit_clearance_mm:g};
printer_compensation_mm = {params.printer_compensation_mm:g};
minimum_surrounding_wall_mm = {params.minimum_surrounding_wall_mm:g};
stop_thickness_mm = {params.stop_thickness_mm:g};
retention_depth_mm = {params.retention_depth_mm:g};
edge_radius_mm = {params.edge_radius_mm:g};
dock_keyed = {_bool(params.keyed)};
dock_male_width_mm = {male.width_mm:g};
dock_male_depth_mm = {male.depth_mm:g};
dock_male_engagement_mm = {male.engagement_length_mm:g};
dock_receiver_width_mm = {receiver.width_mm:g};
dock_receiver_depth_mm = {receiver.depth_mm:g};
dock_receiver_engagement_mm = {receiver.engagement_length_mm:g};
dock_key_offset_mm = {male.key_offset_mm:g};
entrance_chamfer_mm = {male.entrance_chamfer_mm:g};
eps = 0.04;"""


def _common_modules(params: ConnectorParameters) -> str:
    return f"""
module df_mod_rounded_block(size_vec, radius=edge_radius_mm) {{
    // Lightweight deterministic proxy for softened printable geometry.
    cube(size_vec, center=true);
}}

module df_mod_insertion_arrow() {{
    color("lime") translate([0, -dock_male_engagement_mm/2 - 8, dock_male_depth_mm + 3])
        rotate([90, 0, 0]) cylinder(h=14, r1=1.8, r2=0, center=false);
}}

module df_mod_mounting_plane() {{
    color([0.2, 0.6, 1.0, 0.22]) translate([0, 0, -0.08])
        cube([dock_receiver_width_mm + 8, dock_receiver_engagement_mm + 8, 0.12], center=true);
}}

module df_mod_clearance_envelope() {{
    color([1.0, 0.8, 0.1, 0.28])
        cube([dock_receiver_width_mm, dock_receiver_engagement_mm, dock_receiver_depth_mm], center=true);
}}

module dock_key_rib(length_mm, depth_mm) {{
    if (dock_keyed)
        translate([dock_male_width_mm/2 - dock_key_offset_mm, 0, depth_mm/2 + 0.18])
            cube([max(0.8, dock_key_offset_mm), length_mm, 0.36], center=true);
}}

module dock_friction_rib(length_mm) {{
    if (retention_depth_mm > 0)
        translate([0, -length_mm*0.20, dock_male_depth_mm/2 + retention_depth_mm/2])
            cube([dock_male_width_mm*0.52, max(1.2, length_mm*0.18), retention_depth_mm], center=true);
}}

module dock_positive() {{
    union() {{
        color("gainsboro") df_mod_rounded_block([dock_male_width_mm, dock_male_engagement_mm, dock_male_depth_mm]);
        translate([0, dock_male_engagement_mm/2 + stop_thickness_mm/2, 0])
            color("silver") cube([dock_male_width_mm + minimum_surrounding_wall_mm, stop_thickness_mm, dock_male_depth_mm], center=true);
        color("white") dock_key_rib(dock_male_engagement_mm, dock_male_depth_mm);
        color("lightgray") dock_friction_rib(dock_male_engagement_mm);
    }}
}}

module dock_receiver_cavity() {{
    union() {{
        cube([dock_receiver_width_mm, dock_receiver_engagement_mm + eps, dock_receiver_depth_mm + eps], center=true);
        translate([dock_receiver_width_mm/2 - dock_key_offset_mm, 0, dock_receiver_depth_mm/2 + 0.18])
            cube([max(0.8, dock_key_offset_mm) + fit_clearance_mm*2, dock_receiver_engagement_mm + eps, 0.46 + fit_clearance_mm], center=true);
        translate([0, -dock_receiver_engagement_mm/2 - entrance_chamfer_mm/2, 0])
            cube([dock_receiver_width_mm + entrance_chamfer_mm*2, entrance_chamfer_mm, dock_receiver_depth_mm + entrance_chamfer_mm], center=true);
    }}
}}

module dock_receiver_body() {{
    difference() {{
        color("dimgray") translate([0, 0, -minimum_surrounding_wall_mm/2])
            cube([
                dock_receiver_width_mm + minimum_surrounding_wall_mm*2,
                dock_receiver_engagement_mm + stop_thickness_mm + minimum_surrounding_wall_mm*2,
                dock_receiver_depth_mm + minimum_surrounding_wall_mm
            ], center=true);
        translate([0, -stop_thickness_mm/2, dock_receiver_depth_mm/2 - minimum_surrounding_wall_mm/2])
            dock_receiver_cavity();
    }}
    color("tomato") translate([0, dock_receiver_engagement_mm/2, dock_receiver_depth_mm/2 - minimum_surrounding_wall_mm/2])
        cube([dock_receiver_width_mm, stop_thickness_mm, max(0.8, dock_receiver_depth_mm)], center=true);
}}

module cord_loop_positive() {{
    opening_w = max(3, nominal_interface_width_mm - minimum_surrounding_wall_mm*2);
    opening_h = max(2.4, nominal_interface_depth_mm);
    difference() {{
        color("gainsboro") cube([nominal_interface_width_mm, engagement_length_mm, minimum_surrounding_wall_mm*2 + opening_h], center=true);
        color("black") cube([opening_w, engagement_length_mm + eps, opening_h], center=true);
        translate([0, -engagement_length_mm/2, 0])
            cube([opening_w + entrance_chamfer_mm, entrance_chamfer_mm*2, opening_h + entrance_chamfer_mm], center=true);
        translate([0, engagement_length_mm/2, 0])
            cube([opening_w + entrance_chamfer_mm, entrance_chamfer_mm*2, opening_h + entrance_chamfer_mm], center=true);
    }}
}}

module quarter_turn_positive() {{
    color("gainsboro") union() {{
        cylinder(h=dock_male_depth_mm, r=dock_male_width_mm/4, center=true);
        cube([dock_male_width_mm*0.82, dock_male_width_mm*0.34, dock_male_depth_mm], center=true);
        rotate([0, 0, 90]) cube([dock_male_width_mm*0.58, dock_male_width_mm*0.34, dock_male_depth_mm], center=true);
    }}
}}

module quarter_turn_receiver() {{
    difference() {{
        color("dimgray") cube([dock_receiver_width_mm + minimum_surrounding_wall_mm*2, dock_receiver_width_mm + minimum_surrounding_wall_mm*2, dock_receiver_depth_mm + minimum_surrounding_wall_mm], center=true);
        cylinder(h=dock_receiver_depth_mm + eps, r=dock_receiver_width_mm/3, center=true);
        cube([dock_receiver_width_mm*0.95, dock_receiver_width_mm*0.38, dock_receiver_depth_mm + eps], center=true);
    }}
    color("tomato") translate([dock_receiver_width_mm*0.28, dock_receiver_width_mm*0.28, dock_receiver_depth_mm/2])
        cube([stop_thickness_mm, stop_thickness_mm*2, max(0.8, dock_receiver_depth_mm)], center=true);
}}
"""


def _top_call(params: ConnectorParameters, call: str) -> str:
    debug = ""
    if params.debug_geometry:
        debug = """
df_mod_mounting_plane();
df_mod_clearance_envelope();
df_mod_insertion_arrow();"""
    return f"{debug}\n{call}\n"


def generate_connector_positive_scad(params: ConnectorParameters) -> str:
    module_call = "cord_loop_positive();" if params.connector_type == ConnectorType.CORD_LOOP else (
        "quarter_turn_positive();" if params.connector_type == ConnectorType.TWIST_LOCK else "dock_positive();"
    )
    return _header(params, "Positive connector geometry") + "$fn = 48;\n" + connector_assignments(params) + _common_modules(params) + _top_call(params, module_call)


def generate_connector_receiver_scad(params: ConnectorParameters) -> str:
    if params.connector_type == ConnectorType.CORD_LOOP:
        module_call = "cord_loop_positive();"
    elif params.connector_type == ConnectorType.TWIST_LOCK:
        module_call = "quarter_turn_receiver();"
    else:
        module_call = "dock_receiver_body();"
    return _header(params, "Receiver connector geometry") + "$fn = 48;\n" + connector_assignments(params) + _common_modules(params) + _top_call(params, module_call)


def generate_connector_pair_scad(params: ConnectorParameters) -> str:
    if params.connector_type == ConnectorType.CORD_LOOP:
        call = "cord_loop_positive();"
    elif params.connector_type == ConnectorType.TWIST_LOCK:
        call = "translate([-dock_receiver_width_mm,0,0]) quarter_turn_positive(); translate([dock_receiver_width_mm,0,0]) quarter_turn_receiver();"
    else:
        call = "translate([-dock_receiver_width_mm,0,0]) dock_positive(); translate([dock_receiver_width_mm,0,0]) dock_receiver_body();"
    return _header(params, "Paired connector fit preview") + "$fn = 48;\n" + connector_assignments(params) + _common_modules(params) + _top_call(params, call)


def generate_connector_debug_scad(params: ConnectorParameters) -> str:
    debug_params = params if params.debug_geometry else params.__class__(**{**params.__dict__, "debug_geometry": True})
    return generate_connector_pair_scad(debug_params)


def generate_null_tile_scad(params: ConnectorParameters) -> str:
    tile_width = params.nominal_interface_width_mm + params.minimum_surrounding_wall_mm * 1.6
    tile_length = params.engagement_length_mm + params.stop_thickness_mm
    tile_depth = params.nominal_interface_depth_mm + 1.2
    return _header(params, "Null Tile flush blank module") + f"""$fn = 48;
{connector_assignments(params)}
{_common_modules(params)}

module null_tile_face() {{
    color("gainsboro") translate([0, stop_thickness_mm/2, dock_male_depth_mm/2 + 0.62])
        cube([{tile_width:g}, {tile_length:g}, {tile_depth:g}], center=true);
}}

module null_tile() {{
    union() {{
        dock_positive();
        null_tile_face();
    }}
}}

null_tile();
"""
