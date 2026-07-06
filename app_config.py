"""Local, best-effort persistence for Digital Forge UI settings."""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name(".digital_forge_config.json")


def load_config(path: Path = CONFIG_PATH) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_openscad_path(value: str, path: Path = CONFIG_PATH) -> None:
    config = load_config(path)
    config["openscad_path"] = str(value).strip()
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
