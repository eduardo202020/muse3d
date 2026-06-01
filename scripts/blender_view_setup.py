"""Configura Blender para revisar tours Muse3D con materiales y cielo HDR."""

from __future__ import annotations

from pathlib import Path

import bpy


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HDR_CANDIDATES = [
    PROJECT_ROOT.parent / "mañana.hdr",
    PROJECT_ROOT / "assets" / "skies" / "mañana.hdr",
    PROJECT_ROOT / "assets" / "skies" / "morning.hdr",
]
PREVIEW_SUN_NAME = "Muse3D_Preview_Sun"
PREVIEW_WORLD_NAME = "Muse3D_Morning_HDR_World"


def resolve_hdr_path(hdr_path: str | Path | None = None) -> Path | None:
    candidates = [Path(hdr_path).expanduser()] if hdr_path else []
    candidates.extend(DEFAULT_HDR_CANDIDATES)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved

    return None


def set_scene_engine(scene: bpy.types.Scene) -> None:
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = engine
            return
        except Exception:
            continue


def set_color_management(scene: bpy.types.Scene) -> None:
    view_settings = scene.view_settings
    try:
        view_settings.view_transform = "Standard"
    except TypeError:
        pass

    try:
        view_settings.look = "None"
    except TypeError:
        pass

    view_settings.exposure = 0
    view_settings.gamma = 1


def set_hdr_world(scene: bpy.types.Scene, hdr_path: Path | None) -> Path | None:
    if not hdr_path:
        return None

    world = scene.world or bpy.data.worlds.new(PREVIEW_WORLD_NAME)
    scene.world = world
    world.name = PREVIEW_WORLD_NAME
    world.use_nodes = True

    nodes = world.node_tree.nodes
    links = world.node_tree.links
    background = nodes.get("Background")
    if not background:
        background = nodes.new(type="ShaderNodeBackground")

    output = nodes.get("World Output")
    if not output:
        output = nodes.new(type="ShaderNodeOutputWorld")

    environment = nodes.get("Muse3D_Morning_HDR")
    if not environment:
        environment = nodes.new(type="ShaderNodeTexEnvironment")
        environment.name = "Muse3D_Morning_HDR"

    environment.image = bpy.data.images.load(str(hdr_path), check_existing=True)
    background.inputs["Strength"].default_value = 0.85

    if not any(link.from_node == environment and link.to_node == background for link in links):
        links.new(environment.outputs["Color"], background.inputs["Color"])
    if not any(link.from_node == background and link.to_node == output for link in links):
        links.new(background.outputs["Background"], output.inputs["Surface"])

    return hdr_path


def ensure_preview_light() -> None:
    if bpy.data.objects.get(PREVIEW_SUN_NAME):
        return

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 12))
    sun = bpy.context.object
    sun.name = PREVIEW_SUN_NAME
    sun.data.name = PREVIEW_SUN_NAME
    sun.data.energy = 1.8
    sun.rotation_euler = (0.82, 0, 0.64)


def set_viewport_material_mode(*, rendered: bool) -> None:
    shading_type = "RENDERED" if rendered else "MATERIAL"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue

            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue

                space.shading.type = shading_type
                if hasattr(space.shading, "color_type"):
                    space.shading.color_type = "TEXTURE"
                if hasattr(space.shading, "use_scene_world_render"):
                    space.shading.use_scene_world_render = True
                if hasattr(space.shading, "use_scene_lights_render"):
                    space.shading.use_scene_lights_render = True
                space.clip_end = max(space.clip_end, 5000)


def apply_blender_preview_environment(
    hdr_path: str | Path | None = None,
    *,
    rendered: bool = True,
) -> Path | None:
    """Activa materiales/texturas y usa mañana.hdr como cielo de referencia."""

    scene = bpy.context.scene
    resolved_hdr = resolve_hdr_path(hdr_path)
    set_scene_engine(scene)
    set_color_management(scene)
    applied_hdr = set_hdr_world(scene, resolved_hdr)
    ensure_preview_light()
    set_viewport_material_mode(rendered=rendered)

    if applied_hdr:
        print(f"[Muse3D] Vista Blender con materiales + cielo HDR: {applied_hdr}")
    else:
        print("[Muse3D] Vista Blender con materiales; no se encontro mañana.hdr")

    return applied_hdr


if __name__ == "__main__":
    apply_blender_preview_environment(rendered=True)
