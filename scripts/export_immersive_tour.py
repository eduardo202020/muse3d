"""Exporta rutas inmersivas desde Blender a JSON.

Convencion:
- Camaras: Tour_01, Tour_02, Tour_03...
- Targets opcionales: Target_01, Target_02, Target_03...

Ejemplo:
  blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/sala-tour.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TOUR_CAMERA_RE = re.compile(r"^Tour_(\d+)$", re.IGNORECASE)
DEFAULT_DURATION_SECONDS = 6
DEFAULT_LOOK_DISTANCE = 3


def parse_output_path() -> Path:
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = []

    if not args:
        return Path("muse3d/routes/immersive-tour.json")

    return Path(args[0])


def vector_to_dict(vector: Vector) -> dict[str, float]:
    return {
        "x": round(float(vector.x), 5),
        "y": round(float(vector.y), 5),
        "z": round(float(vector.z), 5),
    }


def find_tour_cameras() -> list[tuple[int, bpy.types.Object]]:
    cameras: list[tuple[int, bpy.types.Object]] = []

    for obj in bpy.context.scene.objects:
        match = TOUR_CAMERA_RE.match(obj.name)
        if match and obj.type == "CAMERA":
            cameras.append((int(match.group(1)), obj))

    return sorted(cameras, key=lambda item: item[0])


def resolve_target(index: int, camera: bpy.types.Object) -> Vector:
    target_name = camera.get("target")
    if target_name:
        target = bpy.data.objects.get(str(target_name))
        if target:
            return target.matrix_world.translation.copy()

    target = bpy.data.objects.get(f"Target_{index:02d}") or bpy.data.objects.get(f"Target_{index}")
    if target:
        return target.matrix_world.translation.copy()

    # Blender cameras look along their local -Z axis.
    forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    return camera.matrix_world.translation + forward.normalized() * DEFAULT_LOOK_DISTANCE


def export_tour(output_path: Path) -> None:
    cameras = find_tour_cameras()
    if not cameras:
        raise RuntimeError("No se encontraron camaras Tour_01, Tour_02, etc.")

    points = []
    for index, camera in cameras:
        fov = camera.data.angle * 180 / 3.141592653589793
        duration = float(camera.get("duration", DEFAULT_DURATION_SECONDS))
        points.append(
            {
                "id": str(camera.get("tourPointId", f"tour-{index:02d}")),
                "duration": round(duration, 2),
                "position": vector_to_dict(camera.matrix_world.translation),
                "target": vector_to_dict(resolve_target(index, camera)),
                "fov": round(float(fov), 2),
            }
        )

    first_camera = cameras[0][1]
    payload = {
        "id": str(first_camera.get("tourId", output_path.stem)),
        "model": str(first_camera.get("tourModel", "")) or None,
        "source": bpy.data.filepath,
        "units": "blender",
        "coordinateSystem": "blender-z-up",
        "description": str(first_camera.get("tourDescription", "")) or None,
        "points": points,
    }
    payload = {key: value for key, value in payload.items() if value is not None}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[Muse3D] Ruta exportada: {output_path} ({len(points)} puntos)")


if __name__ == "__main__":
    export_tour(parse_output_path())
