"""Realistic starting dimensions and broad acceptable ranges for sword types."""

REQUIRED_METRICS = (
    "blade_length_mm",
    "blade_base_width_mm",
    "blade_tip_width_mm",
    "blade_thickness_mm",
    "ricasso_length_mm",
    "grip_length_mm",
    "grip_width_mm",
    "guard_width_mm",
    "guard_height_mm",
    "pommel_size_mm",
)


def _metric(default: float, minimum: float, maximum: float) -> dict[str, float]:
    return {"default": default, "min": minimum, "max": maximum}


SWORD_PRESETS = {
    "arming_sword": {
        "blade_length_mm": _metric(760, 650, 850),
        "blade_base_width_mm": _metric(48, 38, 58),
        "blade_tip_width_mm": _metric(5, 1, 15),
        "blade_thickness_mm": _metric(5.0, 3.5, 7.0),
        "ricasso_length_mm": _metric(0, 0, 40),
        "grip_length_mm": _metric(105, 85, 130),
        "grip_width_mm": _metric(28, 22, 35),
        "guard_width_mm": _metric(190, 140, 240),
        "guard_height_mm": _metric(14, 8, 24),
        "pommel_size_mm": _metric(45, 32, 60),
    },
    "longsword": {
        "blade_length_mm": _metric(930, 800, 1100),
        "blade_base_width_mm": _metric(50, 40, 62),
        "blade_tip_width_mm": _metric(5, 1, 14),
        "blade_thickness_mm": _metric(5.5, 4.0, 8.0),
        "ricasso_length_mm": _metric(35, 0, 90),
        "grip_length_mm": _metric(230, 170, 300),
        "grip_width_mm": _metric(29, 23, 36),
        "guard_width_mm": _metric(240, 190, 310),
        "guard_height_mm": _metric(16, 9, 28),
        "pommel_size_mm": _metric(50, 35, 68),
    },
    "greatsword": {
        "blade_length_mm": _metric(1250, 1050, 1600),
        "blade_base_width_mm": _metric(65, 50, 90),
        "blade_tip_width_mm": _metric(8, 2, 22),
        "blade_thickness_mm": _metric(7.0, 5.0, 10.0),
        "ricasso_length_mm": _metric(180, 80, 300),
        "grip_length_mm": _metric(360, 260, 500),
        "grip_width_mm": _metric(34, 27, 44),
        "guard_width_mm": _metric(360, 280, 500),
        "guard_height_mm": _metric(22, 12, 38),
        "pommel_size_mm": _metric(65, 45, 90),
    },
    "dagger": {
        "blade_length_mm": _metric(300, 180, 450),
        "blade_base_width_mm": _metric(35, 22, 50),
        "blade_tip_width_mm": _metric(3, 0.5, 10),
        "blade_thickness_mm": _metric(4.0, 2.5, 6.5),
        "ricasso_length_mm": _metric(0, 0, 25),
        "grip_length_mm": _metric(100, 75, 135),
        "grip_width_mm": _metric(25, 18, 32),
        "guard_width_mm": _metric(120, 70, 180),
        "guard_height_mm": _metric(12, 6, 22),
        "pommel_size_mm": _metric(36, 24, 52),
    },
    "rapier": {
        "blade_length_mm": _metric(1050, 900, 1200),
        "blade_base_width_mm": _metric(25, 16, 35),
        "blade_tip_width_mm": _metric(2, 0.5, 6),
        "blade_thickness_mm": _metric(5.0, 3.0, 7.0),
        "ricasso_length_mm": _metric(70, 30, 140),
        "grip_length_mm": _metric(120, 95, 155),
        "grip_width_mm": _metric(25, 19, 32),
        "guard_width_mm": _metric(230, 160, 320),
        "guard_height_mm": _metric(20, 10, 40),
        "pommel_size_mm": _metric(42, 28, 58),
    },
    "falchion": {
        "blade_length_mm": _metric(700, 550, 850),
        "blade_base_width_mm": _metric(45, 34, 60),
        "blade_tip_width_mm": _metric(30, 15, 50),
        "blade_thickness_mm": _metric(5.5, 3.5, 8.0),
        "ricasso_length_mm": _metric(20, 0, 60),
        "grip_length_mm": _metric(110, 85, 145),
        "grip_width_mm": _metric(29, 22, 37),
        "guard_width_mm": _metric(170, 110, 230),
        "guard_height_mm": _metric(15, 8, 26),
        "pommel_size_mm": _metric(44, 30, 62),
    },
}
