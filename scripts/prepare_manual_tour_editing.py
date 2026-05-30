"""Reconstruye una ruta JSON como objetos editables en Blender.

Este script toma una ruta exportada (`routes/*.json`) y crea:
- camaras `Tour_01`, `Tour_02`, ...
- targets `Target_01`, `Target_02`, ...
- labels `Label_01`, `Label_02`, ...
- una curva `Muse3D_Tour_Path` que conecta los puntos

Despues puedes mover manualmente cada `Tour_XX` y `Target_XX` en Blender y
exportar de nuevo con `export_immersive_tour.py`.

Ejemplo:
  blender sala.blend --python muse3d/scripts/prepare_manual_tour_editing.py -- muse3d/routes/lugar-walking-tour.json
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


TOUR_COLLECTION_NAME = "Muse3D_Tour"
TOUR_OBJECT_RE = re.compile(r"^(Tour|Target|Label)_\d+$", re.IGNORECASE)
TOUR_PATH_NAME = "Muse3D_Tour_Path"
DEFAULT_CAMERA_FOV_DEGREES = 64
DEFAULT_DURATION_SECONDS = 6


def parse_route_path() -> Path:
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = []

    if not args:
        return Path("muse3d/routes/lugar-walking-tour.json")

    return Path(args[0])


def get_tour_collection() -> bpy.types.Collection:
    collection = bpy.data.collections.get(TOUR_COLLECTION_NAME)
    if collection:
        return collection

    collection = bpy.data.collections.new(TOUR_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_existing_tour_objects() -> None:
    for obj in list(bpy.context.scene.objects):
        if TOUR_OBJECT_RE.match(obj.name) or obj.name == TOUR_PATH_NAME:
            bpy.data.objects.remove(obj, do_unlink=True)


def link_to_tour_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    if obj.name not in collection.objects.keys():
        collection.objects.link(obj)

    for source_collection in list(obj.users_collection):
        if source_collection != collection:
            source_collection.objects.unlink(obj)


def vector_from_dict(data: dict[str, float]) -> Vector:
    return Vector((float(data["x"]), float(data["y"]), float(data["z"])))


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    if direction.length <= 0.0001:
        return

    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_target(index: int, location: Vector, collection: bpy.types.Collection) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="SPHERE", location=location)
    target = bpy.context.object
    target.name = f"Target_{index:02d}"
    target.empty_display_size = 0.28
    target.show_name = True
    link_to_tour_collection(target, collection)
    return target


def create_camera(
    index: int,
    location: Vector,
    target: bpy.types.Object,
    point: dict,
    route: dict,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.object
    camera.name = f"Tour_{index:02d}"
    camera.data.name = f"Tour_{index:02d}_Camera"
    camera.data.angle = math.radians(float(point.get("fov", DEFAULT_CAMERA_FOV_DEGREES)))
    camera["duration"] = float(point.get("duration", DEFAULT_DURATION_SECONDS))
    camera["target"] = target.name
    camera["tourPointId"] = str(point.get("id", f"tour-{index:02d}"))
    camera["tourId"] = str(route.get("id", "immersive-tour"))
    camera["tourModel"] = str(route.get("model", ""))
    camera["tourDescription"] = str(route.get("description", ""))
    look_at(camera, target.location)
    camera.show_name = True
    link_to_tour_collection(camera, collection)
    return camera


def create_label(
    index: int,
    location: Vector,
    point_id: str,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location + Vector((0, 0, 0.45)))
    label = bpy.context.object
    label.name = f"Label_{index:02d}"
    label.data.body = f"{index:02d}\\n{point_id}"
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.size = 0.42
    label.show_name = False
    link_to_tour_collection(label, collection)
    return label


def create_path_curve(points: list[Vector], collection: bpy.types.Collection) -> None:
    if len(points) < 2:
        return

    curve = bpy.data.curves.new(TOUR_PATH_NAME, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = 0.035
    curve.bevel_resolution = 3

    polyline = curve.splines.new(type="POLY")
    polyline.points.add(len(points) - 1)
    for point, location in zip(polyline.points, points):
        point.co = (location.x, location.y, location.z, 1)

    obj = bpy.data.objects.new(TOUR_PATH_NAME, curve)
    collection.objects.link(obj)


def prepare_manual_tour(route_path: Path) -> None:
    route = json.loads(route_path.read_text(encoding="utf-8"))
    points = route.get("points", [])
    if not points:
        raise RuntimeError(f"La ruta no tiene puntos: {route_path}")

    clear_existing_tour_objects()
    collection = get_tour_collection()
    camera_locations: list[Vector] = []
    cameras: list[bpy.types.Object] = []

    for index, point in enumerate(points, start=1):
        position = vector_from_dict(point["position"])
        target_location = vector_from_dict(point["target"])
        target = create_target(index, target_location, collection)
        camera = create_camera(index, position, target, point, route, collection)
        create_label(index, position, str(point.get("id", f"tour-{index:02d}")), collection)
        camera_locations.append(position)
        cameras.append(camera)

    create_path_curve(camera_locations, collection)
    if cameras:
        bpy.context.scene.camera = cameras[0]

    print(f"[Muse3D] Ruta lista para edicion manual: {route_path}")
    print(f"[Muse3D] Ajusta Tour_XX y Target_XX. Luego exporta con export_immersive_tour.py")


if __name__ == "__main__":
    prepare_manual_tour(parse_route_path())
