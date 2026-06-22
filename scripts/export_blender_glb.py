from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_source(source_path: Path) -> None:
    suffix = source_path.suffix.lower()

    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source_path))
        return

    clear_scene()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(source_path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source_path))
    elif suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(source_path))
        else:
            bpy.ops.import_scene.obj(filepath=str(source_path))
    elif suffix == ".stl":
        bpy.ops.import_mesh.stl(filepath=str(source_path))
    else:
        raise ValueError(f"Unsupported source format for Blender import: {suffix}")


def selectable_objects(object_names: list[str]) -> list[bpy.types.Object]:
    if object_names:
        selected = [bpy.data.objects[name] for name in object_names if name in bpy.data.objects]
    else:
        selected = [
            obj
            for obj in bpy.context.scene.objects
            if obj.type in {"MESH", "CURVE", "SURFACE", "EMPTY", "ARMATURE"}
        ]
    if not selected:
        raise RuntimeError("No objects were found for GLB export.")
    return selected


def center_to_origin(objects: list[bpy.types.Object]) -> None:
    mesh_objects = [obj for obj in objects if obj.type == "MESH"]
    if not mesh_objects:
        return

    points: list[Vector] = []
    for obj in mesh_objects:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)

    min_corner = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    max_corner = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    center = (min_corner + max_corner) * 0.5

    root_objects = [obj for obj in objects if obj.parent is None]
    for obj in root_objects:
        obj.location -= center


def apply_export_transform(objects: list[bpy.types.Object], transform: dict) -> None:
    scale = float(transform.get("scale", 1.0))
    position = [float(item) for item in transform.get("position", [0, 0, 0])]
    rotation = [math.radians(float(item)) for item in transform.get("rotation", [0, 0, 0])]

    root_objects = [obj for obj in objects if obj.parent is None]
    for obj in root_objects:
        obj.scale = (obj.scale.x * scale, obj.scale.y * scale, obj.scale.z * scale)
        obj.location.x += position[0]
        obj.location.y += position[1]
        obj.location.z += position[2]
        obj.rotation_euler.x += rotation[0]
        obj.rotation_euler.y += rotation[1]
        obj.rotation_euler.z += rotation[2]


def export_glb(output_path: Path, objects: list[bpy.types.Object], apply_transform: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    export_kwargs = {
        "filepath": str(output_path),
        "export_format": "GLB",
        "use_selection": True,
        "export_apply": apply_transform,
    }
    try:
        bpy.ops.export_scene.gltf(**export_kwargs)
    except TypeError:
        export_kwargs.pop("export_apply", None)
        bpy.ops.export_scene.gltf(**export_kwargs)


def main() -> None:
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    source_path = Path(config["source_path"])
    output_path = Path(config["output_path"])
    transform = config.get("transform", {})

    import_source(source_path)
    objects = selectable_objects(config.get("object_names", []))

    if transform.get("center_to_origin", True):
        center_to_origin(objects)
    if transform.get("apply_export_transform", False):
        apply_export_transform(objects, transform)

    export_glb(output_path, objects, bool(transform.get("apply_export_transform", False)))


if __name__ == "__main__":
    main()
