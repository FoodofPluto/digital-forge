"""Streamlit user interface for Digital Forge."""

import streamlit as st

from design_notes import get_design_notes
from geometry_audit import audit_geometry
from preview_service import export_with_openscad
from realism_rules import check_realism
from scad_generator import BLADE_STYLES, GUARD_STYLES, POMMEL_STYLES, generate_scad
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS

st.set_page_config(page_title="Digital Forge", page_icon="DF", layout="wide")
st.title("Digital Forge Version 4")
st.caption("Design a dimensionally grounded decorative sword and export previewable OpenSCAD.")
openscad_path = st.sidebar.text_input("OpenSCAD executable path", value="openscad")
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

st.subheader("Blade details")
detail_col1, detail_col2, detail_col3 = st.columns(3)
with detail_col1:
    fuller_enabled = st.checkbox("Enable fuller", value=False)
    ridge_enabled = st.checkbox("Enable central ridge", value=False)
with detail_col2:
    fuller_length_ratio = st.slider(
        "Fuller length ratio", 0.25, 0.85, 0.65, 0.05, disabled=not fuller_enabled
    )
with detail_col3:
    fuller_width_mm = st.number_input(
        "Fuller width (mm)", min_value=1.0, value=12.0, step=1.0, disabled=not fuller_enabled
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
audit = audit_geometry(metrics, sword_type, blade_style, guard_style, pommel_style)
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
)
st.subheader("Generated OpenSCAD")
st.code(scad, language="openscad")
st.download_button(
    "Download .scad", data=scad, file_name=f"{sword_type}.scad", mime="text/plain"
)

preview_col, stl_col = st.columns(2)
with preview_col:
    if st.button("Generate OpenSCAD Preview"):
        result = export_with_openscad(scad, openscad_path, "png")
        if result.success and result.path:
            st.success(result.message)
            st.image(str(result.path), caption="OpenSCAD preview")
        else:
            st.error(result.message)
with stl_col:
    if st.button("Generate STL"):
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
