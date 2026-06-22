from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _list3(value: Any, default: list[float]) -> list[float]:
    if value is None:
        return default
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("Expected a list with 3 numeric values.")
    return [float(item) for item in value]


def slugify(value: str) -> str:
    cleaned = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
        elif not previous_dash:
            cleaned.append("-")
            previous_dash = True
    return "".join(cleaned).strip("-") or "artwork"


@dataclass(slots=True)
class SourceConfig:
    blend: str | None = None
    model: str | None = None
    object_names: list[str] = field(default_factory=list)

    @property
    def source_path(self) -> str | None:
        return self.blend or self.model


@dataclass(slots=True)
class OutputConfig:
    slug: str | None = None
    filename: str = "model.glb"
    preview: str | None = None


@dataclass(slots=True)
class TransformConfig:
    scale: float = 1.0
    position: list[float] = field(default_factory=lambda: [0.0, -0.5, -2.0])
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    center_to_origin: bool = True
    apply_export_transform: bool = False


@dataclass(slots=True)
class OptimizationConfig:
    enabled: bool = True
    texture_size: int = 1024
    texture_compress: str = "webp"
    compress: str = "draco"
    simplify: bool = False
    simplify_ratio: float = 0.75


@dataclass(slots=True)
class ArConfig:
    fallback_mode: str = "viewer_3d"
    min_app_version: str | None = None


@dataclass(slots=True)
class HotspotConfig:
    id: str
    label: str
    query: str
    position: list[float] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HotspotConfig":
        return cls(
            id=str(payload["id"]),
            label=str(payload["label"]),
            query=str(payload["query"]),
            position=_list3(payload.get("position"), [0.0, 0.0, 0.0])
            if payload.get("position") is not None
            else None,
        )

    def to_metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "query": self.query,
        }
        if self.position is not None:
            payload["position"] = self.position
        return payload


@dataclass(slots=True)
class ArtworkManifest:
    artwork_id: str
    title: str
    museum_id: str
    room_id: str | None = None
    culture: str | None = None
    period: str | None = None
    source: SourceConfig = field(default_factory=SourceConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    ar: ArConfig = field(default_factory=ArConfig)
    hotspots: list[HotspotConfig] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.output.slug or slugify(self.artwork_id)

    @property
    def filename(self) -> str:
        return self.output.filename or "model.glb"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ArtworkManifest":
        source = payload.get("source") or {}
        output = payload.get("output") or {}
        transform = payload.get("transform") or {}
        optimization = payload.get("optimization") or {}
        ar = payload.get("ar") or {}

        return cls(
            artwork_id=str(payload["artwork_id"]),
            title=str(payload["title"]),
            museum_id=str(payload["museum_id"]),
            room_id=payload.get("room_id"),
            culture=payload.get("culture"),
            period=payload.get("period"),
            source=SourceConfig(
                blend=source.get("blend"),
                model=source.get("model"),
                object_names=[str(item) for item in source.get("object_names", [])],
            ),
            output=OutputConfig(
                slug=output.get("slug"),
                filename=output.get("filename", "model.glb"),
                preview=output.get("preview"),
            ),
            transform=TransformConfig(
                scale=float(transform.get("scale", 1.0)),
                position=_list3(transform.get("position"), [0.0, -0.5, -2.0]),
                rotation=_list3(transform.get("rotation"), [0.0, 0.0, 0.0]),
                center_to_origin=bool(transform.get("center_to_origin", True)),
                apply_export_transform=bool(transform.get("apply_export_transform", False)),
            ),
            optimization=OptimizationConfig(
                enabled=bool(optimization.get("enabled", True)),
                texture_size=int(optimization.get("texture_size", 1024)),
                texture_compress=str(optimization.get("texture_compress", "webp")),
                compress=str(optimization.get("compress", "draco")),
                simplify=bool(optimization.get("simplify", False)),
                simplify_ratio=float(optimization.get("simplify_ratio", 0.75)),
            ),
            ar=ArConfig(
                fallback_mode=str(ar.get("fallback_mode", "viewer_3d")),
                min_app_version=ar.get("min_app_version"),
            ),
            hotspots=[
                HotspotConfig.from_dict(item)
                for item in payload.get("hotspots", [])
            ],
        )

    def source_abs_path(self, root: Path) -> Path:
        source_path = self.source.source_path
        if not source_path:
            raise ValueError("Manifest must define source.blend or source.model.")
        path = Path(source_path)
        return path if path.is_absolute() else (root / path).resolve()

    def model_url(self) -> str:
        return f"/media/ar/{self.museum_id}/{self.slug}/{self.filename}"

    def to_metadata(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artwork_id": self.artwork_id,
            "title": self.title,
            "museum_id": self.museum_id,
            "room_id": self.room_id,
            "culture": self.culture,
            "period": self.period,
            "model_3d": {
                "url": self.model_url(),
                "format": "GLB",
                "scale": self.transform.scale,
                "position": self.transform.position,
                "rotation": self.transform.rotation,
                "fallback_mode": self.ar.fallback_mode,
            },
            "hotspots": [hotspot.to_metadata() for hotspot in self.hotspots],
        }
        if self.output.preview:
            payload["model_3d"]["preview"] = (
                f"/media/ar/{self.museum_id}/{self.slug}/{self.output.preview}"
            )
        if self.ar.min_app_version:
            payload["model_3d"]["min_app_version"] = self.ar.min_app_version
        return {key: value for key, value in payload.items() if value is not None}
