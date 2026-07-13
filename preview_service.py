"""Optional, local OpenSCAD command-line preview exports."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Iterator


GENERATED_DIR = Path(__file__).resolve().parent / "generated"
DEFAULT_OPENSCAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ExportResult:
    """Structured export outcome that remains compatible with tuple unpacking."""

    success: bool
    message: str
    path: Path | None = None
    error_code: str | None = None

    def __iter__(self) -> Iterator[object]:
        yield self.success
        yield self.message
        yield self.path


@dataclass(frozen=True)
class PreviewSetResult:
    """Structured outcome for a named multi-image preview export."""

    success: bool
    message: str
    results: dict[str, ExportResult]

    @property
    def successful_paths(self) -> dict[str, Path]:
        return {
            name: result.path
            for name, result in self.results.items()
            if result.success and result.path is not None
        }

    @property
    def failures(self) -> dict[str, ExportResult]:
        return {name: result for name, result in self.results.items() if not result.success}


BRACER_CAMERA_PRESETS = {
    "front_exterior": "0,120,42,68,0,0,520",
    "front_three_quarter": "116,104,58,64,0,-26,560",
    "side_profile": "184,118,36,70,0,-90,540",
    "closure_side": "70,118,12,92,0,148,260",
    "top_oblique": "0,112,190,48,0,0,610",
    "rear_three_quarter": "-106,98,-42,116,0,148,580",
}


def build_openscad_command(
    executable: str,
    output_path: Path,
    scad_path: Path,
    camera: str | None = None,
) -> list[str]:
    """Build a shell-free command that safely supports paths containing spaces."""
    command = [executable or "openscad", "-o", str(output_path)]
    if camera:
        command.extend(["--camera", camera])
    command.append(str(scad_path))
    return command


def _error(message: str, code: str) -> ExportResult:
    return ExportResult(False, message, None, code)


def _validate_export_inputs(scad: str, executable: str, timeout: int) -> ExportResult | None:
    if not isinstance(scad, str) or not scad.strip():
        return _error("OpenSCAD input is empty or invalid.", "invalid_scad")
    if not isinstance(timeout, int) or timeout <= 0:
        return _error("OpenSCAD timeout must be a positive integer.", "invalid_timeout")

    explicit_path = Path(executable).expanduser()
    if (
        explicit_path.is_absolute()
        or explicit_path.parent != Path(".")
        or "\\" in executable
        or "/" in executable
    ) and (not explicit_path.exists() or not explicit_path.is_file()):
        return _error(
            "The configured OpenSCAD executable path is invalid.",
            "invalid_executable",
        )
    return None


def _run_openscad_export(
    command: list[str],
    output_path: Path,
    timeout: int,
    view_name: str | None = None,
) -> ExportResult:
    label = f"{view_name}: " if view_name else ""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return _error(
            "OpenSCAD was not found. Configure its executable path in the sidebar.",
            "missing_executable",
        )
    except subprocess.TimeoutExpired:
        return _error(
            f"{label}OpenSCAD export exceeded the {timeout}-second timeout.",
            "timeout",
        )
    except (OSError, PermissionError) as exc:
        return _error(f"OpenSCAD could not be started: {exc}", "launch_error")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No diagnostic output.").strip()
        return _error(f"{label}OpenSCAD export failed: {detail}", "command_failed")
    try:
        if not output_path.exists() or output_path.stat().st_size <= 0:
            return _error("OpenSCAD completed but produced an empty output file.", "empty_output")
    except OSError as exc:
        return _error(f"Could not inspect OpenSCAD output: {exc}", "output_error")

    return ExportResult(True, f"Generated {output_path.name}.", output_path)


def export_with_openscad(
    scad: str,
    executable: str = "openscad",
    output_format: str = "png",
    timeout: int = DEFAULT_OPENSCAD_TIMEOUT_SECONDS,
) -> ExportResult:
    """Write SCAD and export PNG or STL without requiring OpenSCAD at import time."""
    if output_format not in {"png", "stl"}:
        return _error("Output format must be 'png' or 'stl'.", "invalid_format")

    executable = (executable or "openscad").strip()
    input_error = _validate_export_inputs(scad, executable, timeout)
    if input_error:
        return input_error

    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        scad_path = GENERATED_DIR / "preview.scad"
        output_path = GENERATED_DIR / f"preview.{output_format}"
        scad_path.write_text(scad, encoding="utf-8")
        if output_path.exists():
            output_path.unlink()
    except (OSError, PermissionError) as exc:
        return _error(f"Could not write preview files: {exc}", "write_error")

    command = build_openscad_command(executable, output_path, scad_path)
    return _run_openscad_export(command, output_path, timeout)


def export_preview_set(
    scad: str,
    executable: str = "openscad",
    timeout: int = DEFAULT_OPENSCAD_TIMEOUT_SECONDS,
    presets: dict[str, str] | None = None,
) -> PreviewSetResult:
    """Export deterministic named PNG views while preserving partial successes."""
    executable = (executable or "openscad").strip()
    input_error = _validate_export_inputs(scad, executable, timeout)
    camera_presets = presets or BRACER_CAMERA_PRESETS
    if input_error:
        results = {name: input_error for name in camera_presets}
        return PreviewSetResult(False, input_error.message, results)

    try:
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        scad_path = GENERATED_DIR / "bracer_preview_set.scad"
        scad_path.write_text(scad, encoding="utf-8")
    except (OSError, PermissionError) as exc:
        error = _error(f"Could not write preview files: {exc}", "write_error")
        return PreviewSetResult(False, error.message, {name: error for name in camera_presets})

    results: dict[str, ExportResult] = {}
    for name, camera in camera_presets.items():
        output_path = GENERATED_DIR / f"bracer_{name}.png"
        try:
            if output_path.exists():
                output_path.unlink()
        except (OSError, PermissionError) as exc:
            results[name] = _error(f"Could not prepare {output_path.name}: {exc}", "write_error")
            continue
        command = build_openscad_command(executable, output_path, scad_path, camera)
        results[name] = _run_openscad_export(command, output_path, timeout, name)

    successful = sum(1 for result in results.values() if result.success)
    failed = len(results) - successful
    success = successful > 0 and failed == 0
    if failed:
        message = f"Generated {successful} of {len(results)} bracer preview views; {failed} failed."
    else:
        message = f"Generated {successful} bracer preview views."
    return PreviewSetResult(success, message, results)
