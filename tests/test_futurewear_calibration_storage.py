import json
from pathlib import Path
from uuid import uuid4

from futurewear.calibration import AssemblyResult, ClearanceSampleResult, DamageResult, RetentionResult
from futurewear.calibration import build_calibration_profile
from futurewear.calibration_storage import (
    archive_profile,
    empty_store,
    list_profiles,
    load_calibration_store,
    rename_profile,
    save_calibration_store,
    upsert_profile,
)


def viable_sample(clearance=0.32, cycles=20):
    return ClearanceSampleResult(
        clearance_mm=clearance,
        assembly_result=AssemblyResult.FIRM_FUNCTIONAL.value,
        sliding_result="Controlled",
        retention_result=RetentionResult.FUNCTIONAL.value,
        damage_result=DamageResult.NONE.value,
        cycle_count=cycles,
        notes="",
    )


def test_empty_store_is_deterministic():
    assert empty_store() == {"schema_version": 1, "profiles": []}


def _test_path(name: str) -> Path:
    directory = Path("generated/test_futurewear_calibration_storage")
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}_{uuid4().hex}.json"


def test_missing_and_malformed_storage_recover_safely():
    path = _test_path("malformed")
    data, warnings = load_calibration_store(path)
    assert data == empty_store()
    assert warnings == []

    path.write_text("{bad json", encoding="utf-8")
    data, warnings = load_calibration_store(path)
    assert data == empty_store()
    assert warnings

    path.write_text(json.dumps({"schema_version": 1, "profiles": "bad"}), encoding="utf-8")
    data, warnings = load_calibration_store(path)
    assert data == empty_store()
    assert warnings


def test_storage_save_load_upsert_rename_and_archive():
    path = _test_path("profiles")
    profile = build_calibration_profile("One", viable_sample())
    save_calibration_store([profile], path)
    profiles, warnings = list_profiles(path)
    assert not warnings
    assert len(profiles) == 1
    assert profiles[0].name == "One"

    updated = profile.__class__(**{**profile.__dict__, "name": "Two"})
    upsert_profile(updated, path)
    profiles, _warnings = list_profiles(path)
    assert len(profiles) == 1
    assert profiles[0].name == "Two"

    renamed, _warnings = rename_profile(profile.profile_id, "Three", path)
    assert renamed
    profiles, _warnings = list_profiles(path)
    assert profiles[0].name == "Three"

    archived, _warnings = archive_profile(profile.profile_id, path)
    assert archived
    profiles, _warnings = list_profiles(path)
    assert profiles == []
    profiles, _warnings = list_profiles(path, include_archived=True)
    assert profiles[0].archived
