"""Streamlit controls for the isolated Futurewear connector test mode."""

from dataclasses import dataclass
import json

import streamlit as st

from .audit import audit_connector
from .calibration import (
    AssemblyResult,
    CaliperMeasurements,
    ClearanceSampleResult,
    ConnectorCalibrationProfile,
    DamageResult,
    NullTileVerification,
    RetentionResult,
    SlidingResult,
    build_calibration_profile,
    compare_caliper_measurements,
    evaluate_wristwear_readiness,
    profile_to_json_dict,
    select_best_sample,
)
from .calibration_storage import archive_profile, list_profiles, rename_profile, upsert_profile
from .connector_coupons import (
    COUPON_TYPES,
    build_dock_ladder_samples,
    coupon_identifier,
    dock_ladder_color_legend,
    dock_ladder_sample_table,
    generate_connector_test_coupon_scad,
)
from .connectors import (
    CUSTOMER_CONNECTOR_NAMES,
    ConnectorGender,
    ConnectorSize,
    ConnectorType,
    FitPreset,
    normalize_connector_parameters,
    summarize_effective_fit,
)
from .materials import MATERIAL_PROFILES, PrintProfile
from .preview_presets import CONNECTOR_CAMERA_PRESETS


@dataclass(frozen=True)
class FuturewearRenderResult:
    scad: str
    download_name: str
    can_export: bool
    audit: dict[str, list[str]]
    preview_presets: dict[str, str]
    coupon_identifier: str = ""
    effective_fit: dict[str, float] | None = None
    preview_label: str = "futurewear_connector"
    dock_ladder_samples: tuple[dict[str, object], ...] = ()
    preview_color_legend: tuple[tuple[str, str], ...] = ()


def build_futurewear_connector_result(
    connector_type: ConnectorType | str = ConnectorType.SLIDE_RAIL,
    size: ConnectorSize | str = ConnectorSize.STANDARD,
    material_name: str = "PLA",
    fit_preset: FitPreset | str = FitPreset.STANDARD,
    gender: ConnectorGender | str = ConnectorGender.PAIRED,
    coupon_type: str = "Dock Paired Coupon",
    custom_clearance_mm: float | None = None,
    printer_compensation_mm: float = 0.0,
    elephant_foot_compensation_mm: float = 0.0,
    debug_geometry: bool = False,
    preview_mode: str = "Print Layout",
) -> FuturewearRenderResult:
    print_profile = PrintProfile(
        printer_compensation_mm=printer_compensation_mm,
        elephant_foot_compensation_mm=elephant_foot_compensation_mm,
    )
    params, warnings = normalize_connector_parameters(
        connector_type=connector_type,
        gender=gender,
        size=size,
        fit_preset=fit_preset,
        material=material_name,
        print_profile=print_profile,
        fit_clearance_mm=custom_clearance_mm,
        debug_geometry=debug_geometry,
    )
    scad, coupon_warnings, filename = generate_connector_test_coupon_scad(
        connector_type=params.connector_type,
        size=params.size,
        gender=params.gender,
        coupon_type=coupon_type,
        fit_clearance_mm=params.fit_clearance_mm,
        material_name=material_name,
        printer_compensation_mm=params.printer_compensation_mm,
        debug_geometry=debug_geometry,
        preview_mode=preview_mode,
    )
    audit = audit_connector(params, material_name, print_profile)
    audit["warnings"] = warnings + coupon_warnings + audit["warnings"]
    return FuturewearRenderResult(
        scad,
        filename,
        True,
        audit,
        CONNECTOR_CAMERA_PRESETS,
        coupon_identifier(params, coupon_type, material_name),
        summarize_effective_fit(params),
        dock_ladder_samples=dock_ladder_sample_table(
            params.fit_clearance_mm,
            printer_compensation_mm=params.printer_compensation_mm,
        ) if coupon_type == "Dock Clearance Ladder" else (),
        preview_color_legend=dock_ladder_color_legend() if coupon_type == "Dock Clearance Ladder" else (),
    )


def _sample_from_session(index: int, clearance: float) -> ClearanceSampleResult:
    return ClearanceSampleResult(
        clearance_mm=clearance,
        assembly_result=st.session_state.get(f"fw_assembly_{index}", AssemblyResult.SMOOTH_FUNCTIONAL.value),
        sliding_result=st.session_state.get(f"fw_sliding_{index}", SlidingResult.SMOOTH.value),
        retention_result=st.session_state.get(f"fw_retention_{index}", RetentionResult.FUNCTIONAL.value),
        damage_result=st.session_state.get(f"fw_damage_{index}", DamageResult.NONE.value),
        cycle_count=int(st.session_state.get(f"fw_cycles_{index}", 20)),
        notes=st.session_state.get(f"fw_notes_{index}", ""),
    )


def _render_record_results(params, material_name: str, printer_compensation: float, elephant_foot: float) -> tuple[list[ClearanceSampleResult], NullTileVerification | None]:
    st.markdown("**Record Print Results**")
    ladder_samples = build_dock_ladder_samples(params.fit_clearance_mm, printer_compensation_mm=params.printer_compensation_mm)
    with st.form("futurewear_record_results"):
        printer_name = st.text_input("Printer name", value=st.session_state.get("fw_printer_name", "Unknown Printer"))
        slicer_name = st.text_input("Slicer name", value=st.session_state.get("fw_slicer_name", "Unknown Slicer"))
        print_orientation = st.text_input("Print orientation", value=st.session_state.get("fw_orientation", "Flat on build plate"))
        nozzle = st.number_input("Nozzle diameter (mm)", 0.2, 1.2, 0.4, 0.05)
        layer = st.number_input("Layer height (mm)", 0.08, 0.4, 0.2, 0.02)
        samples: list[ClearanceSampleResult] = []
        st.caption("Record results against the printed A-D identifiers. Clearance remains the stored calibration value.")
        for index, ladder_sample in enumerate(ladder_samples):
            clearance = ladder_sample.clearance_mm
            st.markdown(
                f"Sample {ladder_sample.sample_id}: `{clearance:g} mm per side`, "
                f"`{ladder_sample.effective_total_width_gap_mm:g} mm effective total width gap` "
                f"({ladder_sample.relative_fit_label})"
            )
            cols = st.columns(5)
            with cols[0]:
                assembly = st.selectbox("Assembly", [item.value for item in AssemblyResult], index=3, key=f"fw_assembly_{index}")
            with cols[1]:
                sliding = st.selectbox("Sliding", [item.value for item in SlidingResult], index=3, key=f"fw_sliding_{index}")
            with cols[2]:
                retention = st.selectbox("Retention", [item.value for item in RetentionResult], index=2, key=f"fw_retention_{index}")
            with cols[3]:
                damage = st.selectbox("Damage", [item.value for item in DamageResult], key=f"fw_damage_{index}")
            with cols[4]:
                cycles = st.number_input("Cycles", 0, 500, 20, 1, key=f"fw_cycles_{index}")
            notes = st.text_input("Sample notes", key=f"fw_notes_{index}")
            samples.append(ClearanceSampleResult(clearance, assembly, sliding, retention, damage, int(cycles), notes))
        st.markdown("**Null Tile Verification**")
        ncols = st.columns(5)
        with ncols[0]:
            null_installs = st.checkbox("Installs", key="fw_null_installs")
        with ncols[1]:
            null_stop = st.checkbox("Reaches stop", key="fw_null_stop")
        with ncols[2]:
            null_key = st.checkbox("Key blocks reverse", key="fw_null_key")
        with ncols[3]:
            null_flush = st.checkbox("Flush enough", key="fw_null_flush")
        with ncols[4]:
            null_removes = st.checkbox("Removes cleanly", key="fw_null_removes")
        null_notes = st.text_input("Null Tile notes", key="fw_null_notes")
        submitted = st.form_submit_button("Evaluate recorded results")
    if submitted:
        st.session_state["fw_recorded_samples"] = samples
        st.session_state["fw_printer_name"] = printer_name
        st.session_state["fw_slicer_name"] = slicer_name
        st.session_state["fw_orientation"] = print_orientation
        st.session_state["fw_nozzle"] = nozzle
        st.session_state["fw_layer"] = layer
        st.session_state["fw_null_tile"] = NullTileVerification(null_installs, null_stop, null_key, null_flush, null_removes, null_notes)
    return (
        st.session_state.get("fw_recorded_samples", []),
        st.session_state.get("fw_null_tile"),
    )


def _render_profiles(selected_sample: ClearanceSampleResult | None, material_name: str, printer_compensation: float, elephant_foot: float) -> None:
    st.markdown("**Saved Calibration Profiles**")
    profiles, warnings = list_profiles()
    for warning in warnings:
        st.warning(warning)
    if selected_sample is not None:
        with st.form("futurewear_save_profile"):
            name = st.text_input("Profile name", value="Standard Dock calibration")
            notes = st.text_area("Profile notes", value="")
            save = st.form_submit_button("Save calibration profile")
        if save:
            profile = build_calibration_profile(
                name=name,
                selected_sample=selected_sample,
                material_name=material_name,
                printer_name=st.session_state.get("fw_printer_name", "Unknown Printer"),
                nozzle_diameter_mm=float(st.session_state.get("fw_nozzle", 0.4)),
                layer_height_mm=float(st.session_state.get("fw_layer", 0.2)),
                slicer_name=st.session_state.get("fw_slicer_name", "Unknown Slicer"),
                print_orientation=st.session_state.get("fw_orientation", "Flat on build plate"),
                printer_compensation_mm=printer_compensation,
                elephant_foot_compensation_mm=elephant_foot,
                notes=notes,
            )
            upsert_profile(profile)
            st.success(f"Saved {profile.name}.")
            profiles, _warnings = list_profiles()
    if profiles:
        options = {f"{profile.name} ({profile.material_name}, {profile.selected_clearance_mm:g} mm)": profile for profile in profiles}
        selected_label = st.selectbox("Load profile", tuple(options), key="fw_profile_select")
        selected_profile = options[selected_label]
        st.json(profile_to_json_dict(selected_profile))
        rename_col, archive_col, export_col = st.columns(3)
        with rename_col:
            new_name = st.text_input("Rename selected profile", value=selected_profile.name)
            if st.button("Rename profile"):
                renamed, _warnings = rename_profile(selected_profile.profile_id, new_name)
                st.success("Profile renamed." if renamed else "Profile was not found.")
        with archive_col:
            confirm = st.checkbox("Confirm archive", key="fw_confirm_archive")
            if st.button("Archive profile", disabled=not confirm):
                archived, _warnings = archive_profile(selected_profile.profile_id)
                st.success("Profile archived." if archived else "Profile was not found.")
        with export_col:
            st.download_button(
                "Export profile JSON",
                data=json.dumps(profile_to_json_dict(selected_profile), indent=2, sort_keys=True),
                file_name=f"{selected_profile.profile_id}.json",
                mime="application/json",
            )
    else:
        st.info("No saved calibration profiles yet.")


def render_futurewear_designer(debug_geometry: bool = False) -> FuturewearRenderResult:
    st.subheader("Futurewear")
    product_mode = st.selectbox("Product Mode", ("Connector Test",), key="futurewear_product_mode")
    st.caption("Fashion accessory prototype hardware. Not protective equipment.")

    connector_labels = {
        CUSTOMER_CONNECTOR_NAMES[ConnectorType.SLIDE_RAIL]: ConnectorType.SLIDE_RAIL,
        f"{CUSTOMER_CONNECTOR_NAMES[ConnectorType.TWIST_LOCK]} (Experimental)": ConnectorType.TWIST_LOCK,
        CUSTOMER_CONNECTOR_NAMES[ConnectorType.CORD_LOOP]: ConnectorType.CORD_LOOP,
    }
    col1, col2, col3 = st.columns(3)
    with col1:
        connector_label = st.selectbox("Connector type", tuple(connector_labels), key="futurewear_connector_type")
        connector_type = connector_labels[connector_label]
    with col2:
        size = st.selectbox("Connector size", tuple(size.value for size in ConnectorSize), index=1, key="futurewear_connector_size")
    with col3:
        material_name = st.selectbox("Material", tuple(MATERIAL_PROFILES), key="futurewear_material")

    col4, col5, col6 = st.columns(3)
    with col4:
        fit_preset = st.selectbox("Fit preset", tuple(preset.value for preset in FitPreset), index=1, key="futurewear_fit")
    with col5:
        gender = st.selectbox("Gender / pair", tuple(gender.value for gender in ConnectorGender), index=2, key="futurewear_gender")
    with col6:
        coupon_type = st.selectbox("Coupon type", COUPON_TYPES, key="futurewear_coupon_type")

    preview_mode = "Print Layout"
    if coupon_type == "Dock Clearance Ladder":
        preview_mode = st.selectbox(
            "Dock ladder preview mode",
            ("Print Layout", "Exploded Pair View", "Insertion View", "Assembled Preview"),
            key="futurewear_dock_ladder_preview_mode",
        )

    custom_clearance = None
    printer_compensation = 0.0
    with st.expander("Advanced"):
        if fit_preset == FitPreset.CUSTOM.value:
            custom_clearance = st.number_input("Custom clearance per side (mm)", 0.15, 0.75, 0.32, 0.01)
        printer_compensation = st.number_input("Printer compensation (mm)", -0.5, 0.5, 0.0, 0.01)
        elephant_foot = st.number_input("Elephant-foot compensation (mm)", -0.5, 0.5, 0.0, 0.01)
        local_debug = st.checkbox("Connector debug geometry", value=debug_geometry)
    result = build_futurewear_connector_result(
        connector_type=connector_type,
        size=size,
        material_name=material_name,
        fit_preset=fit_preset,
        gender=gender,
        coupon_type=coupon_type,
        custom_clearance_mm=custom_clearance,
        printer_compensation_mm=printer_compensation,
        elephant_foot_compensation_mm=elephant_foot,
        debug_geometry=local_debug,
        preview_mode=preview_mode,
    )
    params, _warnings = normalize_connector_parameters(
        connector_type=connector_type,
        size=size,
        material=material_name,
        fit_preset=fit_preset,
        fit_clearance_mm=custom_clearance,
        printer_compensation_mm=printer_compensation,
        debug_geometry=local_debug,
    )

    tabs = st.tabs(("Generate Coupon", "Record Print Results", "Saved Calibration Profiles", "Readiness Gate"))
    with tabs[0]:
        st.markdown("**Generated coupon identifier**")
        st.code(result.coupon_identifier)
        if coupon_type == "Dock Clearance Ladder":
            st.info(
                "This ladder contains several male/female Dock pairs. Each pair tests a different clearance. "
                "Match pieces by letter and clearance value, then test from tightest to loosest. "
                "Do not force a sample that binds."
            )
            st.markdown("**Dock ladder samples**")
            st.table(result.dock_ladder_samples)
            st.caption(
                "Insertion direction: the raised arrow points into the receiver toward the positive STOP bar. "
                "Colors are preview-only and STL output may be monochrome, so use the raised identifiers and clearance labels. "
                "Confirm the chosen clearance later with a paired coupon and Null Tile."
            )
            st.markdown("**Preview color legend**")
            st.table(tuple({"Preview color represents": name, "OpenSCAD color": color} for name, color in result.preview_color_legend))
        st.markdown("**Effective fit**")
        st.json(result.effective_fit or {})
        st.caption("Printer compensation shrinks the male and enlarges the receiver; a value applied to both parts changes the total width gap by four times the compensation.")
    with tabs[1]:
        samples, null_tile = _render_record_results(params, material_name, printer_compensation, elephant_foot)
        selection = select_best_sample(samples) if samples else None
        if selection:
            for evaluation in selection.evaluations:
                status = "Candidate" if evaluation.eligible else "Rejected"
                st.write(f"{evaluation.clearance_mm:g} mm: {status}. " + " ".join(evaluation.reasons))
            if selection.selected_sample:
                st.success(f"Recommended clearance: {selection.selected_sample.clearance_mm:g} mm per side.")
        with st.expander("Optional caliper measurements"):
            male_w = st.number_input("Printed male width (mm)", 0.0, 100.0, 0.0, 0.01)
            male_d = st.number_input("Printed male depth (mm)", 0.0, 100.0, 0.0, 0.01)
            receiver_w = st.number_input("Printed receiver opening width (mm)", 0.0, 100.0, 0.0, 0.01)
            receiver_d = st.number_input("Printed receiver depth (mm)", 0.0, 100.0, 0.0, 0.01)
            play = st.number_input("Assembled play (mm)", 0.0, 20.0, 0.0, 0.01)
            measurements = CaliperMeasurements(
                printed_male_width_mm=male_w or None,
                printed_male_depth_mm=male_d or None,
                printed_receiver_opening_width_mm=receiver_w or None,
                printed_receiver_depth_mm=receiver_d or None,
                assembled_play_mm=play or None,
            )
            st.json(compare_caliper_measurements(params, measurements))
    with tabs[2]:
        selected = select_best_sample(st.session_state.get("fw_recorded_samples", [])).selected_sample if st.session_state.get("fw_recorded_samples") else None
        _render_profiles(selected, material_name, printer_compensation, elephant_foot)
    with tabs[3]:
        readiness, gates = evaluate_wristwear_readiness(
            st.session_state.get("fw_recorded_samples", []),
            st.session_state.get("fw_null_tile"),
        )
        for gate in gates:
            st.write(f"{gate.name}: {gate.status.value}")
            for evidence in gate.evidence:
                st.caption(evidence)
            for outstanding in gate.outstanding:
                st.warning(outstanding)
        st.info(f"Readiness: {readiness.value}")

    st.subheader("Connector audit")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Warnings**")
        if result.audit["warnings"]:
            for message in result.audit["warnings"]:
                st.warning(message)
        else:
            st.success("No connector warnings.")
    with c2:
        st.markdown("**Notes**")
        for message in result.audit["info"]:
            st.info(message)
    with c3:
        st.markdown("**Checks passed**")
        for message in result.audit["passes"]:
            st.success(message)
    return result
