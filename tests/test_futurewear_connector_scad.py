from futurewear import MODULAR_STANDARD_VERSION
from futurewear.connector_scad import (
    generate_connector_debug_scad,
    generate_connector_pair_scad,
    generate_connector_positive_scad,
    generate_connector_receiver_scad,
    generate_null_tile_scad,
)
from futurewear.connectors import ConnectorType, normalize_connector_parameters


def test_positive_dock_scad_contains_standard_key_retention_and_stop():
    params, _ = normalize_connector_parameters(debug_geometry=True)
    scad = generate_connector_positive_scad(params)
    assert MODULAR_STANDARD_VERSION in scad
    assert "Customer name: Dock" in scad
    assert "module dock_positive()" in scad
    assert "module dock_key_rib" in scad
    assert "module dock_friction_rib" in scad
    assert "stop_thickness_mm = 2.4;" in scad
    assert "df_mod_insertion_arrow();" in scad
    assert scad.strip().endswith("dock_positive();")


def test_receiver_scad_contains_cavity_chamfer_and_positive_stop():
    params, _ = normalize_connector_parameters()
    scad = generate_connector_receiver_scad(params)
    assert "module dock_receiver_cavity()" in scad
    assert "entrance_chamfer_mm" in scad
    assert "color(\"tomato\")" in scad
    assert "dock_receiver_body();" in scad


def test_pair_scad_contains_male_and_receiver_layout():
    params, _ = normalize_connector_parameters()
    scad = generate_connector_pair_scad(params)
    assert "Paired connector fit preview" in scad
    assert "translate([-dock_receiver_width_mm,0,0]) dock_positive();" in scad
    assert "translate([dock_receiver_width_mm,0,0]) dock_receiver_body();" in scad


def test_debug_scad_forces_debug_geometry():
    params, _ = normalize_connector_parameters(debug_geometry=False)
    scad = generate_connector_debug_scad(params)
    assert "df_mod_mounting_plane();" in scad
    assert "df_mod_clearance_envelope();" in scad
    assert "df_mod_insertion_arrow();" in scad


def test_null_tile_is_a_flush_blank_that_uses_dock_positive():
    params, _ = normalize_connector_parameters()
    scad = generate_null_tile_scad(params)
    assert "Null Tile flush blank module" in scad
    assert "module null_tile_face()" in scad
    assert "dock_positive();" in scad
    assert scad.strip().endswith("null_tile();")


def test_cord_loop_and_quarter_turn_scad_are_available():
    cord, _ = normalize_connector_parameters(connector_type=ConnectorType.CORD_LOOP)
    turn, _ = normalize_connector_parameters(connector_type=ConnectorType.TWIST_LOCK)
    assert "module cord_loop_positive()" in generate_connector_positive_scad(cord)
    assert "Customer name: Quarter Turn" in generate_connector_pair_scad(turn)
    assert "module quarter_turn_receiver()" in generate_connector_receiver_scad(turn)
