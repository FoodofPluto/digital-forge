"""Printable calibration coupons for the Futurewear modular standard."""

from dataclasses import dataclass, replace

from .constants import (
    DEFAULT_CLEARANCE_STEP_MM,
    MAX_CONNECTOR_CLEARANCE_MM,
    MIN_CONNECTOR_CLEARANCE_MM,
    MODULAR_STANDARD_VERSION,
)
from .connectors import (
    ConnectorGender,
    ConnectorParameters,
    ConnectorType,
    derive_male_dimensions,
    derive_receiver_dimensions,
    normalize_connector_parameters,
)
from .connector_scad import _common_modules, _header, connector_assignments, generate_null_tile_scad
from .math_utils import clamp

DEFAULT_FDM_NOZZLE_MM = 0.4
DEFAULT_FDM_LAYER_HEIGHT_MM = 0.20
DOCK_LADDER_LABEL_PLATE_LEN_MM = 8.0
DOCK_LADDER_LABEL_PLATE_DEPTH_MM = 1.2
DOCK_LADDER_LABEL_DEPTH_MM = 0.44
DOCK_LADDER_RECEIVER_TEXT_SIZE_MM = 3.0
DOCK_LADDER_MALE_TEXT_SIZE_MM = 3.6
DOCK_LADDER_BODY_ID_TEXT_SIZE_MM = 3.2
DOCK_LADDER_STOP_BAR_THICKNESS_MM = 0.8


COUPON_TYPES = (
    "Dock Paired Coupon",
    "Dock Clearance Ladder",
    "Cord Opening Ladder",
    "Quarter Turn Coupon",
    "Null Tile",
)


@dataclass(frozen=True)
class DockLadderSample:
    sample_id: str
    clearance_mm: float
    effective_total_width_gap_mm: float
    order_index: int
    relative_fit_label: str

    @property
    def printed_identifier(self) -> str:
        return f"{self.sample_id} {self.clearance_mm:.2f}"


@dataclass(frozen=True)
class DockLadderPartPlacement:
    sample_id: str
    role: str
    center_x_mm: float
    center_y_mm: float
    min_x_mm: float
    max_x_mm: float
    min_y_mm: float
    max_y_mm: float
    min_z_mm: float
    max_z_mm: float


@dataclass(frozen=True)
class DockLadderPrintProfile:
    nozzle_diameter_mm: float = DEFAULT_FDM_NOZZLE_MM
    layer_height_mm: float = DEFAULT_FDM_LAYER_HEIGHT_MM
    material_name: str = "PLA"


@dataclass(frozen=True)
class DockLadderPrintabilityAudit:
    passed: bool
    rules: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: dict[str, float]


def _sample_id(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index < len(alphabet):
        return alphabet[index]
    return f"{index + 1:02d}"


def _fit_label(index: int, count: int, clearance: float, base_clearance_mm: float) -> str:
    if index == 0:
        return "Tightest sample"
    if index == count - 1:
        return "Loosest sample"
    if abs(clearance - base_clearance_mm) < 0.0005:
        return "Selected clearance"
    if clearance < base_clearance_mm:
        return "Below selected clearance"
    return "Above selected clearance"


def build_dock_ladder_samples(
    base_clearance_mm: float,
    step_mm: float = DEFAULT_CLEARANCE_STEP_MM,
    sample_count: int = 4,
    printer_compensation_mm: float = 0.0,
) -> tuple[DockLadderSample, ...]:
    """Return ordered Dock clearance samples without depending on SCAD generation."""
    count = max(1, int(sample_count))
    step = max(0.01, float(step_mm))
    base = clamp(float(base_clearance_mm), MIN_CONNECTOR_CLEARANCE_MM, MAX_CONNECTOR_CLEARANCE_MM)
    max_start = MAX_CONNECTOR_CLEARANCE_MM - step * (count - 1)
    start = clamp(base - step, MIN_CONNECTOR_CLEARANCE_MM, max(MIN_CONNECTOR_CLEARANCE_MM, max_start))
    clearances = tuple(round(clamp(start + index * step, MIN_CONNECTOR_CLEARANCE_MM, MAX_CONNECTOR_CLEARANCE_MM), 6) for index in range(count))
    return tuple(
        DockLadderSample(
            sample_id=_sample_id(index),
            clearance_mm=clearance,
            effective_total_width_gap_mm=round(clearance * 2 + float(printer_compensation_mm) * 4, 6),
            order_index=index,
            relative_fit_label=_fit_label(index, count, clearance, base),
        )
        for index, clearance in enumerate(sorted(clearances))
    )


def dock_ladder_sample_table(
    base_clearance_mm: float,
    step_mm: float = DEFAULT_CLEARANCE_STEP_MM,
    sample_count: int = 4,
    printer_compensation_mm: float = 0.0,
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "Sample": sample.sample_id,
            "Clearance per side": f"{sample.clearance_mm:.2f} mm",
            "Effective total width gap": f"{sample.effective_total_width_gap_mm:.2f} mm",
            "Expected relative fit": sample.relative_fit_label,
            "Printed identifier": sample.printed_identifier,
        }
        for sample in build_dock_ladder_samples(base_clearance_mm, step_mm, sample_count, printer_compensation_mm)
    )


def dock_ladder_color_legend() -> tuple[tuple[str, str], ...]:
    return (
        ("male Dock piece", "gainsboro / silver"),
        ("receiver body", "dimgray"),
        ("clearance envelope or receiver cavity", "yellow translucent / dark cutaway"),
        ("positive stop", "tomato"),
        ("insertion/debug guide", "lime"),
    )


def dock_ladder_printable_feature_rules(profile: DockLadderPrintProfile = DockLadderPrintProfile()) -> dict[str, float]:
    nozzle = max(0.1, float(profile.nozzle_diameter_mm))
    layer = max(0.05, float(profile.layer_height_mm))
    return {
        "minimum_planar_feature_mm": round(nozzle * 2.0, 6),
        "minimum_text_size_mm": round(nozzle * 7.0, 6),
        "minimum_raised_height_mm": round(layer * 2.0, 6),
        "minimum_tab_thickness_mm": round(layer * 4.0, 6),
        "minimum_label_edge_margin_mm": round(nozzle * 2.0, 6),
    }


def dock_ladder_feature_dimensions(params: ConnectorParameters) -> dict[str, float]:
    samples = build_dock_ladder_samples(params.fit_clearance_mm, printer_compensation_mm=params.printer_compensation_mm)
    receiver = derive_receiver_dimensions(replace(params, fit_clearance_mm=samples[-1].clearance_mm))
    body_width = receiver.width_mm + params.minimum_surrounding_wall_mm * 2
    male_width = derive_male_dimensions(params).width_mm + params.minimum_surrounding_wall_mm
    full_label = max(samples, key=lambda sample: len(sample.printed_identifier)).printed_identifier
    # Approximate bold sans text extents conservatively for printability checks.
    receiver_label_width = len(full_label) * DOCK_LADDER_RECEIVER_TEXT_SIZE_MM * 0.62
    receiver_label_height = DOCK_LADDER_RECEIVER_TEXT_SIZE_MM
    male_label_width = DOCK_LADDER_MALE_TEXT_SIZE_MM * 0.75
    arrow_width = min(3.2, body_width * 0.18)
    return {
        "receiver_label_tab_width_mm": round(body_width, 6),
        "receiver_label_tab_length_mm": DOCK_LADDER_LABEL_PLATE_LEN_MM,
        "receiver_label_width_mm": round(receiver_label_width, 6),
        "receiver_label_height_mm": round(receiver_label_height, 6),
        "receiver_label_edge_margin_x_mm": round((body_width - receiver_label_width) / 2, 6),
        "receiver_label_edge_margin_y_mm": round((DOCK_LADDER_LABEL_PLATE_LEN_MM - receiver_label_height) / 2, 6),
        "male_label_tab_width_mm": round(male_width, 6),
        "male_label_tab_length_mm": DOCK_LADDER_LABEL_PLATE_LEN_MM,
        "male_label_width_mm": round(male_label_width, 6),
        "male_label_edge_margin_x_mm": round((male_width - male_label_width) / 2, 6),
        "label_tab_thickness_mm": DOCK_LADDER_LABEL_PLATE_DEPTH_MM,
        "text_extrusion_height_mm": DOCK_LADDER_LABEL_DEPTH_MM,
        "receiver_text_size_mm": DOCK_LADDER_RECEIVER_TEXT_SIZE_MM,
        "male_text_size_mm": DOCK_LADDER_MALE_TEXT_SIZE_MM,
        "arrow_shaft_width_mm": round(arrow_width * 0.45, 6),
        "arrowhead_width_mm": round(arrow_width * 2.0, 6),
        "stop_bar_thickness_mm": DOCK_LADDER_STOP_BAR_THICKNESS_MM,
        "stop_bar_width_mm": round(body_width * 0.55, 6),
    }


def dock_ladder_print_layout_footprint(params: ConnectorParameters) -> dict[str, float]:
    placements = build_dock_ladder_layout(params)
    min_x = min(placement.min_x_mm for placement in placements)
    max_x = max(placement.max_x_mm for placement in placements)
    min_y = min(placement.min_y_mm for placement in placements)
    max_y = max(placement.max_y_mm for placement in placements)
    return {
        "min_x_mm": round(min_x, 6),
        "max_x_mm": round(max_x, 6),
        "min_y_mm": round(min_y, 6),
        "max_y_mm": round(max_y, 6),
        "width_mm": round(max_x - min_x, 6),
        "depth_mm": round(max_y - min_y, 6),
    }


def audit_dock_ladder_printability(
    params: ConnectorParameters,
    profile: DockLadderPrintProfile = DockLadderPrintProfile(),
    max_footprint_area_mm2: float = 9000.0,
) -> DockLadderPrintabilityAudit:
    rules = dock_ladder_printable_feature_rules(profile)
    metrics = dock_ladder_feature_dimensions(params) | dock_ladder_print_layout_footprint(params)
    warnings: list[str] = []
    if metrics["receiver_text_size_mm"] < rules["minimum_text_size_mm"]:
        warnings.append("Receiver clearance text is below the nozzle-relative minimum text size.")
    if metrics["male_text_size_mm"] < rules["minimum_text_size_mm"]:
        warnings.append("Male identifier text is below the nozzle-relative minimum text size.")
    if metrics["text_extrusion_height_mm"] < rules["minimum_raised_height_mm"]:
        warnings.append("Raised text extrusion is below two layer heights.")
    if metrics["label_tab_thickness_mm"] < rules["minimum_tab_thickness_mm"]:
        warnings.append("Label tab is below the minimum four-layer thickness.")
    if metrics["arrow_shaft_width_mm"] < rules["minimum_planar_feature_mm"]:
        warnings.append("Arrow shaft is below two nozzle widths.")
    if metrics["stop_bar_thickness_mm"] < rules["minimum_planar_feature_mm"]:
        warnings.append("STOP marker is below two nozzle widths.")
    if metrics["receiver_label_edge_margin_x_mm"] < rules["minimum_label_edge_margin_mm"]:
        warnings.append("Receiver text is too close to the tab side edge.")
    if metrics["receiver_label_edge_margin_y_mm"] < rules["minimum_label_edge_margin_mm"]:
        warnings.append("Receiver text is too close to the tab front/back edge.")
    if metrics["male_label_edge_margin_x_mm"] < rules["minimum_label_edge_margin_mm"]:
        warnings.append("Male text is too close to the tab side edge.")
    if metrics["width_mm"] * metrics["depth_mm"] > max_footprint_area_mm2:
        warnings.append("Print layout footprint is larger than the calibration coupon limit.")
    return DockLadderPrintabilityAudit(
        passed=not warnings,
        rules=tuple(f"{name}={value:g} mm" for name, value in rules.items()),
        warnings=tuple(warnings),
        metrics=metrics,
    )


def build_dock_ladder_layout(
    params: ConnectorParameters,
    step_mm: float = DEFAULT_CLEARANCE_STEP_MM,
    sample_count: int = 4,
) -> tuple[DockLadderPartPlacement, ...]:
    samples = build_dock_ladder_samples(params.fit_clearance_mm, step_mm, sample_count, params.printer_compensation_mm)
    placements: list[DockLadderPartPlacement] = []
    row_gap = max(6.0, params.minimum_surrounding_wall_mm * 2.5)
    pair_gap = max(5.0, params.minimum_surrounding_wall_mm * 2.0)
    label_len = max(DOCK_LADDER_LABEL_PLATE_LEN_MM, params.minimum_surrounding_wall_mm * 3.2)
    dimensions: list[tuple[DockLadderSample, float, float, float, float, float, float]] = []
    for sample in samples:
        variant = replace(params, fit_clearance_mm=sample.clearance_mm)
        male = derive_male_dimensions(variant)
        receiver = derive_receiver_dimensions(variant)
        receiver_w = receiver.width_mm + variant.minimum_surrounding_wall_mm * 2
        receiver_l = receiver.engagement_length_mm + variant.stop_thickness_mm + variant.minimum_surrounding_wall_mm * 2 + label_len * 2
        male_w = male.width_mm + variant.minimum_surrounding_wall_mm
        male_l = male.engagement_length_mm + variant.stop_thickness_mm + label_len
        dimensions.append((sample, male_w, male_l, male.depth_mm, receiver_w, receiver_l, receiver.depth_mm + variant.minimum_surrounding_wall_mm))
    row_pitch = max(max(male_l, receiver_l) for _sample, _male_w, male_l, _male_h, _receiver_w, receiver_l, _receiver_h in dimensions) + row_gap
    for sample, male_w, male_l, male_h, receiver_w, receiver_l, receiver_h in dimensions:
        row_y = sample.order_index * row_pitch
        receiver_x = 0.0
        male_x = -(receiver_w / 2 + pair_gap + male_w / 2)
        for role, cx, width, length, height in (
            ("male", male_x, male_w, male_l, male_h),
            ("receiver", receiver_x, receiver_w, receiver_l, receiver_h),
        ):
            placements.append(
                DockLadderPartPlacement(
                    sample_id=sample.sample_id,
                    role=role,
                    center_x_mm=round(cx, 6),
                    center_y_mm=round(row_y, 6),
                    min_x_mm=round(cx - width / 2, 6),
                    max_x_mm=round(cx + width / 2, 6),
                    min_y_mm=round(row_y - length / 2, 6),
                    max_y_mm=round(row_y + length / 2, 6),
                    min_z_mm=0.0,
                    max_z_mm=round(height, 6),
                )
            )
    return tuple(placements)


def stable_coupon_filename(params: ConnectorParameters, coupon_type: str) -> str:
    slug = coupon_type.lower().replace(" ", "_").replace("-", "_")
    connector = params.connector_type.value.lower().replace(" ", "_")
    size = params.size.value.lower()
    if coupon_type == "Dock Clearance Ladder":
        return (
            f"{MODULAR_STANDARD_VERSION}_{connector}_{size}_{slug}_"
            f"c{params.fit_clearance_mm:g}_s{DEFAULT_CLEARANCE_STEP_MM:g}_n4.scad"
        )
    return f"{MODULAR_STANDARD_VERSION}_{connector}_{size}_{slug}.scad"


def coupon_identifier(params: ConnectorParameters, coupon_type: str, material_name: str = "PLA") -> str:
    slug = coupon_type.lower().replace(" ", "_").replace("-", "_")
    connector = params.connector_type.value.lower().replace(" ", "_")
    size = params.size.value.lower()
    material = material_name.lower().replace(" ", "_")
    base = (
        f"{MODULAR_STANDARD_VERSION}|{connector}|{size}|{material}|"
        f"{slug}|clearance_{params.fit_clearance_mm:g}|printer_comp_{params.printer_compensation_mm:g}"
    )
    if coupon_type == "Dock Clearance Ladder":
        base += f"|step_{DEFAULT_CLEARANCE_STEP_MM:g}|samples_4"
    return base


def generate_dock_paired_coupon_scad(params: ConnectorParameters) -> str:
    return _header(params, "Dock paired calibration coupon") + f"""$fn = 48;
{connector_assignments(params)}
{_common_modules(params)}

module coupon_grip_tab(label_offset=0) {{
    color("gray") translate([0, label_offset, -minimum_surrounding_wall_mm])
        cube([dock_receiver_width_mm + 10, 14, 4], center=true);
}}

module dock_paired_coupon() {{
    translate([-dock_receiver_width_mm, 0, 0]) {{
        dock_positive();
        coupon_grip_tab(-dock_male_engagement_mm/2 - 9);
    }}
    translate([dock_receiver_width_mm, 0, 0]) {{
        dock_receiver_body();
        coupon_grip_tab(-dock_receiver_engagement_mm/2 - 12);
    }}
}}

dock_paired_coupon();
"""


def _scad_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dock_ladder_metadata_comments(params: ConnectorParameters, samples: tuple[DockLadderSample, ...], step_mm: float) -> str:
    sample_text = ", ".join(f"{sample.sample_id}={sample.clearance_mm:.2f}mm" for sample in samples)
    legend_text = "; ".join(f"{name}: {color}" for name, color in dock_ladder_color_legend())
    return f"""// Coupon metadata: {MODULAR_STANDARD_VERSION} Dock {params.size.value}, material profile embedded by generator caller, base_clearance={params.fit_clearance_mm:g}mm, ladder_step={step_mm:g}mm, sample_count={len(samples)}
// Dock ladder samples ordered tightest to loosest: {sample_text}
// Preview color legend: {legend_text}
// Physical labels are raised on non-mating tabs so monochrome STL exports remain identifiable.
// Insertion direction: START arrow points toward the receiver positive stop.
"""


def generate_dock_clearance_ladder_scad(
    params: ConnectorParameters,
    step_mm: float = DEFAULT_CLEARANCE_STEP_MM,
    preview_mode: str = "Print Layout",
    selected_sample_id: str = "A",
) -> str:
    samples = build_dock_ladder_samples(params.fit_clearance_mm, step_mm, 4, params.printer_compensation_mm)
    placements = build_dock_ladder_layout(params, step_mm, len(samples))
    placement_lookup = {(placement.sample_id, placement.role): placement for placement in placements}
    sections = []
    exploded_sections = []
    assembled_sections = []
    insertion_sections = []
    for sample in samples:
        variant = replace(params, fit_clearance_mm=sample.clearance_mm)
        male_place = placement_lookup[(sample.sample_id, "male")]
        receiver_place = placement_lookup[(sample.sample_id, "receiver")]
        receiver = derive_receiver_dimensions(variant)
        label = sample.printed_identifier
        sections.append(
            f"""
// clearance_variant_{sample.order_index}: {sample.clearance_mm:g} mm per side, sample {sample.sample_id}, total_width_gap {sample.effective_total_width_gap_mm:g} mm
translate([{male_place.center_x_mm:g}, {male_place.center_y_mm:g}, 0]) {{
{connector_assignments(variant)}
    dock_ladder_male_coupon({ _scad_string(sample.sample_id) });
}}
translate([{receiver_place.center_x_mm:g}, {receiver_place.center_y_mm:g}, 0]) {{
{connector_assignments(variant)}
    dock_ladder_receiver_coupon({ _scad_string(sample.sample_id) }, { _scad_string(label) });
}}"""
        )
        exploded_sections.append(
            f"""
translate([0, {sample.order_index * (max(male_place.max_y_mm - male_place.min_y_mm, receiver_place.max_y_mm - receiver_place.min_y_mm) + 10):g}, 0]) {{
{connector_assignments(variant)}
    translate([0, -dock_receiver_engagement_mm - label_plate_len_mm - 6, 0])
        dock_ladder_male_coupon({ _scad_string(sample.sample_id) });
    translate([0, 0, 0])
        dock_ladder_receiver_coupon({ _scad_string(sample.sample_id) }, { _scad_string(label) });
}}"""
        )
        assembled_sections.append(
            f"""
translate([0, {sample.order_index * (max(male_place.max_y_mm - male_place.min_y_mm, receiver_place.max_y_mm - receiver_place.min_y_mm) + 10):g}, 0]) {{
{connector_assignments(variant)}
    translate([0, -dock_receiver_engagement_mm*0.52, 0])
        dock_ladder_male_coupon({ _scad_string(sample.sample_id) });
    dock_ladder_receiver_coupon({ _scad_string(sample.sample_id) }, { _scad_string(label) });
}}"""
        )
        if sample.sample_id == selected_sample_id:
            insertion_sections.append(
                f"""
{connector_assignments(variant)}
translate([0, -dock_receiver_engagement_mm - 10, 0])
    dock_ladder_male_coupon({ _scad_string(sample.sample_id) });
translate([0, 0, 0])
    dock_ladder_receiver_coupon({ _scad_string(sample.sample_id) }, { _scad_string(label) });
color("lime") translate([0, {-receiver.engagement_length_mm / 2 - 10:g}, {receiver.depth_mm + variant.minimum_surrounding_wall_mm + 1.4:g}])
    dock_ladder_arrow_3d(18, 2.2, 0.7);
color("tomato") translate([0, {receiver.engagement_length_mm / 2:g}, {receiver.depth_mm + variant.minimum_surrounding_wall_mm + 1:g}])
    cube([dock_receiver_width_mm, 0.8, 0.8], center=true);"""
            )
    selected_call = {
        "print layout": "dock_clearance_ladder_print_layout();",
        "exploded pair view": "dock_clearance_ladder_exploded_pair_view();",
        "insertion view": "dock_clearance_ladder_insertion_view();",
        "assembled preview": "dock_clearance_ladder_assembled_preview();",
    }.get(preview_mode.strip().lower(), "dock_clearance_ladder_print_layout();")
    return _header(params, "Dock clearance ladder coupon") + f"""$fn = 48;
{_dock_ladder_metadata_comments(params, samples, step_mm)}
{connector_assignments(params)}
{_common_modules(params)}

label_depth_mm = {DOCK_LADDER_LABEL_DEPTH_MM:g};
label_size_mm = {DOCK_LADDER_BODY_ID_TEXT_SIZE_MM:g};
label_plate_depth_mm = {DOCK_LADDER_LABEL_PLATE_DEPTH_MM:g};
label_plate_len_mm = max({DOCK_LADDER_LABEL_PLATE_LEN_MM:g}, minimum_surrounding_wall_mm*3.2);

module dock_ladder_text(label, size_mm=label_size_mm) {{
    linear_extrude(height=label_depth_mm)
        text(label, size=size_mm, halign="center", valign="center", font="Liberation Sans:style=Bold");
}}

module dock_ladder_arrow_3d(length_mm=12, width_mm=2.6, height_mm=label_depth_mm) {{
    linear_extrude(height=height_mm)
        union() {{
            translate([0, -length_mm*0.15, 0]) square([width_mm*0.45, length_mm*0.58], center=true);
            translate([0, length_mm*0.28, 0]) polygon(points=[
                [-width_mm, -length_mm*0.18],
                [width_mm, -length_mm*0.18],
                [0, length_mm*0.30]
            ]);
        }}
}}

module dock_ladder_label_plate(width_mm, label, text_size=label_size_mm) {{
    color("gray") cube([width_mm, label_plate_len_mm, label_plate_depth_mm], center=true);
    color("black") translate([0, 0, label_plate_depth_mm/2])
        dock_ladder_text(label, text_size);
}}

module dock_ladder_start_plate(width_mm) {{
    color("gray") cube([width_mm, label_plate_len_mm, label_plate_depth_mm], center=true);
    color("lime") translate([0, -label_plate_len_mm*0.12, label_plate_depth_mm/2])
        dock_ladder_arrow_3d(label_plate_len_mm*0.9, min(3.2, width_mm*0.18), label_depth_mm);
}}

module dock_ladder_stop_plate(width_mm, label) {{
    dock_ladder_label_plate(width_mm, label, {DOCK_LADDER_RECEIVER_TEXT_SIZE_MM:g});
    color("tomato") translate([0, -label_plate_len_mm*0.43, label_plate_depth_mm/2 + label_depth_mm])
        cube([width_mm*0.55, {DOCK_LADDER_STOP_BAR_THICKNESS_MM:g}, 0.55], center=true);
}}

module dock_ladder_male_coupon(sample_label) {{
    union() {{
        translate([0, 0, dock_male_depth_mm/2]) dock_positive();
        translate([0, dock_male_engagement_mm/2 + stop_thickness_mm + label_plate_len_mm/2, label_plate_depth_mm/2])
            dock_ladder_label_plate(dock_male_width_mm + minimum_surrounding_wall_mm, sample_label, {DOCK_LADDER_MALE_TEXT_SIZE_MM:g});
    }}
}}

module dock_ladder_receiver_coupon(sample_label, clearance_label) {{
    body_len = dock_receiver_engagement_mm + stop_thickness_mm + minimum_surrounding_wall_mm*2;
    body_width = dock_receiver_width_mm + minimum_surrounding_wall_mm*2;
    union() {{
        translate([0, 0, dock_receiver_depth_mm/2 + minimum_surrounding_wall_mm]) dock_receiver_body();
        translate([0, -body_len/2 - label_plate_len_mm/2, label_plate_depth_mm/2])
            dock_ladder_start_plate(body_width);
        translate([0, body_len/2 + label_plate_len_mm/2, label_plate_depth_mm/2])
            dock_ladder_stop_plate(body_width, clearance_label);
        color("black") translate([-body_width/2 + minimum_surrounding_wall_mm*0.95, body_len/2 - minimum_surrounding_wall_mm, dock_receiver_depth_mm + minimum_surrounding_wall_mm + label_depth_mm/2])
            dock_ladder_text(sample_label, {DOCK_LADDER_BODY_ID_TEXT_SIZE_MM:g});
    }}
}}

module dock_clearance_ladder_print_layout() {{
{''.join(sections)}
}}

module dock_clearance_ladder_exploded_pair_view() {{
{''.join(exploded_sections)}
}}

module dock_clearance_ladder_insertion_view() {{
{''.join(insertion_sections) or ''.join(exploded_sections[:1])}
}}

module dock_clearance_ladder_assembled_preview() {{
{''.join(assembled_sections)}
}}

module dock_clearance_ladder() {{
    dock_clearance_ladder_print_layout();
}}

{selected_call}
"""


def generate_cord_opening_ladder_scad(params: ConnectorParameters, step_mm: float = 0.8) -> str:
    openings = [
        max(3.0, params.nominal_interface_width_mm - params.minimum_surrounding_wall_mm * 2 - step_mm),
        max(3.0, params.nominal_interface_width_mm - params.minimum_surrounding_wall_mm * 2),
        max(3.0, params.nominal_interface_width_mm - params.minimum_surrounding_wall_mm * 2 + step_mm),
    ]
    spacing = params.nominal_interface_width_mm * 1.8
    pieces = []
    for index, opening in enumerate(openings):
        width = opening + params.minimum_surrounding_wall_mm * 2
        pieces.append(
            f"""
translate([{(index - 1) * spacing:g}, 0, 0]) {{
    // cord_opening_variant_{index}: {opening:g} mm
    difference() {{
        color("gainsboro") cube([{width:g}, engagement_length_mm, {params.nominal_interface_depth_mm + params.minimum_surrounding_wall_mm * 2:g}], center=true);
        cube([{opening:g}, engagement_length_mm + eps, {params.nominal_interface_depth_mm:g}], center=true);
    }}
}}"""
        )
    return _header(params, "Cord opening ladder coupon") + f"""$fn = 48;
{connector_assignments(params)}
{_common_modules(params)}

module cord_opening_ladder() {{
{''.join(pieces)}
}}

cord_opening_ladder();
"""


def generate_quarter_turn_coupon_scad(params: ConnectorParameters) -> str:
    return _header(params, "Experimental Quarter Turn paired coupon") + f"""$fn = 48;
{connector_assignments(params)}
{_common_modules(params)}

module quarter_turn_coupon() {{
    translate([-dock_receiver_width_mm, 0, 0]) quarter_turn_positive();
    translate([dock_receiver_width_mm, 0, 0]) quarter_turn_receiver();
}}

quarter_turn_coupon();
"""


def generate_connector_test_coupon_scad(
    connector_type=ConnectorType.SLIDE_RAIL,
    size="Standard",
    gender=ConnectorGender.PAIRED,
    coupon_type: str = "Dock Paired Coupon",
    fit_clearance_mm: float | None = None,
    material_name: str = "PLA",
    printer_compensation_mm: float = 0.0,
    debug_geometry: bool = False,
    preview_mode: str = "Print Layout",
) -> tuple[str, list[str], str]:
    params, warnings = normalize_connector_parameters(
        connector_type=connector_type,
        gender=gender,
        size=size,
        material=material_name,
        fit_clearance_mm=fit_clearance_mm,
        printer_compensation_mm=printer_compensation_mm,
        debug_geometry=debug_geometry,
    )
    if coupon_type == "Null Tile":
        scad = generate_null_tile_scad(params)
    elif coupon_type == "Dock Clearance Ladder":
        scad = generate_dock_clearance_ladder_scad(params, preview_mode=preview_mode)
    elif coupon_type == "Cord Opening Ladder":
        cord_params = replace(params, connector_type=ConnectorType.CORD_LOOP, gender=ConnectorGender.PAIRED)
        scad = generate_cord_opening_ladder_scad(cord_params)
        params = cord_params
    elif coupon_type == "Quarter Turn Coupon":
        turn_params = replace(params, connector_type=ConnectorType.TWIST_LOCK, gender=ConnectorGender.PAIRED)
        scad = generate_quarter_turn_coupon_scad(turn_params)
        params = turn_params
    else:
        scad = generate_dock_paired_coupon_scad(params)
    return scad, warnings, stable_coupon_filename(params, coupon_type)
