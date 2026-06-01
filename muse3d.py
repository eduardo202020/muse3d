"""Asistente interactivo de Muse3D.

Entrada recomendada para construir experiencias inmersivas sin ejecutar varios
scripts manualmente:

  python3 muse3d.py

El asistente permite seleccionar un GLB, crear una ruta editable, abrir Blender,
esperar el ajuste manual, exportar el JSON y sincronizar la lista de experiencias
con MuseIQ App.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
APP_ROOT = PROJECT_ROOT.parent / "museiqApp"
MANIFEST_PATH = PROJECT_ROOT / "experiences" / "immersive-experiences.json"
SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "setup_immersive_tour.py"
SYNC_ROUTE_SCRIPT = PROJECT_ROOT / "scripts" / "sync_route_to_app.py"
GENERATED_APP_FILE = APP_ROOT / "lib" / "immersive-experiences.generated.ts"
APP_MODELS_DIR = APP_ROOT / "assets" / "models" / "immersive"
DEFAULT_ROOM_ID = "SALA_1"
MAX_ADDED_PAIR_COUNT = 24


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "immersive"


def to_camel_case(value: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    if not parts:
        return "immersiveExperience"

    first, *rest = parts
    return first[:1].lower() + first[1:] + "".join(part[:1].upper() + part[1:] for part in rest)


def title_from_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in slugify(value).split("-")) or "Experiencia"


def json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def prompt_text(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def prompt_int(label: str, default: int) -> int:
    while True:
        raw_value = prompt_text(label, str(default))
        try:
            value = int(raw_value)
        except ValueError:
            print("Ingresa un numero valido.")
            continue

        if value <= 0:
            print("Ingresa un numero mayor a cero.")
            continue

        return value


def prompt_yes_no(label: str, default: bool = True) -> bool:
    default_text = "S/n" if default else "s/N"
    while True:
        value = input(f"{label} [{default_text}]: ").strip().lower()
        if not value:
            return default
        if value in {"s", "si", "sí", "y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Responde con s o n.")


def prompt_choice(label: str, options: list[Path]) -> Path | None:
    if not options:
        return None

    print(label)
    for index, option in enumerate(options, start=1):
        try:
            display = option.relative_to(PROJECT_ROOT)
        except ValueError:
            try:
                display = Path("museiqApp") / option.relative_to(APP_ROOT)
            except ValueError:
                display = option
        print(f"  {index}. {display}")

    while True:
        raw_value = input("Seleccion: ").strip()
        try:
            selected_index = int(raw_value)
        except ValueError:
            print("Ingresa el numero de la opcion.")
            continue

        if 1 <= selected_index <= len(options):
            return options[selected_index - 1]

        print("Seleccion fuera de rango.")


def discover_immersive_glbs() -> list[Path]:
    roots = [PROJECT_ROOT / "models" / "immersive", APP_MODELS_DIR]
    glbs: list[Path] = []
    for root in roots:
        if root.exists():
            glbs.extend(sorted(root.rglob("*.glb")))
    unique_glbs = {path.resolve(): path.resolve() for path in glbs}
    return sorted(unique_glbs.values())


def load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return []

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(experiences: list[dict[str, Any]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(experiences, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def relative_to_app(path: Path) -> str:
    try:
        return path.resolve().relative_to(APP_ROOT).as_posix()
    except ValueError:
        return path.name


def route_model_reference(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return relative_to_app(path)


def copy_model_to_app(model_path: Path) -> str:
    APP_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    destination = APP_MODELS_DIR / model_path.name

    if destination.exists() and destination.resolve() != model_path.resolve():
        overwrite = prompt_yes_no(
            f"Ya existe {relative_to_app(destination)}. Sobrescribirlo",
            default=False,
        )
        if not overwrite:
            return relative_to_app(destination)

    if destination.resolve() != model_path.resolve():
        shutil.copy2(model_path, destination)
        print(f"[Muse3D] Modelo copiado a la app: {relative_to_app(destination)}")

    return relative_to_app(destination)


def generate_app_experience_file(experiences: list[dict[str, Any]]) -> None:
    imports: list[str] = []
    rows: list[str] = []
    used_model_imports: set[str] = set()
    used_tour_imports: set[str] = set()

    for experience in experiences:
        model_import = to_camel_case(f"{Path(experience['modelAssetPath']).stem} glb")
        while model_import in used_model_imports:
            model_import = f"{model_import}Asset"
        used_model_imports.add(model_import)
        experience["_modelImport"] = model_import
        imports.append(
            f"import {model_import} from \"@/{experience['modelAssetPath']}\";"
        )

    tour_imports = []
    for experience in experiences:
        tour_export = experience["tourExportName"]
        if tour_export not in used_tour_imports:
            used_tour_imports.add(tour_export)
            tour_imports.append(tour_export)

    imports = sorted(imports)
    tour_import_line = (
        f"import {{ {', '.join(sorted(tour_imports))} }} from \"@/lib/immersive-tours\";"
        if tour_imports
        else ""
    )

    for experience in experiences:
        rows.extend(
            [
                "  {",
                f"    id: {json_string(experience['id'])},",
                f"    roomId: {json_string(experience['roomId'])},",
                f"    title: {json_string(experience['title'])},",
                f"    promptTitle: {json_string(experience['promptTitle'])},",
                f"    description: {json_string(experience['description'])},",
                f"    ctaLabel: {json_string(experience['ctaLabel'])},",
                f"    modelAsset: {experience['_modelImport']},",
                f"    modelLabel: {json_string(experience['modelLabel'])},",
                f"    tour: {experience['tourExportName']},",
                "  },",
            ]
        )

    content_lines = [
        "// Archivo generado por muse3d.py. No editar a mano.",
        *imports,
        'import type { RoomImmersiveExperience } from "@/lib/immersive-experience-types";',
    ]
    if tour_import_line:
        content_lines.append(tour_import_line)
    content_lines.extend(
        [
            "",
            "export const immersiveRoomExperiences: RoomImmersiveExperience[] = [",
            *rows,
            "];",
            "",
        ]
    )
    GENERATED_APP_FILE.write_text("\n".join(content_lines), encoding="utf-8")
    print(f"[Muse3D] Lista de experiencias generada: {GENERATED_APP_FILE}")


def upsert_experience(experience: dict[str, Any]) -> None:
    experiences = load_manifest()
    next_experiences = [item for item in experiences if item.get("id") != experience["id"]]
    next_experiences.append(experience)
    next_experiences.sort(key=lambda item: (item.get("roomId", ""), item.get("title", "")))
    save_manifest(next_experiences)
    generate_app_experience_file(next_experiences)


def run_command(command: list[str]) -> None:
    print()
    print("[Muse3D] Ejecutando:")
    print(" ".join(command))
    subprocess.run(command, check=True)


def launch_command(command: list[str]) -> subprocess.Popen:
    print()
    print("[Muse3D] Abriendo:")
    print(" ".join(command))
    return subprocess.Popen(command)


def send_blender_command(
    command_file: Path,
    status_file: Path,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    command_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    command_id = str(time.time_ns())
    command_payload = {
        "id": command_id,
        **payload,
    }

    command_file.write_text(json.dumps(command_payload, indent=2), encoding="utf-8")
    started_at = time.time()

    while time.time() - started_at < timeout_seconds:
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                time.sleep(0.2)
                continue

            if str(status.get("id")) == command_id:
                if status.get("status") == "done":
                    return status
                if status.get("status") == "error":
                    raise RuntimeError(str(status.get("message", "Error en Blender")))

        time.sleep(0.25)

    raise RuntimeError("No hubo respuesta del Blender abierto. Revisa que siga ejecutandose.")


def select_or_enter_model() -> Path:
    glbs = discover_immersive_glbs()
    selected = prompt_choice("Selecciona el GLB del lugar:", glbs)
    if selected:
        return selected.resolve()

    while True:
        model_path = Path(prompt_text("Ruta del GLB")).expanduser().resolve()
        if model_path.exists() and model_path.suffix.lower() == ".glb":
            return model_path
        print("No encontre ese GLB. Revisa la ruta.")


def preview_tour_in_blender(command_file: Path, status_file: Path) -> None:
    try:
        status = send_blender_command(
            command_file,
            status_file,
            {
                "action": "preview",
                "fps": 24,
                "play": True,
                "startFrame": 1,
            },
            timeout_seconds=15,
        )
        print(f"[Muse3D] {status.get('message', 'Preview actualizado')}")
        print("[Muse3D] Mira la timeline de Blender: la camara Muse3D_Preview_Camera ya esta animada.")
    except RuntimeError as error:
        print(f"[Muse3D] No se pudo previsualizar en vivo: {error}")


def add_tour_pairs_in_blender(command_file: Path, status_file: Path) -> None:
    requested_count = prompt_int("Cantidad de pares Tour/Target a agregar", 1)
    count = min(requested_count, MAX_ADDED_PAIR_COUNT)
    if count != requested_count:
        print(f"[Muse3D] Por seguridad se agregaran {MAX_ADDED_PAIR_COUNT} pares como maximo.")

    try:
        status = send_blender_command(
            command_file,
            status_file,
            {
                "action": "add_pairs",
                "count": count,
            },
            timeout_seconds=15,
        )
        print(f"[Muse3D] {status.get('message', 'Pares Tour/Target creados')}")
        print("[Muse3D] Mueve los nuevos Tour_XX y Target_XX en Blender, luego previsualiza.")
    except RuntimeError as error:
        print(f"[Muse3D] No se pudieron agregar pares en vivo: {error}")


def refresh_blender_view(command_file: Path, status_file: Path) -> None:
    try:
        status = send_blender_command(
            command_file,
            status_file,
            {
                "action": "refresh_view",
            },
            timeout_seconds=15,
        )
        print(f"[Muse3D] {status.get('message', 'Vista actualizada')}")
    except RuntimeError as error:
        print(f"[Muse3D] No se pudo actualizar la vista en vivo: {error}")


def export_and_sync_experience(
    *,
    command_file: Path,
    cta_label: str,
    description: str,
    experience_id: str,
    export_name: str,
    model_path: Path,
    prompt_title: str,
    room_id: str,
    route_path: Path,
    status_file: Path,
    title: str,
) -> bool:
    if not prompt_yes_no("Exportar y sincronizar ahora", default=True):
        return False

    try:
        status = send_blender_command(
            command_file,
            status_file,
            {
                "action": "export",
                "output": str(route_path),
            },
            timeout_seconds=30,
        )
        print(f"[Muse3D] {status.get('message', 'Ruta exportada')}")
    except RuntimeError as error:
        print(f"[Muse3D] No se pudo exportar desde Blender vivo: {error}")
        return False

    run_command(
        [
            sys.executable,
            str(SYNC_ROUTE_SCRIPT),
            str(route_path),
            "--export-name",
            export_name,
        ]
    )

    model_asset_path = copy_model_to_app(model_path)
    upsert_experience(
        {
            "id": experience_id,
            "roomId": room_id,
            "title": title,
            "promptTitle": prompt_title,
            "description": description,
            "ctaLabel": cta_label,
            "modelAssetPath": model_asset_path,
            "modelLabel": model_path.name,
            "tourExportName": export_name,
        }
    )

    print()
    print("[Muse3D] Experiencia lista en la app.")
    print(f"[Muse3D] Ruta: {route_path}")
    print(f"[Muse3D] Experiencia: {experience_id}")
    return True


def run_blender_edit_loop(
    *,
    blender_bin: str,
    cta_label: str,
    description: str,
    experience_id: str,
    export_name: str,
    model_path: Path,
    points: int,
    prompt_title: str,
    room_id: str,
    route_id: str,
    route_model: str,
    route_path: Path,
    title: str,
    workspace_path: Path,
) -> None:
    command_file = workspace_path.with_suffix(".commands.json")
    status_file = workspace_path.with_suffix(".status.json")
    if command_file.exists():
        command_file.unlink()
    if status_file.exists():
        status_file.unlink()

    print()
    print("[Muse3D] Se abrira Blender con la ruta editable.")
    print("[Muse3D] Mientras ajustas, deja esta terminal abierta como panel de control.")
    print("[Muse3D] Puedes previsualizar/exportar sin guardar: se usara la escena viva de Blender.")

    blender_process = launch_command(
        [
            blender_bin,
            "--python",
            str(SETUP_SCRIPT),
            "--",
            str(model_path),
            "--points",
            str(points),
            "--route-id",
            route_id,
            "--route-model",
            route_model,
            "--description",
            description,
            "--save-blend",
            str(workspace_path),
            "--command-file",
            str(command_file),
            "--status-file",
            str(status_file),
        ]
    )

    while True:
        process_state = "abierto" if blender_process.poll() is None else "cerrado"
        print()
        print(f"Muse3D - Edicion de tour ({process_state})")
        print("1. Previsualizar recorrido en Blender")
        print("2. Anadir pares Tour/Target")
        print("3. Exportar y sincronizar con la app")
        print("4. Actualizar materiales/cielo en Blender")
        print("5. Terminar sin exportar")
        option = input("Seleccion: ").strip()

        if option == "1":
            preview_tour_in_blender(command_file, status_file)
        elif option == "2":
            add_tour_pairs_in_blender(command_file, status_file)
        elif option == "3":
            exported = export_and_sync_experience(
                command_file=command_file,
                cta_label=cta_label,
                description=description,
                experience_id=experience_id,
                export_name=export_name,
                model_path=model_path,
                prompt_title=prompt_title,
                room_id=room_id,
                route_path=route_path,
                status_file=status_file,
                title=title,
            )
            if exported:
                return
        elif option == "4":
            refresh_blender_view(command_file, status_file)
        elif option == "5":
            print("[Muse3D] Flujo terminado. Blender queda bajo tu control si sigue abierto.")
            return
        else:
            print("Seleccion no valida.")


def create_or_update_experience(blender_bin: str) -> None:
    model_path = select_or_enter_model()
    slug = slugify(model_path.stem)
    route_id = prompt_text("ID de ruta", f"{slug}-walking-tour")
    experience_id = prompt_text("ID de experiencia", f"immersive-{slug}")
    export_name = prompt_text("Nombre TS del tour", to_camel_case(route_id))
    room_id = prompt_text("Room ID de la app", DEFAULT_ROOM_ID)
    title = prompt_text("Titulo visible", title_from_slug(slug))
    prompt_title = prompt_text("Titulo del modal", "Modo inmersivo disponible")
    description = prompt_text(
        "Descripcion",
        "Recorrido inmersivo por una reconstruccion 3D preparada para headset.",
    )
    cta_label = prompt_text("Texto CTA", "Entrar al modo inmersivo")
    points = prompt_int("Cantidad de puntos", 12)

    workspace_path = PROJECT_ROOT / "workspaces" / f"{slug}-tour.blend"
    route_path = PROJECT_ROOT / "routes" / f"{route_id}.json"
    route_model = route_model_reference(model_path)

    run_blender_edit_loop(
        blender_bin=blender_bin,
        cta_label=cta_label,
        description=description,
        experience_id=experience_id,
        export_name=export_name,
        model_path=model_path,
        points=points,
        prompt_title=prompt_title,
        room_id=room_id,
        route_id=route_id,
        route_model=route_model,
        route_path=route_path,
        title=title,
        workspace_path=workspace_path,
    )


def sync_app_from_manifest() -> None:
    experiences = load_manifest()
    if not experiences:
        print("[Muse3D] No hay experiencias en el manifiesto.")
        return

    generate_app_experience_file(experiences)


def run_menu(blender_bin: str) -> None:
    while True:
        print()
        print("Muse3D")
        print("1. Crear/editar experiencia inmersiva desde GLB")
        print("2. Regenerar lista de experiencias en la app")
        print("3. Salir")
        option = input("Seleccion: ").strip()

        if option == "1":
            create_or_update_experience(blender_bin)
        elif option == "2":
            sync_app_from_manifest()
        elif option == "3":
            return
        else:
            print("Seleccion no valida.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Asistente interactivo de Muse3D.")
    parser.add_argument("--blender", default="blender", help="Binario de Blender.")
    parser.add_argument(
        "--sync-app",
        action="store_true",
        help="Solo regenera la lista de experiencias de la app desde el manifiesto.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    blender_bin = shutil.which(args.blender) or args.blender
    if args.sync_app:
        sync_app_from_manifest()
        return

    run_menu(blender_bin)


if __name__ == "__main__":
    main()
