"""Small numeric helpers local to Futurewear."""

from math import isfinite


def finite_float(value: object, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if isfinite(number) else fallback


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def normalize_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = vector
    magnitude = (x * x + y * y + z * z) ** 0.5
    if magnitude <= 0:
        return (0.0, 0.0, 0.0)
    return (x / magnitude, y / magnitude, z / magnitude)
