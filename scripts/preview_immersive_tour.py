"""Crea una previsualizacion animada del tour dentro de Blender.

El script no exporta ni guarda cambios. Solo crea/actualiza una camara temporal
`Muse3D_Preview_Camera` con keyframes que recorren `Tour_01...Tour_N` mirando a
`Target_01...Target_N`. Luego puedes presionar Play en Blender para revisar el
recorrido completo.

Uso:
  blender workspaces/lugar-tour.blend --python scripts/preview_immersive_tour.py -- --play
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIEW_SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "blender_view_setup.py"
TOUR_COLLECTION_NAME = "Muse3D_Tour"
TOUR_CAMERA_RE = re.compile(r"^Tour_(\d+)$", re.IGNORECASE)
TOUR_PATH_NAME = "Muse3D_Tour_Path"
PATH_MATERIAL_NAME = "Muse3D_Tour_Path_Material"
PREVIEW_CAMERA_NAME = "Muse3D_Preview_Camera"
DEFAULT_DURATION_SECONDS = 5.2
DEFAULT_LOOK_DISTANCE = 3
DEFAULT_PREVIEW_FOV_DEGREES = 64
MIN_PREVIEW_FOV_DEGREES = 35
MAX_PREVIEW_FOV_DEGREES = 82


def load_script_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"No se pudo cargar script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = []

    parser = argparse.ArgumentParser(description="Previsualizar tour Muse3D.")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--start-frame", type=int, default=1)
    parser.add_argument("--play", action="store_true")
    return parser.parse_args(args)


def find_tour_cameras() -> list[tuple[int, bpy.types.Object]]:
    cameras: list[tuple[int, bpy.types.Object]] = []
    for obj in bpy.context.scene.objects:
        match = TOUR_CAMERA_RE.match(obj.name)
        if match and obj.type == "CAMERA":
            cameras.append((int(match.group(1)), obj))
    return sorted(cameras, key=lambda item: item[0])


def get_tour_collection() -> bpy.types.Collection:
    return bpy.data.collections.get(TOUR_COLLECTION_NAME) or bpy.context.scene.collection


def get_path_material() -> bpy.types.Material:
    material = bpy.data.materials.get(PATH_MATERIAL_NAME)
    if material:
        return material

    material = bpy.data.materials.new(PATH_MATERIAL_NAME)
    material.diffuse_color = (0.25, 0.85, 1.0, 1.0)
    return material


def rebuild_path_curve(tour_cameras: list[tuple[int, bpy.types.Object]]) -> None:
    if len(tour_cameras) < 2:
        return

    existing = bpy.data.objects.get(TOUR_PATH_NAME)
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    curve = bpy.data.curves.new(TOUR_PATH_NAME, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = 0.035
    curve.bevel_resolution = 3
    curve.materials.append(get_path_material())

    polyline = curve.splines.new(type="POLY")
    polyline.points.add(len(tour_cameras) - 1)
    for point, (_, camera) in zip(polyline.points, tour_cameras):
        location = camera.matrix_world.translation
        point.co = (location.x, location.y, location.z, 1)

    path_object = bpy.data.objects.new(TOUR_PATH_NAME, curve)
    get_tour_collection().objects.link(path_object)


def sync_labels_to_cameras(tour_cameras: list[tuple[int, bpy.types.Object]]) -> None:
    for index, camera in tour_cameras:
        label = bpy.data.objects.get(f"Label_{index:02d}") or bpy.data.objects.get(f"Label_{index}")
        if label:
            label.location = camera.matrix_world.translation + Vector((0, 0, 0.42))


def normalize_camera_fov(camera: bpy.types.Object) -> float:
    fov_degrees = math.degrees(float(camera.data.angle))
    if fov_degrees < MIN_PREVIEW_FOV_DEGREES or fov_degrees > MAX_PREVIEW_FOV_DEGREES:
        fov_degrees = DEFAULT_PREVIEW_FOV_DEGREES
        camera.data.angle = math.radians(fov_degrees)
        camera["fovNormalizedByMuse3D"] = True

    try:
        camera.data.lens_unit = "FOV"
    except TypeError:
        pass

    camera.data.clip_start = min(float(camera.data.clip_start), 0.05)
    camera.data.clip_end = max(float(camera.data.clip_end), 1000)
    return math.radians(fov_degrees)


def normalize_tour_camera_fovs(tour_cameras: list[tuple[int, bpy.types.Object]]) -> None:
    for _, camera in tour_cameras:
        normalize_camera_fov(camera)


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


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    if direction.length <= 0.0001:
        return

    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def get_or_create_preview_camera() -> bpy.types.Object:
    existing = bpy.data.objects.get(PREVIEW_CAMERA_NAME)
    if existing and existing.type == "CAMERA":
        return existing

    camera_data = bpy.data.cameras.new(PREVIEW_CAMERA_NAME)
    camera = bpy.data.objects.new(PREVIEW_CAMERA_NAME, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    return camera


def clear_preview_animation(camera: bpy.types.Object) -> None:
    camera.animation_data_clear()
    camera.data.animation_data_clear()


def set_linear_interpolation(camera: bpy.types.Object) -> None:
    if not camera.animation_data or not camera.animation_data.action:
        return

    fcurves = getattr(camera.animation_data.action, "fcurves", None)
    if not fcurves:
        return

    for fcurve in fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "BEZIER"


def apply_preview_fov(preview_camera: bpy.types.Object, tour_cameras: list[tuple[int, bpy.types.Object]]) -> None:
    if not tour_cameras:
        return

    preview_camera.data.angle = normalize_camera_fov(tour_cameras[0][1])
    try:
        preview_camera.data.lens_unit = "FOV"
    except TypeError:
        pass


def clear_camera_data_animation(camera: bpy.types.Object) -> None:
    animation_data = camera.data.animation_data
    if not animation_data or not animation_data.action:
        return

    fcurves = getattr(animation_data.action, "fcurves", None)
    if not fcurves:
        return

    for fcurve in list(fcurves):
        animation_data.action.fcurves.remove(fcurve)


def set_camera_marker(scene: bpy.types.Scene, camera: bpy.types.Object, frame: int) -> None:
    marker = scene.timeline_markers.get("Muse3D Preview")
    if not marker:
        marker = scene.timeline_markers.new("Muse3D Preview", frame=frame)

    marker.frame = frame
    marker.camera = camera


def animate_preview_camera(args: argparse.Namespace) -> None:
    view_module = load_script_module("muse3d_view_setup_runtime", VIEW_SETUP_SCRIPT)
    view_module.apply_blender_preview_environment(rendered=True)

    tour_cameras = find_tour_cameras()
    if not tour_cameras:
        raise RuntimeError("No se encontraron camaras Tour_01, Tour_02, etc.")

    normalize_tour_camera_fovs(tour_cameras)
    rebuild_path_curve(tour_cameras)
    sync_labels_to_cameras(tour_cameras)

    preview_camera = get_or_create_preview_camera()
    clear_preview_animation(preview_camera)
    clear_camera_data_animation(preview_camera)
    apply_preview_fov(preview_camera, tour_cameras)
    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.frame_start = args.start_frame

    frame = args.start_frame
    for index, source_camera in tour_cameras:
        target = resolve_target(index, source_camera)
        preview_camera.location = source_camera.matrix_world.translation.copy()
        look_at(preview_camera, target)
        preview_camera.keyframe_insert(data_path="location", frame=frame)
        preview_camera.keyframe_insert(data_path="rotation_euler", frame=frame)

        duration = float(source_camera.get("duration", DEFAULT_DURATION_SECONDS))
        frame += max(1, round(duration * args.fps))

    last_index, last_camera = tour_cameras[-1]
    target = resolve_target(last_index, last_camera)
    preview_camera.location = last_camera.matrix_world.translation.copy()
    look_at(preview_camera, target)
    preview_camera.keyframe_insert(data_path="location", frame=frame)
    preview_camera.keyframe_insert(data_path="rotation_euler", frame=frame)

    scene.camera = preview_camera
    scene.frame_end = frame
    scene.frame_set(args.start_frame)
    set_camera_marker(scene, preview_camera, args.start_frame)
    set_linear_interpolation(preview_camera)

    print(
        f"[Muse3D] Preview listo: {PREVIEW_CAMERA_NAME}, "
        f"frames {scene.frame_start}-{scene.frame_end}, fps={scene.render.fps}"
    )
    print("[Muse3D] Presiona Play en Blender para ver el recorrido.")

    if args.play:
        try:
            bpy.ops.screen.animation_play()
        except Exception:
            print("[Muse3D] No se pudo iniciar Play automaticamente; presionalo manualmente.")


if __name__ == "__main__":
    animate_preview_camera(parse_args())
