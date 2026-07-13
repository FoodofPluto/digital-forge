"""Optional, local OpenSCAD command-line preview exports."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Iterator


GENERATED_DIR = Path(__file__).resolve().parent / "generated"


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


def build_openscad_command(executable: str, output_path: Path, scad_path: Path) -> list[str]:
    """Build a shell-free command that safely supports paths containing spaces."""
    return [executable or "openscad", "-o", str(output_path), str(scad_path)]


def _error(message: str, code: str) -> ExportResult:
    return ExportResult(False, message, None, code)


def export_with_openscad(
    scad: str,
    executable: str = "openscad",
    output_format: str = "png",
    timeout: int = 180,
) -> ExportResult:
    """Write SCAD and export PNG or STL without requiring OpenSCAD at import time."""
    if output_format not in {"png", "stl"}:
        return _error("Output format must be 'png' or 'stl'.", "invalid_format")
    if not isinstance(scad, str) or not scad.strip():
        return _error("OpenSCAD input is empty or invalid.", "invalid_scad")
    if not isinstance(timeout, int) or timeout <= 0:
        return _error("OpenSCAD timeout must be a positive integer.", "invalid_timeout")

    executable = (executable or "openscad").strip()
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
            f"OpenSCAD export exceeded the {timeout}-second timeout.",
            "timeout",
        )
    except (OSError, PermissionError) as exc:
        return _error(f"OpenSCAD could not be started: {exc}", "launch_error")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No diagnostic output.").strip()
        return _error(f"OpenSCAD export failed: {detail}", "command_failed")
    try:
        if not output_path.exists() or output_path.stat().st_size <= 0:
            return _error("OpenSCAD completed but produced an empty output file.", "empty_output")
    except OSError as exc:
        return _error(f"Could not inspect OpenSCAD output: {exc}", "output_error")

    return ExportResult(True, f"Generated {output_path.name}.", output_path)
