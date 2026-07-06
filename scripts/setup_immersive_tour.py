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
import importlib.util
import json
import math
import re
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


TOUR_COLLECTION_NAME = "Muse3D_Tour"
TOUR_CAMERA_RE = re.compile(r"^Tour_(\d+)$", re.IGNORECASE)
TOUR_OBJECT_RE = re.compile(r"^(Tour|Target|Label)_\d+$", re.IGNORECASE)
TOUR_PATH_NAME = "Muse3D_Tour_Path"
DEFAULT_CAMERA_FOV_DEGREES = 64
DEFAULT_POINT_DURATION_SECONDS = 5.2
DEFAULT_POINT_COUNT = 12
DEFAULT_LOOK_DISTANCE = 3
MAX_ADDED_PAIR_COUNT = 24
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = PROJECT_ROOT / "scripts" / "export_immersive_tour.py"
PREVIEW_SCRIPT = PROJECT_ROOT / "scripts" / "preview_immersive_tour.py"
VIEW_SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "blender_view_setup.py"


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
    parser.add_argument("--command-file", default="")
    parser.add_argument("--status-file", default="")
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


def load_script_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"No se pudo cargar script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_bridge_status(status_path: Path, payload: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def install_command_bridge(command_path: Path, status_path: Path) -> None:
    command_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    last_command_id: str | None = None

    write_bridge_status(
        status_path,
        {
            "id": None,
            "message": "Muse3D bridge listo",
            "status": "ready",
        },
    )

    def poll_commands() -> float:
        nonlocal last_command_id

        try:
            if not command_path.exists():
                return 0.35

            command = json.loads(command_path.read_text(encoding="utf-8"))
            command_id = str(command.get("id", ""))
            if not command_id or command_id == last_command_id:
                return 0.35

            last_command_id = command_id
            action = command.get("action")

            if action == "preview":
                preview_module = load_script_module("muse3d_preview_runtime", PREVIEW_SCRIPT)
                args = argparse.Namespace(
                    fps=int(command.get("fps", 24)),
                    play=bool(command.get("play", True)),
                    start_frame=int(command.get("startFrame", 1)),
                )
                preview_module.animate_preview_camera(args)
                write_bridge_status(
                    status_path,
                    {
                        "id": command_id,
                        "message": "Preview actualizado en Blender",
                        "status": "done",
                    },
                )
                return 0.35

            if action == "export":
                output_raw = str(command.get("output", "")).strip()
                if not output_raw:
                    raise RuntimeError("Comando export sin output")
                output_path = Path(output_raw).expanduser()
                export_module = load_script_module("muse3d_export_runtime", EXPORT_SCRIPT)
                export_module.export_tour(output_path)
                write_bridge_status(
                    status_path,
                    {
                        "id": command_id,
                        "message": f"Ruta exportada: {output_path}",
                        "status": "done",
                    },
                )
                return 0.35

            if action == "add_pairs":
                count = max(1, min(int(command.get("count", 1)), MAX_ADDED_PAIR_COUNT))
                created_names = add_tour_pairs(count)
                write_bridge_status(
                    status_path,
                    {
                        "id": command_id,
                        "message": f"Pares creados: {', '.join(created_names)}",
                        "status": "done",
                    },
                )
                return 0.35

            if action == "refresh_view":
                view_module = load_script_module("muse3d_view_setup_runtime", VIEW_SETUP_SCRIPT)
                view_module.apply_blender_preview_environment(rendered=True)
                write_bridge_status(
                    status_path,
                    {
                        "id": command_id,
                        "message": "Vista actualizada con materiales y cielo HDR",
                        "status": "done",
                    },
                )
                return 0.35

            raise RuntimeError(f"Accion no soportada: {action}")
        except Exception as error:
            write_bridge_status(
                status_path,
                {
                    "id": last_command_id,
                    "message": str(error),
                    "status": "error",
                    "traceback": traceback.format_exc(),
                },
            )
            return 0.35

    bpy.app.timers.register(poll_commands, persistent=True)
    print(f"[Muse3D] Bridge activo: {command_path}")


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

    forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    return camera.matrix_world.translation + forward.normalized() * DEFAULT_LOOK_DISTANCE


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
    try:
        camera.data.lens_unit = "FOV"
    except TypeError:
        pass
    camera.data.angle = math.radians(fov)
    camera.data.clip_start = 0.05
    camera.data.clip_end = 1000
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
    existing = bpy.data.objects.get(TOUR_PATH_NAME)
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

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


def rebuild_tour_path() -> None:
    collection = get_tour_collection()
    create_path_curve(
        [camera.matrix_world.translation.copy() for _, camera in find_tour_cameras()],
        collection,
    )


def get_next_pair_direction(
    cameras: list[tuple[int, bpy.types.Object]],
    last_index: int,
    last_camera: bpy.types.Object,
) -> tuple[Vector, float, float]:
    last_location = last_camera.matrix_world.translation.copy()
    last_target = resolve_target(last_index, last_camera)
    direction = last_target - last_location
    horizontal_direction = Vector((direction.x, direction.y, 0))

    if horizontal_direction.length <= 0.0001:
        forward = last_camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
        horizontal_direction = Vector((forward.x, forward.y, 0))

    if horizontal_direction.length <= 0.0001:
        horizontal_direction = Vector((0, 1, 0))

    horizontal_direction.normalize()

    previous_step = 0.0
    if len(cameras) >= 2:
        previous_location = cameras[-2][1].matrix_world.translation.copy()
        previous_delta = last_location - previous_location
        previous_step = Vector((previous_delta.x, previous_delta.y, 0)).length

    target_distance = max(direction.length, DEFAULT_LOOK_DISTANCE)
    step_distance = previous_step if previous_step > 0.0001 else target_distance * 0.65
    step_distance = min(max(step_distance, 1.2), 4.0)
    target_distance = min(max(target_distance, step_distance * 1.2, 2.0), 7.0)
    return horizontal_direction, step_distance, target_distance


def select_created_objects(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active = objects[0]


def add_tour_pairs(count: int) -> list[str]:
    collection = get_tour_collection()
    cameras = find_tour_cameras()
    created_objects: list[bpy.types.Object] = []
    created_names: list[str] = []

    if cameras:
        last_index, last_camera = cameras[-1]
        last_location = last_camera.matrix_world.translation.copy()
        last_target = resolve_target(last_index, last_camera)
        route_id = str(last_camera.get("tourId", "immersive-tour"))
        route_model = str(last_camera.get("tourModel", ""))
        route_description = str(last_camera.get("tourDescription", ""))
        duration = float(last_camera.get("duration", DEFAULT_POINT_DURATION_SECONDS))
        fov = math.degrees(float(last_camera.data.angle))
    else:
        last_index = 0
        last_location = Vector((0, 0, 1.55))
        last_target = Vector((0, DEFAULT_LOOK_DISTANCE, 1.45))
        route_id = "immersive-tour"
        route_model = ""
        route_description = "Ruta caminable ajustada manualmente."
        duration = DEFAULT_POINT_DURATION_SECONDS
        fov = DEFAULT_CAMERA_FOV_DEGREES

    fov = min(max(fov, 35), 82)

    for offset in range(1, count + 1):
        current_cameras = find_tour_cameras()
        if current_cameras:
            last_index, last_camera = current_cameras[-1]
            last_location = last_camera.matrix_world.translation.copy()
            last_target = resolve_target(last_index, last_camera)
            direction, step_distance, target_distance = get_next_pair_direction(
                current_cameras,
                last_index,
                last_camera,
            )
        else:
            direction = Vector((0, 1, 0))
            step_distance = 1.8
            target_distance = DEFAULT_LOOK_DISTANCE

        next_index = last_index + 1
        next_position = last_location + direction * step_distance
        next_position.z = max(next_position.z, 0.85)
        next_target_position = next_position + direction * target_distance
        next_target_position.z = max(last_target.z, 0.8)
        point_id = f"walk-{next_index:02d}"
        target = create_target(next_index, next_target_position, collection)
        camera = create_camera(
            next_index,
            next_position,
            target,
            collection,
            duration=duration,
            fov=fov,
            point_id=point_id,
            route_description=route_description,
            route_id=route_id,
            route_model=route_model,
        )
        label = create_label(next_index, next_position, point_id, collection)
        created_objects.extend([camera, target, label])
        created_names.append(f"{camera.name}/{target.name}")

    rebuild_tour_path()
    select_created_objects(created_objects)
    if created_objects:
        bpy.context.scene.camera = created_objects[0]

    return created_names


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
    route: list[tuple[str, Vector, Vector, float, float]] = []

    # La ruta inicial debe ser predecible para editar: una linea sobre el eje Y.
    # Si el GLB no cruza el eje X=0, usamos el centro del modelo como fallback.
    x_axis_margin = max(width * 0.18, 0.65)
    x_axis = 0.0 if min_corner.x - x_axis_margin <= 0 <= max_corner.x + x_axis_margin else center.x
    start_y = min_corner.y - depth * 0.18
    end_y = max_corner.y + depth * 0.12
    step = 1 / max(count - 1, 1)
    base_z = max(0.0, min_corner.z)
    eye_z = base_z + max(1.45, height * 0.08)
    target_z = base_z + max(1.35, height * 0.075)

    for item in range(count):
        t = item * step
        next_t = min(1.0, t + step)
        y = start_y + (end_y - start_y) * t
        target_y = start_y + (end_y - start_y) * next_t
        if item == count - 1:
            target_y = y + max(depth * 0.18, 1.0)
        fov = 72.0 if item == 0 else DEFAULT_CAMERA_FOV_DEGREES
        duration = 6.4 if item == 0 else DEFAULT_POINT_DURATION_SECONDS
        position = Vector(
            (
                x_axis,
                y,
                eye_z,
            )
        )
        target = Vector(
            (
                x_axis,
                target_y,
                target_z,
            )
        )
        point_id = f"walk-{item + 1:02d}"
        route.append((point_id, position, target, duration, fov))

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

    view_module = load_script_module("muse3d_view_setup_runtime", VIEW_SETUP_SCRIPT)
    view_module.apply_blender_preview_environment(rendered=True)

    if args.save_blend:
        save_path = Path(args.save_blend).expanduser().resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(save_path))

    if args.command_file and args.status_file:
        install_command_bridge(
            Path(args.command_file).expanduser().resolve(),
            Path(args.status_file).expanduser().resolve(),
        )

    print(f"[Muse3D] Tour base creado con {len(route)} puntos en coleccion {TOUR_COLLECTION_NAME}")
    print(f"[Muse3D] routeId={route_id} routeModel={route_model or '--'}")
    print("[Muse3D] Ajusta Tour_XX y Target_XX visualmente, luego exporta el JSON.")


if __name__ == "__main__":
    setup_tour()
