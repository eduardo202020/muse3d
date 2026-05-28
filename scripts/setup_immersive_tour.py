"""Crea una ruta inmersiva base dentro de Blender.

Este script no renderiza video. Solo coloca camaras `Tour_01...` y targets
`Target_01...` alrededor del modelo para que Muse3D pueda exportarlos a JSON.

Uso desde terminal:
  blender sala.blend --python muse3d/scripts/setup_immersive_tour.py

Uso desde Blender:
  1. Abre el archivo o importa el GLB.
  2. Ejecuta este script desde el panel de scripting.
  3. Ajusta visualmente las camaras y targets si quieres afinar el tour.
  4. Exporta con `export_immersive_tour.py`.
"""

from __future__ import annotations

import math
import re
import sys

import bpy
from mathutils import Vector


TOUR_CAMERA_RE = re.compile(r"^Tour_\d+$", re.IGNORECASE)
TARGET_RE = re.compile(r"^Target_\d+$", re.IGNORECASE)
TOUR_COLLECTION_NAME = "Muse3D_Tour"
DEFAULT_CAMERA_FOV_DEGREES = 64
DEFAULT_POINT_DURATION_SECONDS = 6


def parse_flag(name: str) -> bool:
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = []

    return name in args


def get_tour_collection() -> bpy.types.Collection:
    collection = bpy.data.collections.get(TOUR_COLLECTION_NAME)
    if collection:
        return collection

    collection = bpy.data.collections.new(TOUR_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_existing_tour_objects() -> None:
    for obj in list(bpy.context.scene.objects):
        if TOUR_CAMERA_RE.match(obj.name) or TARGET_RE.match(obj.name):
            bpy.data.objects.remove(obj, do_unlink=True)


def get_mesh_objects() -> list[bpy.types.Object]:
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    if selected_meshes:
        return selected_meshes

    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj.name not in {TOUR_COLLECTION_NAME}
    ]


def calculate_world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    if not objects:
        raise RuntimeError("No hay objetos mesh seleccionados ni en la escena.")

    points: list[Vector] = []
    for obj in objects:
        matrix = obj.matrix_world
        points.extend(matrix @ vertex.co for vertex in obj.data.vertices)

    min_corner = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    max_corner = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    return min_corner, max_corner


def link_to_tour_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    if obj.name not in collection.objects.keys():
        collection.objects.link(obj)

    for source_collection in list(obj.users_collection):
        if source_collection != collection:
            source_collection.objects.unlink(obj)


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    if direction.length <= 0.0001:
        return

    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def create_target(index: int, location: Vector, collection: bpy.types.Collection) -> bpy.types.Object:
    bpy.ops.object.empty_add(type="SPHERE", location=location)
    target = bpy.context.object
    target.name = f"Target_{index:02d}"
    target.empty_display_size = 0.16
    link_to_tour_collection(target, collection)
    return target


def create_camera(
    index: int,
    location: Vector,
    target: bpy.types.Object,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.object
    camera.name = f"Tour_{index:02d}"
    camera.data.name = f"Tour_{index:02d}_Camera"
    camera.data.angle = math.radians(DEFAULT_CAMERA_FOV_DEGREES)
    camera["duration"] = DEFAULT_POINT_DURATION_SECONDS
    camera["target"] = target.name
    look_at(camera, target.location)
    link_to_tour_collection(camera, collection)
    return camera


def build_default_route(min_corner: Vector, max_corner: Vector) -> list[tuple[Vector, Vector]]:
    center = (min_corner + max_corner) * 0.5
    size = max_corner - min_corner
    width = max(size.x, 1)
    depth = max(size.y, 1)
    height = max(size.z, 1)
    visitor_z = min_corner.z + max(height * 0.48, 1.45)
    close_z = min_corner.z + max(height * 0.42, 1.25)
    target_z = min_corner.z + max(height * 0.36, 1.05)

    def pos(x: float, y: float, z: float = visitor_z) -> Vector:
        return Vector((center.x + width * x, center.y + depth * y, z))

    def target(x: float, y: float, z: float = target_z) -> Vector:
        return Vector((center.x + width * x, center.y + depth * y, z))

    return [
        (pos(-0.08, -0.28, visitor_z), target(-0.1, -0.14, target_z)),
        (pos(-0.12, -0.16, visitor_z), target(-0.08, -0.04, target_z)),
        (pos(-0.08, -0.04, close_z), target(0.0, 0.08, target_z + height * 0.06)),
        (pos(0.0, 0.08, close_z), target(0.08, 0.18, target_z)),
        (pos(0.1, 0.18, visitor_z), target(0.12, 0.3, target_z)),
        (pos(0.12, 0.3, visitor_z), target(0.12, 0.42, target_z)),
    ]


def setup_tour() -> None:
    keep_existing = parse_flag("--keep-existing")
    if not keep_existing:
        clear_existing_tour_objects()

    mesh_objects = get_mesh_objects()
    min_corner, max_corner = calculate_world_bounds(mesh_objects)
    collection = get_tour_collection()
    route = build_default_route(min_corner, max_corner)

    cameras = []
    for index, (camera_position, target_position) in enumerate(route, start=1):
        target = create_target(index, target_position, collection)
        camera = create_camera(index, camera_position, target, collection)
        cameras.append(camera)

    if cameras:
        bpy.context.scene.camera = cameras[0]

    print(f"[Muse3D] Tour base creado con {len(route)} puntos en coleccion {TOUR_COLLECTION_NAME}")
    print("[Muse3D] Ajusta Tour_XX y Target_XX visualmente, luego exporta el JSON.")


if __name__ == "__main__":
    setup_tour()
