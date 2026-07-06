"""Streamlit user interface for Digital Forge."""

import os

import streamlit as st

from app_config import load_config, save_openscad_path
from design_notes import get_design_notes
from geometry_audit import audit_geometry
from preview_service import export_with_openscad
from realism_rules import check_realism
from scad_generator import (
    BLADE_STYLES,
    COMPONENT_NAMES,
    GUARD_STYLES,
    POMMEL_STYLES,
    VISIBILITY_PRESETS,
    blade_detail_offset_for_position,
    generate_scad,
    has_visible_components,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS

st.set_page_config(page_title="Digital Forge", page_icon="DF", layout="wide")
st.title("Digital Forge Version 4")
st.caption("Design a dimensionally grounded decorative sword and export previewable OpenSCAD.")


def persist_openscad_path() -> None:
    save_openscad_path(st.session_state.openscad_path)


saved_path = load_config().get("openscad_path", "")
try:
    fallback_path = st.secrets.get("OPENSCAD_PATH", "")
except (FileNotFoundError, KeyError):
    fallback_path = ""
fallback_path = fallback_path or os.environ.get("OPENSCAD_PATH", "")
if "openscad_path" not in st.session_state:
    st.session_state.openscad_path = saved_path or fallback_path
openscad_path = st.sidebar.text_input(
    "OpenSCAD executable path", key="openscad_path", on_change=persist_openscad_path,
    help="Only PNG preview and STL export require OpenSCAD. SCAD generation and download do not.",
)
st.sidebar.caption("The .scad file can always be generated and downloaded without OpenSCAD.")
debug_geometry = st.sidebar.toggle(
    "Debug geometry",
    value=False,
    help="Add anchor, centerline, and translucent bounding markers to generated SCAD.",
)

sword_type = st.selectbox("Sword type", list(SWORD_PRESETS))
preset = SWORD_PRESETS[sword_type]

style_col1, style_col2, style_col3 = st.columns(3)
with style_col1:
    blade_style = st.selectbox("Blade style", BLADE_STYLES)
with style_col2:
    guard_style = st.selectbox("Guard style", GUARD_STYLES)
with style_col3:
    pommel_style = st.selectbox("Pommel style", POMMEL_STYLES)

st.subheader("Assembly view")


def apply_visibility_preset() -> None:
    for component, visible in VISIBILITY_PRESETS[st.session_state.visibility_preset].items():
        st.session_state[f"show_{component}"] = visible


visibility_preset = st.selectbox(
    "Quick preset",
    list(VISIBILITY_PRESETS),
    key="visibility_preset",
    on_change=apply_visibility_preset,
)
visibility_columns = st.columns(len(COMPONENT_NAMES))
visible_components = {}
for column, component in zip(visibility_columns, COMPONENT_NAMES):
    key = f"show_{component}"
    if key not in st.session_state:
        st.session_state[key] = VISIBILITY_PRESETS[visibility_preset][component]
    with column:
        visible_components[component] = st.checkbox(
            component.title(), key=key, help=f"Show or hide the {component} at its assembly position."
        )
has_visible_component = has_visible_components(visible_components)
if not has_visible_component:
    st.warning("Select at least one component to preview or export.")

st.subheader("Dimensions")
metric_columns = st.columns(3)
metrics = {}
for index, name in enumerate(REQUIRED_METRICS):
    spec = preset[name]
    with metric_columns[index % 3]:
        metrics[name] = st.number_input(
            name.replace("_mm", "").replace("_", " ").title() + " (mm)",
            min_value=0.0 if name == "ricasso_length_mm" else 0.1,
            value=float(spec["default"]),
            step=1.0,
            key=f"{sword_type}_{name}",
            help=f"Typical range: {spec['min']:g}-{spec['max']:g} mm",
        )

st.subheader("Tang and peg details")
tang_col1, tang_col2, tang_col3 = st.columns(3)
grip_length = metrics["grip_length_mm"]
grip_width = metrics["grip_width_mm"]
grip_depth = max(metrics["blade_thickness_mm"] * 1.8, grip_width * 0.68)
with tang_col1:
    metrics["tang_length_mm"] = st.number_input(
        "Tang length (mm)", 1.0, float(grip_length * 0.98), float(grip_length * 0.9), 1.0,
        key=f"{sword_type}_tang_length_mm",
        help="Internal prop core length; kept shorter than the external grip."
    )
    metrics["tang_width_mm"] = st.number_input(
        "Tang width (mm)", 1.0, float(grip_width * 0.9), float(grip_width * 0.5), 0.5,
        key=f"{sword_type}_tang_width_mm"
    )
with tang_col2:
    metrics["tang_thickness_mm"] = st.number_input(
        "Tang thickness (mm)", 1.0, float(grip_depth * 0.9),
        float(min(max(2.4, metrics["blade_thickness_mm"] * 0.72), grip_depth * 0.55)), 0.2,
        key=f"{sword_type}_tang_thickness_mm"
    )
    metrics["peg_hole_count"] = st.selectbox(
        "Peg hole count", (0, 1, 2, 3), key=f"{sword_type}_peg_hole_count"
    )
with tang_col3:
    metrics["peg_hole_diameter_mm"] = st.number_input(
        "Peg hole diameter (mm)", 1.0, float(max(1.0, grip_width * 0.25)), 4.0, 0.5,
        key=f"{sword_type}_peg_hole_diameter_mm"
    )
    metrics["peg_hole_spacing_mm"] = st.number_input(
        "Peg hole spacing (mm)", 1.0, float(max(1.0, grip_length)),
        float(max(8.0, grip_length * 0.22)), 1.0, disabled=metrics["peg_hole_count"] < 2,
        key=f"{sword_type}_peg_hole_spacing_mm",
        help="Center-to-center spacing; generation clamps holes inside the tang."
    )
metrics["peg_hole_offset_from_guard_mm"] = max(6.0, grip_length * 0.12)

st.subheader("Blade details")
detail_col1, detail_col2, detail_col3 = st.columns(3)
with detail_col1:
    fuller_enabled = st.checkbox("Enable fuller", value=False)
    ridge_enabled = st.checkbox("Enable central ridge", value=False)
with detail_col2:
    fuller_length_ratio = st.slider(
        "Fuller length ratio", 0.35, 0.90, 0.65, 0.05, disabled=not fuller_enabled,
        help="Percentage of usable blade length; generation keeps ricasso and tip margins.",
    )
with detail_col3:
    fuller_width_mm = st.number_input(
        "Fuller width (mm)", min_value=1.0, value=12.0, step=1.0, disabled=not fuller_enabled
    )
    fuller_depth_mm = st.number_input(
        "Fuller depth (mm)", min_value=0.35, max_value=3.0, value=0.8, step=0.1,
        disabled=not fuller_enabled,
    )
position_col1, position_col2 = st.columns(2)
position_options = ("Center", "Slight left", "Slight right")
with position_col1:
    fuller_position = st.selectbox(
        "Fuller position", position_options, disabled=not fuller_enabled
    )
with position_col2:
    ridge_position = st.selectbox(
        "Ridge position", position_options, disabled=not ridge_enabled
    )
fuller_offset_x = blade_detail_offset_for_position(
    fuller_position, metrics["blade_base_width_mm"], metrics["blade_length_mm"], blade_style
)
ridge_offset_x = blade_detail_offset_for_position(
    ridge_position, metrics["blade_base_width_mm"], metrics["blade_length_mm"], blade_style
)

st.subheader("Design notes")
st.info(get_design_notes(sword_type, blade_style, guard_style, pommel_style))

warnings = check_realism(sword_type, metrics, fuller_enabled, fuller_length_ratio)
if warnings:
    st.subheader("Realism notes")
    for warning in warnings:
        st.warning(warning)
else:
    st.success("All dimensions are within the preset's typical ranges and proportions.")

st.subheader("Geometry audit")
audit = audit_geometry(
    metrics, sword_type, blade_style, guard_style, pommel_style, visible_components,
    fuller_enabled, fuller_length_ratio, ridge_enabled,
    fuller_offset_x, ridge_offset_x, fuller_width_mm, fuller_depth_mm,
)
audit_warning_col, audit_info_col, audit_pass_col = st.columns(3)
with audit_warning_col:
    st.markdown("**Warnings**")
    if audit["warnings"]:
        for message in audit["warnings"]:
            st.warning(message)
    else:
        st.success("No geometry warnings.")
with audit_info_col:
    st.markdown("**Notes**")
    if audit["info"]:
        for message in audit["info"]:
            st.info(message)
    else:
        st.caption("No additional geometry notes.")
with audit_pass_col:
    st.markdown("**Checks passed**")
    for message in audit["passes"]:
        st.success(message)

scad = generate_scad(
    sword_type,
    metrics,
    blade_style,
    guard_style,
    pommel_style,
    fuller_enabled,
    fuller_length_ratio,
    fuller_width_mm,
    ridge_enabled,
    debug_geometry,
    visible_components,
    fuller_offset_x,
    ridge_offset_x,
    fuller_depth_mm,
)
st.subheader("Generated OpenSCAD")
st.code(scad, language="openscad")
st.download_button(
    "Download .scad", data=scad, file_name=f"{sword_type}.scad", mime="text/plain"
)

preview_col, stl_col = st.columns(2)
with preview_col:
    if st.button("Generate OpenSCAD Preview", disabled=not has_visible_component):
        result = export_with_openscad(scad, openscad_path, "png")
        if result.success and result.path:
            st.success(result.message)
            st.image(str(result.path), caption="OpenSCAD preview")
        else:
            st.error(result.message)
with stl_col:
    if st.button("Generate STL", disabled=not has_visible_component):
        result = export_with_openscad(scad, openscad_path, "stl")
        if result.success and result.path:
            try:
                stl_data = result.path.read_bytes()
            except OSError as exc:
                st.error(f"Generated STL could not be read: {exc}")
            else:
                st.success(result.message)
                st.download_button(
                    "Download preview.stl",
                    data=stl_data,
                    file_name="preview.stl",
                    mime="model/stl",
                )
        else:
            st.error(result.message)

with st.expander("Known limitations"):
    st.markdown(
        """
- PNG and STL generation require a local OpenSCAD installation.
- Command-line previews use OpenSCAD's default camera.
- Geometry is simplified, decorative, and not intended for fabrication decisions.
- Debug markers are included in exported geometry only while Debug geometry is enabled.
"""
    )
