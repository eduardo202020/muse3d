"""Lanza Blender con un GLB y una ruta inmersiva editable.

Este script es el punto de entrada del pipeline sin IA:
1. Recibe un GLB de sala/lugar.
2. Abre Blender.
3. Importa el GLB.
4. Crea 10/12/15 puntos `Tour_XX` y `Target_XX`.
5. Deja la escena lista para ajuste manual.

Ejemplo:
  python3 scripts/create_immersive_tour_workspace.py models/immersive/lugar.glb --points 12
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = PROJECT_ROOT / "scripts" / "setup_immersive_tour.py"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "immersive"


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Abrir Blender con ruta editable para un GLB.")
    parser.add_argument("model", help="Ruta del GLB de sala/lugar.")
    parser.add_argument("--points", type=int, default=12, help="Cantidad de puntos de recorrido.")
    parser.add_argument("--route-id", default="", help="ID de ruta para exportar.")
    parser.add_argument("--route-model", default="", help="Ruta de modelo guardada en el JSON.")
    parser.add_argument("--description", default="", help="Descripcion de la ruta.")
    parser.add_argument("--save-blend", default="", help="Blend opcional donde guardar el workspace.")
    parser.add_argument("--blender", default="blender", help="Binario de Blender.")
    parser.add_argument("--wait", action="store_true", help="Esperar hasta cerrar Blender.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    blender_bin = shutil.which(args.blender) or args.blender
    model_path = Path(args.model).expanduser().resolve()
    slug = slugify(model_path.stem)
    route_id = args.route_id or f"{slug}-walking-tour"
    route_model = args.route_model or relative_to_project(model_path)
    description = args.description or "Ruta caminable generada automaticamente para ajuste manual."
    save_blend = (
        Path(args.save_blend).expanduser().resolve()
        if args.save_blend
        else PROJECT_ROOT / "workspaces" / f"{slug}-tour.blend"
    )

    command = [
        blender_bin,
        "--python",
        str(SETUP_SCRIPT),
        "--",
        str(model_path),
        "--points",
        str(args.points),
        "--route-id",
        route_id,
        "--route-model",
        route_model,
        "--description",
        description,
        "--save-blend",
        str(save_blend),
    ]

    print("[Muse3D] Abriendo Blender para editar ruta:")
    print(" ".join(command))
    print()
    print("[Muse3D] Al terminar de ajustar, exporta con:")
    print(
        "blender "
        f"{save_blend} --background --python {PROJECT_ROOT / 'scripts' / 'export_immersive_tour.py'} "
        f"-- {PROJECT_ROOT / 'routes' / f'{route_id}.json'}"
    )

    process = subprocess.Popen(command)
    if args.wait:
        process.wait()


if __name__ == "__main__":
    main()
