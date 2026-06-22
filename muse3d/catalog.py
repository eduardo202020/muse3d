from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import write_json


def collect_dist_catalog(dist_ar_dir: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if not dist_ar_dir.exists():
        return {"total": 0, "items": []}

    for metadata_path in sorted(dist_ar_dir.glob("*/*/metadata.json")):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        items.append(payload)

    return {"total": len(items), "items": items}


def write_catalog(dist_ar_dir: Path, catalog_path: Path) -> dict[str, Any]:
    catalog = collect_dist_catalog(dist_ar_dir)
    write_json(catalog_path, catalog)
    return catalog
