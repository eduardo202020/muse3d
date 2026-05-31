"""Crea una ruta inmersiva base dentro de Blender.

Este script no usa IA ni renderiza video. Importa un GLB opcional, calcula sus
limites y crea camaras `Tour_01...` con targets `Target_01...` para que la ruta
pueda ajustarse manualmente en Blender y exportarse a JSON.

Uso rapido:
  blender --python muse3d/scripts/setup_immersive_tour.py -- models/immersive/sala.glb --points 12

Uso sobre una escena ya abierta:
  blender sala.blend --python muse3d/scripts/setup_immersive_tour.py -- --points 12
"""

from __future__ import annotations

import argparse
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
DEFAULT_POINT_DURATION_SECONDS = 5.2
DEFAULT_POINT_COUNT = 12
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = []

    parser = argparse.ArgumentParser(description="Crear ruta inmersiva editable.")
    parser.add_argument("model", nargs="?", help="GLB de sala/lugar a importar.")
    parser.add_argument("--points", type=int, default=DEFAULT_POINT_COUNT)
    parser.add_argument("--route-id", default="")
    parser.add_argument("--route-model", default="")
    parser.add_argument(
        "--description",
        default="Ruta caminable generada automaticamente para ajuste manual.",
    )
    parser.add_argument("--save-blend", default="")
    parser.add_argument("--keep-scene", action="store_true")
    parser.add_argument("--keep-existing", action="store_true")
    return parser.parse_args(args)


def slug_from_path(path: Path | None) -> str:
    if not path:
        return "immersive"

    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-") or "immersive"


def guess_route_model(model_path: Path | None) -> str:
    if not model_path:
        return ""

    try:
        return model_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return model_path.name


def get_tour_collection() -> bpy.types.Collection:
    collection = bpy.data.collections.get(TOUR_COLLECTION_NAME)
    if collection:
        return collection

    collection = bpy.data.collections.new(TOUR_COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def clear_existing_tour_objects() -> None:
    for obj in list(bpy.context.scene.objects):
        if TOUR_OBJECT_RE.match(obj.name) or obj.name == TOUR_PATH_NAME:
            bpy.data.objects.remove(obj, do_unlink=True)


def import_glb(model_path: Path) -> None:
    if not model_path.exists():
        raise RuntimeError(f"No existe el GLB: {model_path}")

    bpy.ops.import_scene.gltf(filepath=str(model_path))


def is_tour_object(obj: bpy.types.Object) -> bool:
    return any(collection.name == TOUR_COLLECTION_NAME for collection in obj.users_collection)


def get_mesh_objects() -> list[bpy.types.Object]:
    selected_meshes = [
        obj for obj in bpy.context.selected_objects if obj.type == "MESH" and not is_tour_object(obj)
    ]
    if selected_meshes:
        return selected_meshes

    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not is_tour_object(obj)
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
    target.empty_display_size = 0.24
    target.show_name = True
    link_to_tour_collection(target, collection)
    return target


def create_label(
    index: int,
    location: Vector,
    point_id: str,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location + Vector((0, 0, 0.42)))
    label = bpy.context.object
    label.name = f"Label_{index:02d}"
    label.data.body = f"{index:02d}\\n{point_id}"
    label.data.align_x = "CENTER"
    label.data.align_y = "CENTER"
    label.data.size = 0.38
    link_to_tour_collection(label, collection)
    return label


def create_camera(
    index: int,
    location: Vector,
    target: bpy.types.Object,
    collection: bpy.types.Collection,
    *,
    duration: float,
    fov: float,
    point_id: str,
    route_description: str,
    route_id: str,
    route_model: str,
) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.object
    camera.name = f"Tour_{index:02d}"
    camera.data.name = f"Tour_{index:02d}_Camera"
    camera.data.angle = math.radians(fov)
    camera["duration"] = duration
    camera["target"] = target.name
    camera["tourPointId"] = point_id
    camera["tourId"] = route_id
    camera["tourModel"] = route_model
    camera["tourDescription"] = route_description
    camera.show_name = True
    look_at(camera, target.location)
    link_to_tour_collection(camera, collection)
    return camera


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


def build_default_route(
    min_corner: Vector,
    max_corner: Vector,
    point_count: int,
) -> list[tuple[str, Vector, Vector, float, float]]:
    count = max(2, min(point_count, 30))
    center = (min_corner + max_corner) * 0.5
    size = max_corner - min_corner
    width = max(size.x, 1)
    depth = max(size.y, 1)
    height = max(size.z, 1)
    eye_z = min_corner.z + max(1.55, height * 0.18)
    close_eye_z = min_corner.z + max(1.35, height * 0.14)
    target_z = min_corner.z + max(1.35, height * 0.16)
    panoramic_z = eye_z + max(0.7, height * 0.12)
    route: list[tuple[str, Vector, Vector, float, float]] = []

    first_position = Vector((center.x - width * 0.42, center.y - depth * 0.55, panoramic_z))
    first_target = Vector((center.x - width * 0.04, center.y - depth * 0.08, target_z))
    route.append(("walk-01", first_position, first_target, 6.4, 72.0))

    remaining = count - 1
    for item in range(remaining):
        t = item / max(remaining - 1, 1)
        next_t = min(1.0, t + 1 / max(remaining - 1, 1))
        wave = math.sin(t * math.pi * 2.4) * 0.1
        next_wave = math.sin(next_t * math.pi * 2.4) * 0.06
        x_factor = -0.32 + 0.64 * t + wave
        y_factor = -0.36 + 0.78 * t
        next_x_factor = -0.32 + 0.64 * next_t + next_wave
        next_y_factor = -0.36 + 0.78 * next_t
        height_wave = math.sin(t * math.pi * 1.8) * height * 0.025
        position = Vector(
            (
                center.x + width * x_factor,
                center.y + depth * y_factor,
                close_eye_z + height_wave,
            )
        )
        target = Vector(
            (
                center.x + width * next_x_factor,
                center.y + depth * next_y_factor,
                target_z + height * 0.035,
            )
        )
        point_id = f"walk-{item + 2:02d}"
        fov = 68.0 if item == 0 else DEFAULT_CAMERA_FOV_DEGREES
        route.append((point_id, position, target, DEFAULT_POINT_DURATION_SECONDS, fov))

    return route


def setup_tour() -> None:
    args = parse_args()
    model_path = Path(args.model).expanduser().resolve() if args.model else None
    route_slug = slug_from_path(model_path)
    route_id = args.route_id or f"{route_slug}-walking-tour"
    route_model = args.route_model or guess_route_model(model_path)

    if model_path and not args.keep_scene:
        clear_scene()
    if model_path:
        import_glb(model_path)
    if not args.keep_existing:
        clear_existing_tour_objects()

    mesh_objects = get_mesh_objects()
    min_corner, max_corner = calculate_world_bounds(mesh_objects)
    collection = get_tour_collection()
    route = build_default_route(min_corner, max_corner, args.points)

    cameras = []
    camera_locations = []
    for index, (point_id, camera_position, target_position, duration, fov) in enumerate(
        route,
        start=1,
    ):
        target = create_target(index, target_position, collection)
        camera = create_camera(
            index,
            camera_position,
            target,
            collection,
            duration=duration,
            fov=fov,
            point_id=point_id,
            route_description=args.description,
            route_id=route_id,
            route_model=route_model,
        )
        create_label(index, camera_position, point_id, collection)
        cameras.append(camera)
        camera_locations.append(camera_position)

    create_path_curve(camera_locations, collection)
    if cameras:
        bpy.context.scene.camera = cameras[0]

    if args.save_blend:
        save_path = Path(args.save_blend).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(save_path))

    print(f"[Muse3D] Tour base creado con {len(route)} puntos en coleccion {TOUR_COLLECTION_NAME}")
    print(f"[Muse3D] routeId={route_id} routeModel={route_model or '--'}")
    print("[Muse3D] Ajusta Tour_XX y Target_XX visualmente, luego exporta el JSON.")


if __name__ == "__main__":
    setup_tour()
