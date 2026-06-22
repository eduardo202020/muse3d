from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ArtworkManifest


def _parse_scalar(value: str) -> Any:
    cleaned = value.strip()
    if cleaned in {"true", "True"}:
        return True
    if cleaned in {"false", "False"}:
        return False
    if cleaned in {"null", "None", "~"}:
        return None
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item.strip()) for item in inner.split(",")]
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        return cleaned[1:-1]
    try:
        if "." in cleaned:
            return float(cleaned)
        return int(cleaned)
    except ValueError:
        return cleaned


def _strip_inline_comment(line: str) -> str:
    if " #" in line:
        return line.split(" #", 1)[0].rstrip()
    return line.rstrip()


def _read_simple_yaml(text: str) -> dict[str, Any]:
    """Small YAML subset reader for Muse3D manifests.

    This keeps `python -m muse3d build --dry-run` usable before dependencies are
    installed. PyYAML remains the preferred reader when available.
    """

    payload: dict[str, Any] = {}
    section: str | None = None
    current_hotspot: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = _strip_inline_comment(raw_line)
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        if indent == 0:
            key, _, value = content.partition(":")
            key = key.strip()
            if value.strip():
                payload[key] = _parse_scalar(value)
                section = None
            else:
                payload[key] = [] if key == "hotspots" else {}
                section = key
            continue

        if section == "hotspots":
            if indent == 2 and content.startswith("- "):
                current_hotspot = {}
                payload["hotspots"].append(current_hotspot)
                content = content[2:].strip()
                if content:
                    key, _, value = content.partition(":")
                    current_hotspot[key.strip()] = _parse_scalar(value)
            elif indent >= 4 and current_hotspot is not None:
                key, _, value = content.partition(":")
                current_hotspot[key.strip()] = _parse_scalar(value)
            continue

        if section and isinstance(payload.get(section), dict) and indent >= 2:
            key, _, value = content.partition(":")
            payload[section][key.strip()] = _parse_scalar(value)

    return payload


def read_manifest(path: Path) -> ArtworkManifest:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            payload = _read_simple_yaml(path.read_text(encoding="utf-8"))
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise ValueError("Manifest must be .json, .yaml, or .yml")

    if not isinstance(payload, dict):
        raise ValueError("Manifest root must be an object.")
    return ArtworkManifest.from_dict(payload)


def find_manifest(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate.resolve()

    manifest_dir = root / "manifests"
    for suffix in (".yaml", ".yml", ".json"):
        path = manifest_dir / f"{value}{suffix}"
        if path.exists():
            return path.resolve()

    raise FileNotFoundError(
        f"Could not find manifest '{value}' in {manifest_dir}."
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
