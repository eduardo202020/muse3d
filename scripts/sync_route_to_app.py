"""Convierte una ruta JSON de Muse3D en una constante TypeScript para MuseIQ App.

El script no registra automaticamente la sala en `room-experiences.ts`; solo
mantiene sincronizada la definicion del tour dentro de `lib/immersive-tours.ts`.

Ejemplo:
  python3 scripts/sync_route_to_app.py routes/lugar-walking-tour.json --export-name lugarWalkingTour
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_FILE = PROJECT_ROOT.parent / "museApp" / "lib" / "immersive-tours.ts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sincronizar ruta JSON hacia TypeScript.")
    parser.add_argument("route_json", help="Ruta JSON exportada por Muse3D.")
    parser.add_argument("--app-file", default=str(DEFAULT_APP_FILE))
    parser.add_argument("--export-name", default="")
    return parser.parse_args()


def to_camel_case(value: str) -> str:
    parts = [part for part in re.split(r"[^a-zA-Z0-9]+", value) if part]
    if not parts:
        return "immersiveTour"

    first, *rest = parts
    return first[:1].lower() + first[1:] + "".join(part[:1].upper() + part[1:] for part in rest)


def format_number(value: float) -> str:
    rounded = round(float(value), 5)
    if rounded == int(rounded):
        return str(int(rounded))

    return str(rounded).rstrip("0").rstrip(".")


def format_vector(vector: dict[str, float]) -> str:
    return (
        "{ "
        f"x: {format_number(vector['x'])}, "
        f"y: {format_number(vector['y'])}, "
        f"z: {format_number(vector['z'])}"
        " }"
    )


def build_tour_block(route: dict, export_name: str) -> str:
    lines = [
        f"export const {export_name}: ImmersiveTourDefinition = {{",
        f"  id: {json.dumps(route['id'])},",
    ]
    if route.get("model"):
        lines.append(f"  model: {json.dumps(route['model'])},")
    lines.extend(
        [
            f"  coordinateSystem: {json.dumps(route.get('coordinateSystem', 'blender-z-up'))},",
        ]
    )
    if route.get("description"):
        lines.append(f"  description: {json.dumps(route['description'])},")
    lines.append("  points: [")

    for point in route.get("points", []):
        lines.extend(
            [
                "    {",
                f"      id: {json.dumps(point['id'])},",
                f"      duration: {format_number(point['duration'])},",
                f"      position: {format_vector(point['position'])},",
                f"      target: {format_vector(point['target'])},",
            ]
        )
        if "fov" in point:
            lines.append(f"      fov: {format_number(point['fov'])},")
        lines.append("    },")

    lines.extend(["  ],", "};", ""])
    return "\n".join(lines)


def replace_or_append_const(source: str, export_name: str, block: str) -> str:
    pattern = re.compile(
        rf"export const {re.escape(export_name)}: ImmersiveTourDefinition = \{{.*?\n\}};\n",
        re.DOTALL,
    )
    if pattern.search(source):
        return pattern.sub(block, source)

    return source.rstrip() + "\n\n" + block


def main() -> None:
    args = parse_args()
    route_path = Path(args.route_json).expanduser().resolve()
    app_file = Path(args.app_file).expanduser().resolve()
    route = json.loads(route_path.read_text(encoding="utf-8"))
    export_name = args.export_name or to_camel_case(str(route.get("id", route_path.stem)))
    block = build_tour_block(route, export_name)

    source = app_file.read_text(encoding="utf-8")
    app_file.write_text(replace_or_append_const(source, export_name, block), encoding="utf-8")
    print(f"[Muse3D] Ruta sincronizada en {app_file}: {export_name}")


if __name__ == "__main__":
    main()
