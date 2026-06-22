from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .manifest import find_manifest
from .pipeline import (
    BuildOptions,
    build_manifest,
    muserag_ar_dir,
    project_root,
    rebuild_catalog,
    resolve_blender,
    resolve_tool,
)


def add_common_build_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--publish", action="store_true", help="Copy output to museRAG/assets/ar.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without running them.")
    parser.add_argument("--skip-optimize", action="store_true", help="Copy raw GLB without glTF optimization.")
    parser.add_argument("--skip-validate", action="store_true", help="Skip Khronos glTF validation.")
    parser.add_argument("--blender", help="Path to blender executable.")


def command_doctor(_: argparse.Namespace) -> int:
    root = project_root()
    print("Muse3D doctor")
    print(f"root: {root}")
    print(f"python: {sys.version.split()[0]}")

    node = resolve_tool("node")
    npx = resolve_tool("npx")
    blender = resolve_blender(root)
    target = muserag_ar_dir(root)
    node_modules = root / "node_modules"

    checks = [
        ("Node.js", node or "not found"),
        ("npx", npx or "not found"),
        ("Blender", blender or "not found; set BLENDER_PATH in .env"),
        ("node_modules", "installed" if node_modules.exists() else "not installed; run npm install"),
        ("MuseRAG AR target", str(target)),
    ]

    for label, value in checks:
        print(f"- {label}: {value}")
    return 0


def command_build(args: argparse.Namespace) -> int:
    root = project_root()
    manifest_path = find_manifest(root, args.manifest)
    result = build_manifest(
        manifest_path,
        BuildOptions(
            dry_run=args.dry_run,
            publish=args.publish,
            skip_optimize=args.skip_optimize,
            skip_validate=args.skip_validate,
            blender_path=args.blender,
        ),
    )

    print(f"Built: {result.manifest.artwork_id}")
    print(f"- GLB: {result.final_glb}")
    print(f"- Metadata: {result.metadata}")
    if result.validation_report:
        print(f"- Validation: {result.validation_report}")
    if result.published_dir:
        print(f"- Published: {result.published_dir}")
    return 0


def command_build_all(args: argparse.Namespace) -> int:
    root = project_root()
    manifest_dir = root / "manifests"
    manifest_paths = sorted(
        [
            *manifest_dir.glob("*.yaml"),
            *manifest_dir.glob("*.yml"),
            *manifest_dir.glob("*.json"),
        ]
    )
    if not manifest_paths:
        print(f"No manifests found in {manifest_dir}")
        return 1

    for manifest_path in manifest_paths:
        print(f"\n==> {manifest_path.name}")
        build_manifest(
            manifest_path,
            BuildOptions(
                dry_run=args.dry_run,
                publish=args.publish,
                skip_optimize=args.skip_optimize,
                skip_validate=args.skip_validate,
                blender_path=args.blender,
            ),
        )
    print(f"\nBuilt {len(manifest_paths)} manifest(s).")
    return 0


def command_catalog(args: argparse.Namespace) -> int:
    catalog_path = rebuild_catalog(project_root(), publish=args.publish, dry_run=args.dry_run)
    print(f"Catalog: {catalog_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="muse3d",
        description="Build, optimize, validate, and publish MuseIQ GLB assets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check local toolchain.")
    doctor.set_defaults(func=command_doctor)

    build = subparsers.add_parser("build", help="Build one artwork manifest.")
    build.add_argument("manifest", help="Manifest path or artwork id in manifests/.")
    add_common_build_options(build)
    build.set_defaults(func=command_build)

    build_all = subparsers.add_parser("build-all", help="Build every manifest.")
    add_common_build_options(build_all)
    build_all.set_defaults(func=command_build_all)

    catalog = subparsers.add_parser("catalog", help="Rebuild AR catalog from dist.")
    catalog.add_argument("--publish", action="store_true", help="Copy catalog to museRAG/assets/ar/catalog.json.")
    catalog.add_argument("--dry-run", action="store_true", help="Print actions without running them.")
    catalog.set_defaults(func=command_catalog)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
