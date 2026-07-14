"""Streamlit user interface for Digital Forge."""

import os
from io import BytesIO
from zipfile import ZipFile

import streamlit as st

from app_config import load_config, save_openscad_path
from design_notes import get_design_notes
from geometry_audit import (
    audit_bracer_geometry,
    audit_custom_stl_scabbard_geometry,
    audit_geometry,
    audit_pauldron_geometry,
    audit_scabbard_geometry,
)
from preview_service import SCABBARD_CAMERA_PRESETS, export_preview_set, export_with_openscad
from realism_rules import check_realism
from scad_generator import (
    ARMOR_TYPES,
    BLADE_STYLES,
    BRACER_BINDING_STYLES,
    BRACER_PANEL_TYPES,
    DEFAULT_BRACER_METRICS,
    DEFAULT_PAULDRON_METRICS,
    COMPONENT_NAMES,
    GUARD_STYLES,
    PAULDRON_STYLES,
    POMMEL_STYLES,
    VISIBILITY_PRESETS,
    blade_detail_offset_for_position,
    generate_armor_scad,
    generate_scad,
    has_visible_components,
    resolve_bracer_metrics,
)
from scabbard_generator import (
    CUSTOM_STL_PREVIEW_MODES,
    DEFAULT_SCABBARD_CLEARANCE_MM,
    DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM,
    DEFAULT_SCABBARD_WALL_THICKNESS_MM,
    DEFAULT_THROAT_LENGTH_MM,
    MAX_CUSTOM_STL_UPLOAD_BYTES,
    MAX_SCABBARD_CLEARANCE_MM,
    MAX_SCABBARD_WALL_THICKNESS_MM,
    MIN_SCABBARD_CLEARANCE_MM,
    MIN_SCABBARD_WALL_THICKNESS_MM,
    SCABBARD_FIT_MODES,
    SCABBARD_SPLIT_MODES,
    generate_custom_stl_scabbard_scad,
    generate_scabbard_scad,
    save_uploaded_stl,
)
from sword_presets import REQUIRED_METRICS, SWORD_PRESETS
from ui_params import (
    BRACER_DECORATION_PRESETS,
    GENERATION_CATEGORIES,
    build_bracer_generation_params,
    build_pauldron_generation_params,
    build_scabbard_generation_params,
    enabled_bracer_detail_labels,
    enabled_pauldron_detail_labels,
    normalize_pauldron_detail_options,
)

st.set_page_config(page_title="Digital Forge", page_icon="DF", layout="wide")
st.title("Digital Forge Version 4")
st.caption("Design dimensionally grounded decorative fantasy props and export previewable OpenSCAD.")


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

generation_category = st.selectbox("Generation category", GENERATION_CATEGORIES, index=0)
can_export = True

if generation_category == "Sword":
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
    can_export = has_visible_components(visible_components)
    if not can_export:
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
    download_name = f"{sword_type}.scad"
elif generation_category == "Scabbard":
    st.subheader("Scabbard")
    st.caption("Fitted scabbards derive their cavity and shell from the selected blade geometry.")
    scabbard_mode = st.radio(
        "Scabbard mode",
        ("Blade-derived scabbard", "Experimental STL-derived scabbard"),
        horizontal=True,
        key="scabbard_mode",
    )
    sword_type = st.selectbox("Source sword preset", list(SWORD_PRESETS), key="scabbard_sword_type")
    preset = SWORD_PRESETS[sword_type]
    if scabbard_mode == "Blade-derived scabbard":
        blade_label = st.selectbox(
            "Blade geometry",
            ("Symmetrical Tapered", "Leaf", "Curved", "Falchion"),
            key="scabbard_blade_type",
            help="This selects the blade profile the fitted scabbard follows; it is not a separate scabbard preset.",
        )
        blade_style = {
            "Symmetrical Tapered": "tapered",
            "Leaf": "leaf",
            "Curved": "curved",
            "Falchion": "falchion",
        }[blade_label]

        st.subheader("Inherited blade dimensions")
        st.info("Compatibility: Symmetrical Tapered, Leaf, Curved, and Falchion are supported by fitted blade-envelope geometry.")
        scabbard_metric_columns = st.columns(3)
        scabbard_metrics = {}
        for index, name in enumerate(("blade_length_mm", "blade_base_width_mm", "blade_tip_width_mm", "blade_thickness_mm", "ricasso_length_mm")):
            spec = preset[name]
            with scabbard_metric_columns[index % 3]:
                scabbard_metrics[name] = st.number_input(
                    name.replace("_mm", "").replace("_", " ").title() + " (mm)",
                    min_value=0.0 if name == "ricasso_length_mm" else 0.1,
                    value=float(spec["default"]),
                    step=1.0 if name != "blade_thickness_mm" else 0.1,
                    key=f"scabbard_{sword_type}_{name}",
                    help=f"Inherited from the corresponding sword configuration. Typical range: {spec['min']:g}-{spec['max']:g} mm",
                )

        st.subheader("Fit and construction")
        fit_col1, fit_col2, fit_col3 = st.columns(3)
        with fit_col1:
            fit_mode = st.selectbox("Exterior mode", SCABBARD_FIT_MODES, key="scabbard_fit_mode")
            clearance_per_side_mm = st.number_input(
                "Clearance per side (mm)",
                min_value=0.0,
                max_value=float(MAX_SCABBARD_CLEARANCE_MM * 2),
                value=float(DEFAULT_SCABBARD_CLEARANCE_MM),
                step=0.05,
                help="Applied around blade width and thickness. Values outside the safe range are clamped.",
            )
        with fit_col2:
            wall_thickness_mm = st.number_input(
                "Wall thickness (mm)",
                min_value=0.1,
                max_value=float(MAX_SCABBARD_WALL_THICKNESS_MM * 2),
                value=float(DEFAULT_SCABBARD_WALL_THICKNESS_MM),
                step=0.1,
                help="Minimum material from cavity to exterior sides/faces.",
            )
            seam_allowance_mm = st.number_input(
                "Seam allowance (mm)",
                min_value=0.0,
                max_value=1.5,
                value=float(DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM),
                step=0.05,
                help="Small offset for split-print cuts to avoid coplanar zero-thickness seams.",
            )
        with fit_col3:
            split_mode = st.selectbox("Print split", SCABBARD_SPLIT_MODES[:-1], key="scabbard_split_mode")
            throat_enabled = st.checkbox("Throat collar", value=True)
            end_cap_enabled = st.checkbox("End cap", value=True)

        try:
            scabbard_params, scabbard_warnings = build_scabbard_generation_params(
                blade_style,
                scabbard_metrics,
                clearance_per_side_mm,
                wall_thickness_mm,
                split_mode,
                throat_enabled,
                end_cap_enabled,
                fit_mode,
                seam_allowance_mm,
            )
            can_export = True
        except ValueError as exc:
            scabbard_params = {}
            scabbard_warnings = [str(exc)]
            can_export = False

        st.subheader("Geometry audit")
        scabbard_audit = audit_scabbard_geometry(
            scabbard_metrics,
            blade_style,
            clearance_per_side_mm,
            wall_thickness_mm,
            split_mode,
            throat_enabled,
            end_cap_enabled,
            fit_mode,
            seam_allowance_mm,
        )
        audit_warning_col, audit_info_col, audit_pass_col = st.columns(3)
        with audit_warning_col:
            st.markdown("**Warnings**")
            warnings = scabbard_warnings + scabbard_audit["warnings"]
            if warnings:
                for message in dict.fromkeys(warnings):
                    st.warning(message)
            else:
                st.success("No scabbard geometry warnings.")
        with audit_info_col:
            st.markdown("**Notes**")
            st.info(f"Safe clearance range: {MIN_SCABBARD_CLEARANCE_MM:g}-{MAX_SCABBARD_CLEARANCE_MM:g} mm per side.")
            st.info(f"Safe wall thickness minimum: {MIN_SCABBARD_WALL_THICKNESS_MM:g} mm.")
            for message in scabbard_audit["info"]:
                st.info(message)
        with audit_pass_col:
            st.markdown("**Checks passed**")
            for message in scabbard_audit["passes"]:
                st.success(message)

        scad = generate_scabbard_scad(**scabbard_params) if scabbard_params else "// Unsupported scabbard configuration."
        download_name = f"{sword_type}_{blade_style}_scabbard.scad"
    else:
        st.subheader("Custom STL Scabbard")
        st.warning("Experimental blade-only STL workflow. Use a watertight, manifold blade mesh aligned to the project axis.")
        st.caption(
            "Final STL export contains only the hollow scabbard. The uploaded blade is used to create the cavity "
            "and appears only in diagnostic previews."
        )
        uploaded_stl = st.file_uploader(
            "Upload blade STL",
            type=["stl"],
            key="custom_scabbard_stl",
            help=f"Only .stl files up to {MAX_CUSTOM_STL_UPLOAD_BYTES // (1024 * 1024)} MB are accepted.",
        )
        saved_stl_path = None
        stl_save_warnings = []
        if uploaded_stl is not None:
            saved_stl_path, stl_save_warnings = save_uploaded_stl(uploaded_stl)
            if saved_stl_path:
                st.success(f"Saved controlled STL import: {saved_stl_path.name}")

        stl_col1, stl_col2, stl_col3 = st.columns(3)
        with stl_col1:
            stl_scale = st.number_input("Scale", min_value=0.05, max_value=20.0, value=1.0, step=0.05)
            stl_clearance = st.number_input("Cavity clearance (mm)", min_value=0.0, max_value=6.0, value=float(DEFAULT_SCABBARD_CLEARANCE_MM), step=0.05)
            stl_wall = st.number_input("Shell wall thickness (mm)", min_value=0.1, max_value=24.0, value=float(DEFAULT_SCABBARD_WALL_THICKNESS_MM), step=0.1)
        with stl_col2:
            stl_rx = st.number_input("Rotate X (deg)", value=0.0, step=5.0)
            stl_ry = st.number_input("Rotate Y (deg)", value=0.0, step=5.0)
            stl_rz = st.number_input("Rotate Z (deg)", value=0.0, step=5.0)
        with stl_col3:
            stl_split = st.selectbox("Print split", SCABBARD_SPLIT_MODES[:-1], key="custom_stl_split")
            stl_seam = st.number_input("Seam allowance (mm)", min_value=0.0, max_value=1.5, value=float(DEFAULT_SCABBARD_SEAM_ALLOWANCE_MM), step=0.05, key="custom_stl_seam")
            stl_throat = st.number_input("Throat opening length (mm)", min_value=1.0, max_value=80.0, value=float(DEFAULT_THROAT_LENGTH_MM), step=1.0, key="custom_stl_throat")
            stl_preview_mode = st.selectbox("Preview mode", CUSTOM_STL_PREVIEW_MODES, key="custom_stl_preview_mode")

        if saved_stl_path:
            custom_stl_generation_params = {
                "stl_path": saved_stl_path,
                "object_type": "Blade only",
                "rotate_x_deg": stl_rx,
                "rotate_y_deg": stl_ry,
                "rotate_z_deg": stl_rz,
                "scale": stl_scale,
                "clearance_mm": stl_clearance,
                "wall_thickness_mm": stl_wall,
                "throat_length_mm": stl_throat,
                "split_mode": stl_split,
                "seam_allowance_mm": stl_seam,
            }
            scad, custom_warnings = generate_custom_stl_scabbard_scad(
                **custom_stl_generation_params,
                preview_mode=stl_preview_mode,
            )
            custom_stl_export_scad, custom_export_warnings = generate_custom_stl_scabbard_scad(
                **custom_stl_generation_params,
                preview_mode="Scabbard Only",
            )
            custom_warnings.extend(custom_export_warnings)
            scabbard_audit = audit_custom_stl_scabbard_geometry(
                str(saved_stl_path), "Blade only", stl_rx, stl_ry, stl_rz, stl_scale, stl_clearance, stl_wall,
                throat_length_mm=stl_throat, split_mode=stl_split, seam_allowance_mm=stl_seam,
            )
            warnings = stl_save_warnings + custom_warnings + scabbard_audit["warnings"]
            for message in dict.fromkeys(warnings):
                st.warning(message)
            for message in scabbard_audit["info"]:
                st.info(message)
            for message in scabbard_audit["passes"]:
                st.success(message)
            blocking_warning = any(
                phrase in message.lower()
                for message in warnings
                for phrase in ("missing", "could not", "outside the controlled", "accept only")
            )
            can_export = not blocking_warning
        else:
            scad = "// Upload a blade-only STL to generate an experimental STL-derived scabbard."
            custom_stl_export_scad = scad
            for message in stl_save_warnings:
                st.warning(message)
            can_export = False
        download_name = f"{sword_type}_custom_stl_scabbard.scad"
else:
    st.subheader("Armor")
    armor_type = st.selectbox("Armor type", ARMOR_TYPES)

    st.caption("Armor models are decorative/prototype fantasy prop geometry only, not wearable protective equipment.")

    if armor_type == "Bracer":
        bracer_style = "Plain"
        st.subheader("Bracer Dimensions")
        bracer_columns = st.columns(3)
        bracer_specs = {
            "bracer_length_mm": (60.0, 420.0, DEFAULT_BRACER_METRICS["bracer_length_mm"], 1.0),
            "wrist_width_mm": (35.0, 180.0, DEFAULT_BRACER_METRICS["wrist_width_mm"], 1.0),
            "forearm_width_mm": (45.0, 240.0, DEFAULT_BRACER_METRICS["forearm_width_mm"], 1.0),
            "bracer_depth_mm": (24.0, 140.0, DEFAULT_BRACER_METRICS["bracer_depth_mm"], 1.0),
        }
        bracer_metrics = {}
        for index, (name, spec) in enumerate(bracer_specs.items()):
            minimum, maximum, default, step = spec
            with bracer_columns[index % 3]:
                bracer_metrics[name] = st.number_input(
                    name.replace("_mm", "").replace("_", " ").title() + (" (deg)" if name.endswith("degrees") else " (mm)"),
                    minimum,
                    maximum,
                    float(default),
                    step,
                    key=f"armor_{name}",
                )

        st.subheader("Shell and Opening")
        shell_col1, shell_col2, shell_col3 = st.columns(3)
        with shell_col1:
            bracer_metrics["bracer_wall_thickness_mm"] = st.number_input(
                "Wall thickness (mm)", 2.4, 12.0,
                float(DEFAULT_BRACER_METRICS["bracer_wall_thickness_mm"]), 0.2,
                key="armor_bracer_wall_thickness_mm",
                help="Printable shell wall; generation clamps it inside the outer profile.",
            )
        with shell_col2:
            bracer_metrics["bracer_opening_width_mm"] = st.number_input(
                "Opening width (mm)", 16.0, 120.0,
                float(DEFAULT_BRACER_METRICS["bracer_opening_width_mm"]), 1.0,
                key="armor_bracer_opening_width_mm",
                help="Gap along the inner forearm so the bracer reads as wearable.",
            )
        with shell_col3:
            bracer_metrics["bracer_arc_degrees"] = st.number_input(
                "Coverage angle (deg)", 120.0, 260.0,
                float(DEFAULT_BRACER_METRICS["bracer_arc_degrees"]), 1.0,
                key="armor_bracer_arc_degrees",
                help="How far the shell wraps around the forearm before the opening.",
            )
        bracer_metrics["bracer_exterior_finishing_allowance_mm"] = st.slider(
            "Exterior Finishing Allowance (mm)",
            0.0,
            1.5,
            float(DEFAULT_BRACER_METRICS["bracer_exterior_finishing_allowance_mm"]),
            0.1,
            key="armor_bracer_exterior_finishing_allowance_mm",
            help="Adds sandable stock to exterior shell surfaces without reducing the arm cavity or closure passages.",
        )

        st.subheader("Decoration")
        preset_names = tuple(BRACER_DECORATION_PRESETS)
        default_preset = "Plain"
        decoration_preset = st.selectbox(
            "Decoration",
            preset_names,
            index=preset_names.index(default_preset),
            key="armor_bracer_decoration",
            help="Plain shell or a broad raised exterior panel for maker-finished original decoration.",
        )
        detail_options = dict(BRACER_DECORATION_PRESETS[decoration_preset])

        if decoration_preset == "Raised Design Panel":
            panel_seed = dict(bracer_metrics)
            if "armor_bracer_panel_type" in st.session_state:
                panel_seed["bracer_panel_type"] = st.session_state["armor_bracer_panel_type"]
            for name in (
                "bracer_panel_length_mm",
                "bracer_panel_width_mm",
                "bracer_panel_height_mm",
                "bracer_panel_edge_roundness_mm",
                "bracer_panel_position_mm",
            ):
                if f"armor_{name}" in st.session_state:
                    panel_seed[name] = st.session_state[f"armor_{name}"]
            panel_bounds, _ = resolve_bracer_metrics(panel_seed)

            st.subheader("Raised Design Panel")
            panel_type = st.selectbox(
                "Panel Type",
                BRACER_PANEL_TYPES,
                index=BRACER_PANEL_TYPES.index(panel_bounds["bracer_panel_type"]),
                key="armor_bracer_panel_type",
                help=(
                    "Wide Panel provides a broad maker-finished surface. "
                    "Narrow Panel provides a slimmer inscription or design field."
                ),
            )
            panel_seed["bracer_panel_type"] = panel_type
            panel_bounds, _ = resolve_bracer_metrics(panel_seed)
            width_key = "armor_bracer_panel_width_mm"
            if width_key in st.session_state:
                st.session_state[width_key] = max(
                    float(panel_bounds["bracer_panel_min_width_mm"]),
                    min(float(st.session_state[width_key]), float(panel_bounds["bracer_panel_max_width_mm"])),
                )
                panel_seed["bracer_panel_width_mm"] = st.session_state[width_key]
                panel_bounds, _ = resolve_bracer_metrics(panel_seed)
            height_key = "armor_bracer_panel_height_mm"
            if height_key in st.session_state:
                st.session_state[height_key] = max(
                    float(panel_bounds["bracer_panel_min_height_mm"]),
                    min(float(st.session_state[height_key]), float(panel_bounds["bracer_panel_max_height_mm"])),
                )
                panel_seed["bracer_panel_height_mm"] = st.session_state[height_key]
                panel_bounds, _ = resolve_bracer_metrics(panel_seed)
            panel_col1, panel_col2, panel_col3 = st.columns(3)
            with panel_col1:
                bracer_metrics["bracer_panel_length_mm"] = st.number_input(
                    "Panel length (mm)",
                    18.0,
                    float(panel_bounds["bracer_panel_usable_length_mm"]),
                    float(panel_bounds["bracer_panel_length_mm"]),
                    1.0,
                    key="armor_bracer_panel_length_mm",
                    help="Wrist-to-forearm span of the raised maker-finished field.",
                )
                bracer_metrics["bracer_panel_height_mm"] = st.number_input(
                    "Panel height (mm)",
                    float(panel_bounds["bracer_panel_min_height_mm"]),
                    float(panel_bounds["bracer_panel_max_height_mm"]),
                    float(panel_bounds["bracer_panel_height_mm"]),
                    0.1,
                    key="armor_bracer_panel_height_mm",
                    help=(
                        "Amount of exterior raised stock. Actual sanding or carving limits depend on print "
                        "material and physical testing."
                    ),
                )
            with panel_col2:
                bracer_metrics["bracer_panel_width_mm"] = st.number_input(
                    "Panel width (mm)",
                    float(panel_bounds["bracer_panel_min_width_mm"]),
                    float(panel_bounds["bracer_panel_max_width_mm"]),
                    float(panel_bounds["bracer_panel_width_mm"]),
                    1.0,
                    key="armor_bracer_panel_width_mm",
                    help="Width bounds follow the selected Panel Type while preserving closure clearance.",
                )
                bracer_metrics["bracer_panel_edge_roundness_mm"] = st.number_input(
                    "Panel edge roundness (mm)",
                    0.5,
                    float(max(0.5, min(panel_bounds["bracer_panel_length_mm"], panel_bounds["bracer_panel_width_mm"]) * 0.28)),
                    float(panel_bounds["bracer_panel_edge_roundness_mm"]),
                    0.5,
                    key="armor_bracer_panel_edge_roundness_mm",
                    help="Softens panel corners and transitions where OpenSCAD hull geometry permits.",
                )
            with panel_col3:
                position_limit = max(
                    0.0,
                    (panel_bounds["bracer_panel_usable_length_mm"] - panel_bounds["bracer_panel_length_mm"]) / 2,
                )
                bracer_metrics["bracer_panel_position_mm"] = st.slider(
                    "Panel position toward forearm (mm)",
                    float(-position_limit),
                    float(position_limit),
                    float(panel_bounds["bracer_panel_position_mm"]),
                    1.0,
                    key="armor_bracer_panel_position_mm",
                    help="Negative moves toward the wrist; positive moves toward the forearm while staying within margins.",
                )
            bracer_metrics["bracer_panel_type"] = panel_type

        st.subheader("Binding / Closure")
        bracer_binding_style = st.selectbox(
            "Closure style",
            BRACER_BINDING_STYLES,
            help="Optional paired holes, true loops, strap slots, or buckle-ready strap hardware passages.",
        )
        if bracer_binding_style == "Buckle-Ready Slots":
            buckle_seed = dict(bracer_metrics)
            for metric_name in (
                "bracer_buckle_receiver_gap_mm",
                "bracer_buckle_receiver_projection_mm",
                "bracer_buckle_receiver_ear_thickness_mm",
                "bracer_buckle_pin_diameter_mm",
            ):
                state_key = f"armor_{metric_name}"
                if state_key in st.session_state:
                    buckle_seed[metric_name] = st.session_state[state_key]
            buckle_bounds, _ = resolve_bracer_metrics(buckle_seed)
            buckle_specs = {
                "bracer_buckle_receiver_gap_mm": (8.0, 14.0, "Receiver Gap (mm)", "Clear channel between the two exterior mounting ears."),
                "bracer_buckle_receiver_projection_mm": (5.0, 8.0, "Receiver Projection (mm)", "Outward height of the exterior mounting ears."),
                "bracer_buckle_receiver_ear_thickness_mm": (3.0, 5.0, "Ear Thickness (mm)", "Longitudinal thickness of each mounting ear."),
                "bracer_buckle_pin_diameter_mm": (2.5, 4.0, "Pin Passage Diameter (mm)", "Transverse bar or pin passage through both receiver ears."),
            }
            for metric_name, (minimum, maximum, _label, _help) in buckle_specs.items():
                state_key = f"armor_{metric_name}"
                if state_key in st.session_state:
                    st.session_state[state_key] = float(
                        max(minimum, min(float(st.session_state[state_key]), maximum))
                    )
            buckle_cols = st.columns(4)
            for index, (metric_name, (minimum, maximum, label, help_text)) in enumerate(buckle_specs.items()):
                with buckle_cols[index]:
                    bracer_metrics[metric_name] = st.number_input(
                        label,
                        minimum,
                        maximum,
                        float(buckle_bounds[metric_name]),
                        0.5,
                        key=f"armor_{metric_name}",
                        help=help_text,
                    )

        armor_params, armor_warnings = build_bracer_generation_params(
            armor_type, bracer_style, bracer_metrics, detail_options, bracer_binding_style
        )
        armor_audit = audit_bracer_geometry(
            armor_params["metrics"],
            armor_params["armor_type"],
            armor_params["bracer_style"],
            armor_params["detail_options"],
            armor_params["bracer_binding_style"],
        )
        enabled_details = enabled_bracer_detail_labels(armor_params["detail_options"])
    else:
        pauldron_style = st.selectbox("Pauldron style", PAULDRON_STYLES)
        st.subheader("Pauldron dimensions")
        pauldron_columns = st.columns(3)
        pauldron_specs = {
            "pauldron_width_mm": (70.0, 320.0, DEFAULT_PAULDRON_METRICS["pauldron_width_mm"], 1.0),
            "pauldron_depth_mm": (55.0, 260.0, DEFAULT_PAULDRON_METRICS["pauldron_depth_mm"], 1.0),
            "pauldron_height_mm": (18.0, 130.0, DEFAULT_PAULDRON_METRICS["pauldron_height_mm"], 1.0),
            "plate_count": (2, 8, int(DEFAULT_PAULDRON_METRICS["plate_count"]), 1),
            "plate_overlap_mm": (4.0, 45.0, DEFAULT_PAULDRON_METRICS["plate_overlap_mm"], 1.0),
            "pauldron_thickness_mm": (2.4, 12.0, DEFAULT_PAULDRON_METRICS["pauldron_thickness_mm"], 0.2),
        }
        pauldron_metrics = {}
        for index, (name, spec) in enumerate(pauldron_specs.items()):
            minimum, maximum, default, step = spec
            with pauldron_columns[index % 3]:
                label = name.replace("_mm", "").replace("_", " ").title()
                if name.endswith("_mm"):
                    label += " (mm)"
                pauldron_metrics[name] = st.number_input(
                    label,
                    minimum,
                    maximum,
                    default,
                    step,
                    key=f"armor_{name}",
                )

        st.subheader("Pauldron details")
        default_details = normalize_pauldron_detail_options(pauldron_style)
        detail_cols = st.columns(4)
        detail_options = {}
        labels = {
            "raised_trim": "Raised trim",
            "rivets": "Rivets",
            "spikes": "Spikes",
            "runes": "Runes / motif",
        }
        for column, name in zip(detail_cols, labels):
            with column:
                detail_options[name] = st.checkbox(labels[name], value=default_details[name], key=f"armor_{pauldron_style}_{name}")

        armor_params, armor_warnings = build_pauldron_generation_params(
            armor_type, pauldron_style, pauldron_metrics, detail_options
        )
        armor_audit = audit_pauldron_geometry(
            armor_params["metrics"],
            armor_params["armor_type"],
            armor_params["pauldron_style"],
            armor_params["detail_options"],
        )
        enabled_details = enabled_pauldron_detail_labels(armor_params["detail_options"])

    st.subheader("Geometry audit")
    audit_warning_col, audit_info_col, audit_pass_col = st.columns(3)
    with audit_warning_col:
        st.markdown("**Warnings**")
        warnings = armor_warnings + armor_audit["warnings"]
        if warnings:
            for warning in warnings:
                st.warning(warning)
        else:
            st.success(f"No {armor_type.lower()} geometry warnings.")
    with audit_info_col:
        st.markdown("**Notes**")
        detail_label = "Enabled bracer decoration" if armor_type == "Bracer" else "Enabled pauldron details"
        st.info(detail_label + ": " + (", ".join(enabled_details) if enabled_details else "none") + ".")
        for message in armor_audit["info"]:
            st.info(message)
    with audit_pass_col:
        st.markdown("**Checks passed**")
        for message in armor_audit["passes"]:
            st.success(message)

    scad = generate_armor_scad(**armor_params, debug_geometry=debug_geometry, render_quality="preview")
    download_name = f"{armor_type.lower()}.scad"


def scad_for_render_quality(render_quality: str) -> str:
    if generation_category == "Armor":
        return generate_armor_scad(
            **armor_params,
            debug_geometry=debug_geometry,
            render_quality=render_quality,
        )
    if (
        generation_category == "Scabbard"
        and scabbard_mode == "Experimental STL-derived scabbard"
        and render_quality == "final"
    ):
        return custom_stl_export_scad
    return scad


st.subheader("Generated OpenSCAD")
st.code(scad, language="openscad")
st.download_button(
    "Download .scad", data=scad, file_name=download_name, mime="text/plain"
)

preview_col, stl_col = st.columns(2)
with preview_col:
    if st.button("Generate OpenSCAD Preview", disabled=not can_export):
        result = export_with_openscad(scad_for_render_quality("preview"), openscad_path, "png")
        if result.success and result.path:
            st.success(result.message)
            st.image(str(result.path), caption="OpenSCAD preview")
        else:
            st.error(result.message)
with stl_col:
    if st.button("Generate STL", disabled=not can_export):
        result = export_with_openscad(scad_for_render_quality("final"), openscad_path, "stl")
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

if generation_category == "Armor" and armor_type == "Bracer":
    if st.button("Generate Preview Set", disabled=not can_export):
        preview_set = export_preview_set(scad_for_render_quality("preview_set"), openscad_path)
        if preview_set.success:
            st.success(preview_set.message)
        elif preview_set.successful_paths:
            st.warning(preview_set.message)
        else:
            st.error(preview_set.message)

        successful_paths = preview_set.successful_paths
        if successful_paths:
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, "w") as zip_file:
                for view_name, image_path in successful_paths.items():
                    try:
                        zip_file.write(image_path, arcname=image_path.name)
                    except OSError as exc:
                        st.warning(f"{view_name}: generated image could not be added to ZIP: {exc}")
            st.download_button(
                "Download bracer preview set ZIP",
                data=zip_buffer.getvalue(),
                file_name="bracer_preview_set.zip",
                mime="application/zip",
            )
            cols = st.columns(3)
            for index, (view_name, image_path) in enumerate(successful_paths.items()):
                with cols[index % 3]:
                    st.image(str(image_path), caption=view_name.replace("_", " ").title())

        for view_name, result in preview_set.failures.items():
            st.error(f"{view_name}: {result.message}")

if generation_category == "Scabbard":
    if st.button("Generate Scabbard Preview Set", disabled=not can_export):
        preview_set = export_preview_set(
            scad_for_render_quality("preview_set"),
            openscad_path,
            presets=SCABBARD_CAMERA_PRESETS,
            label="scabbard",
        )
        if preview_set.success:
            st.success(preview_set.message)
        elif preview_set.successful_paths:
            st.warning(preview_set.message)
        else:
            st.error(preview_set.message)
        successful_paths = preview_set.successful_paths
        if successful_paths:
            cols = st.columns(2)
            for index, (view_name, image_path) in enumerate(successful_paths.items()):
                with cols[index % 2]:
                    st.image(str(image_path), caption=view_name.replace("_", " ").title())
        for view_name, result in preview_set.failures.items():
            st.error(f"{view_name}: {result.message}")

with st.expander("Known limitations"):
    st.markdown(
        """
- PNG and STL generation require a local OpenSCAD installation.
- Single command-line previews use OpenSCAD's default camera; Bracer and scabbard preview sets use named camera presets.
- Geometry is simplified, decorative, and not intended for fabrication decisions.
- Debug markers are included in exported geometry only while Debug geometry is enabled.
"""
    )
