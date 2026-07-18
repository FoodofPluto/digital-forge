"""Local JSON storage for Futurewear calibration profiles."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .calibration import (
    CALIBRATION_SCHEMA_VERSION,
    ConnectorCalibrationProfile,
    normalize_calibration_profile,
    profile_to_json_dict,
)

CALIBRATION_DIR = Path(__file__).resolve().parent.parent / "generated" / "futurewear"
CALIBRATION_FILE = CALIBRATION_DIR / "connector_calibration_profiles.json"


def empty_store() -> dict[str, object]:
    return {"schema_version": CALIBRATION_SCHEMA_VERSION, "profiles": []}


def load_calibration_store(path: Path = CALIBRATION_FILE) -> tuple[dict[str, object], list[str]]:
    if not path.exists():
        return empty_store(), []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return empty_store(), [f"Calibration storage could not be read; starting empty: {exc}"]
    if not isinstance(data, dict) or not isinstance(data.get("profiles"), list):
        return empty_store(), ["Calibration storage schema was invalid; starting empty."]
    if data.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
        return empty_store(), ["Calibration storage schema version is unsupported; starting empty."]
    return data, []


def list_profiles(path: Path = CALIBRATION_FILE, include_archived: bool = False) -> tuple[list[ConnectorCalibrationProfile], list[str]]:
    data, warnings = load_calibration_store(path)
    profiles = [normalize_calibration_profile(item) for item in data.get("profiles", []) if isinstance(item, dict)]
    if not include_archived:
        profiles = [profile for profile in profiles if not profile.archived]
    return profiles, warnings


def save_calibration_store(profiles: list[ConnectorCalibrationProfile], path: Path = CALIBRATION_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "profiles": [profile_to_json_dict(profile) for profile in profiles],
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def upsert_profile(profile: ConnectorCalibrationProfile, path: Path = CALIBRATION_FILE) -> tuple[ConnectorCalibrationProfile, list[str]]:
    profiles, warnings = list_profiles(path, include_archived=True)
    updated = [existing for existing in profiles if existing.profile_id != profile.profile_id]
    updated.append(profile)
    save_calibration_store(updated, path)
    return profile, warnings


def rename_profile(profile_id: str, new_name: str, path: Path = CALIBRATION_FILE) -> tuple[bool, list[str]]:
    profiles, warnings = list_profiles(path, include_archived=True)
    changed = False
    updated = []
    for profile in profiles:
        if profile.profile_id == profile_id:
            profile = profile.__class__(**{**profile.__dict__, "name": new_name})
            changed = True
        updated.append(profile)
    save_calibration_store(updated, path)
    return changed, warnings


def archive_profile(profile_id: str, path: Path = CALIBRATION_FILE) -> tuple[bool, list[str]]:
    profiles, warnings = list_profiles(path, include_archived=True)
    changed = False
    updated = []
    for profile in profiles:
        if profile.profile_id == profile_id:
            profile = profile.__class__(**{**profile.__dict__, "archived": True})
            changed = True
        updated.append(profile)
    save_calibration_store(updated, path)
    return changed, warnings
