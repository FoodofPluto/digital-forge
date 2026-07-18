"""Digital Forge Futurewear modular accessory system."""

from .constants import MODULAR_STANDARD_VERSION
from .connectors import (
    ConnectorAuditResult,
    ConnectorGender,
    ConnectorMount,
    ConnectorParameters,
    ConnectorSize,
    ConnectorType,
    FitPreset,
    connector_metadata,
    connector_size_preset,
    derive_clearance_envelope,
    derive_male_dimensions,
    derive_receiver_dimensions,
    normalize_connector_parameters,
    summarize_effective_fit,
)
from .calibration import ConnectorCalibrationProfile, ClearanceSampleResult
from .materials import MaterialProfile, PrintProfile

__all__ = [
    "MODULAR_STANDARD_VERSION",
    "ConnectorAuditResult",
    "ConnectorGender",
    "ConnectorMount",
    "ConnectorParameters",
    "ConnectorSize",
    "ConnectorType",
    "FitPreset",
    "MaterialProfile",
    "PrintProfile",
    "connector_metadata",
    "connector_size_preset",
    "derive_clearance_envelope",
    "derive_male_dimensions",
    "derive_receiver_dimensions",
    "normalize_connector_parameters",
    "summarize_effective_fit",
    "ConnectorCalibrationProfile",
    "ClearanceSampleResult",
]
